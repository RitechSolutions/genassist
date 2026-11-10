"""
The tools the Workflow Builder agent uses to read and change a workflow draft.

Each tool is a thin wrapper over ``WorkflowDraft``: load the draft for the
conversation, apply one operation, save, and return a short text result. A
failed operation changes nothing and returns the reason, so the agent can
correct itself in the same turn.
"""

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

import re

from app.modules.workflow.builder import catalog, patterns, resources
from app.modules.workflow.builder.draft import DraftError, WorkflowDraft, load_draft, save_draft
from app.modules.workflow.builder.narration import StepNarrator
from app.modules.workflow.builder.resources import describe_resources
from app.modules.workflow.builder.testing import (
    error_signature,
    run_draft_test,
    test_found_code_error,
    test_passed,
    test_was_attempted,
)

# A fix-and-retest loop on one error burns a model call per attempt and rarely converges.
MAX_SAME_FAILURE = 3
MAX_FAILED_TESTS = 5

logger = logging.getLogger(__name__)

# One lock per conversation: an agent may issue several tool calls at once, and
# each call is a read-modify-write of the same draft.
_locks: Dict[str, asyncio.Lock] = {}


def _lock_for(thread_id: str) -> asyncio.Lock:
    lock = _locks.get(thread_id)
    if lock is None:
        lock = _locks[thread_id] = asyncio.Lock()
    return lock


def _param(kind: str, description: str, required: bool = True) -> Dict[str, Any]:
    return {"type": kind, "description": description, "required": required}


_NODE_ID = "Node id from the workflow outline, e.g. \"n3\"."

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "get_workflow",
        "description": (
            "The workflow outline again: nodes with ids, settings, connections, open issues, workspace "
            "resources. Every message already arrives with it; call this after your changes when you "
            "need the whole picture (each change also returns what is still open)."
        ),
        "parameters": {},
    },
    {
        "name": "get_node",
        "description": "One node's full config (long prompts and code in full) and its connections.",
        "parameters": {"node_id": _param("string", _NODE_ID)},
    },
    {
        "name": "lookup_node",
        "description": (
            "Find node types by what they do, or by exact type name. Returns the matches and the full "
            "settings, handles and usage rules of the best one."
        ),
        "parameters": {"query": _param("string", "Keywords (\"send slack message\") or a type (\"switchNode\").")},
    },
    {
        "name": "get_pattern",
        "description": "A ready apply_plan for a common shape, with notes. No name lists the patterns.",
        "parameters": {"name": _param("string", "Pattern name.", required=False)},
    },
    {
        "name": "list_resources",
        "description": "Full list of the workspace's knowledge bases, integrations or data sources, when the outline shows only part.",
        "parameters": {"kind": _param("string", "knowledge_bases, integrations or data_sources.")},
    },
    {
        "name": "search_web",
        "description": (
            "Search the web for facts you do not have: a business's products, policies or tone for an agent "
            "brief, an external API's endpoints and fields for an API step, a service's rules. Returns a few "
            "results with title, link and snippet. Not for GenAssist node names or settings (use lookup_node)."
        ),
        "parameters": {"query": _param("string", "A short, specific search query.")},
    },
    {
        "name": "apply_plan",
        "description": (
            "Apply a JSON array of operations in order; failures are reported and skipped. New nodes get a "
            "temporary \"id\": \"$name\" usable in later operations (\"$name.node\" is the node a tool runs). "
            "Operations: "
            "{op:add_node, id, node_type, name, system_prompt?, config?, connect_from?, connect_to?} "
            "(connect_from \"n3\" or \"n3.output_true\"; both connect_from and connect_to inserts between them) | "
            "{op:add_tool, id, agent_id, node_type, name, description, config?, parameters?} "
            "(parameters {name: description} are what the agent passes, read in config as {{source.<name>}}) | "
            "{op:set_node_field, node_id, field, value} | {op:update_node, node_id, config?, name?} | "
            "{op:connect, source, target} | {op:disconnect, source, target} | {op:remove_node, node_id}. "
            "config and parameters are JSON objects."
        ),
        "parameters": {"operations": _param("string", "The JSON array of operations, as text.")},
    },
    {
        "name": "set_node_field",
        "description": "Set one config field as plain text: the way to write or rewrite a system prompt, template or code.",
        "parameters": {
            "node_id": _param("string", _NODE_ID),
            "field": _param("string", "e.g. \"systemPrompt\", \"template\", \"code\"."),
            "value": _param("string", "The new value. Non-text fields as JSON (true, 5, [\"a\"])."),
        },
    },
    {
        "name": "test_workflow",
        "description": (
            "Run the workflow once with a user message: returns the reply, each step's output or error, the "
            "agents' tool calls and the steps that did not run. A real run: tools that send or create really do."
        ),
        "parameters": {
            "message": _param("string", "The user message, written as a real person would."),
            "finalize_if_ok": _param("string", "\"true\" to finalize in the same call when nothing failed and no errors are open.", required=False),
            "summary": _param("string", "One sentence for the finalize.", required=False),
        },
    },
    {
        "name": "get_last_test_run",
        "description": "The person's own latest canvas test run: input, reply, each step's output or error, tool calls.",
        "parameters": {},
    },
    {
        "name": "finalize_workflow",
        "description": "Validate and mark the workflow done, when a passing test already exists. Fails with the errors to fix.",
        "parameters": {"summary": _param("string", "One sentence on what was built or changed.", required=False)},
    },
    {
        "name": "ask_user",
        "description": (
            "Ask the person one question when the answer changes what you build and cannot be assumed. "
            "The options are shown to them as buttons (plus a box to type their own answer). After calling "
            "it, end your turn: reply with the question in one sentence and do not list the options."
        ),
        "parameters": {
            "question": _param("string", "The question, one sentence, in plain words."),
            "options": _param("string", "JSON array of 2 to 4 short answers, e.g. [\"Email the customer\", \"Open a ticket\"]."),
            "recommended": _param("string", "The option you would pick, copied exactly.", required=False),
        },
    },
]

TOOL_NAMES = [tool["name"] for tool in TOOL_DEFINITIONS]

# Tools that only read; they never create a draft or bump its revision.
_READ_ONLY = {
    "get_workflow", "get_node", "lookup_node", "get_pattern", "test_workflow", "list_resources",
    "get_last_test_run", "search_web",
}


def _lookup_node(query: str) -> str:
    """Search plus the best match's schema, so finding and configuring a node is one call."""
    query = (query or "").strip()
    if catalog.is_known(query) and query not in catalog.HIDDEN_NODE_TYPES:
        return catalog.node_schema_text(query)
    matches = catalog.search_nodes(query)
    if not matches:
        return f"No node type matches '{query}'. Node types:\n{catalog.compact_index()}"
    listing = "\n".join(f"- {m['type']} ({m['label']}): {m['description']}" for m in matches)
    return f"Matches:\n{listing}\n\nDetails of {matches[0]['type']}:\n{catalog.node_schema_text(matches[0]['type'])}"


# Results handed to the builder are deliberately small: a handful of snippets is
# enough to write a brief or find an endpoint, and every character comes back on
# each later model call of the turn.
SEARCH_RESULTS = 5
SEARCH_SNIPPET_CHARS = 240


async def _search_web(query: str) -> str:
    """Compact web search for the builder; same kill switch and tenant rate limit as the Web Search node."""
    from app.core.tenant_scope import get_tenant_context
    from app.core.utils.web_search_guard import check_enabled, check_tenant_rate
    from app.core.utils.web_search_utils import WebSearchError, _sanitize_error, search_web

    query = (query or "").strip()
    if not query:
        return "query is required."
    if not check_enabled():
        return "Web search is disabled by the administrator. Build with what the person told you, and ask them for anything you still need."
    if not await check_tenant_rate(get_tenant_context()):
        return "Web search rate limit reached for now. Build with what you know, and ask the person for anything you still need."
    try:
        results = await search_web(query, max_results=SEARCH_RESULTS)
    except WebSearchError as exc:
        return f"Web search failed: {exc}. Do not retry the same query; build with what you know and ask the person if needed."
    except Exception as exc:  # provider or network trouble: never a crash for the agent
        logger.warning("builder web search failed: %s", _sanitize_error(exc))
        return "Web search is unavailable right now. Do not retry; build with what you know and ask the person if needed."
    if not results:
        return f'No results for "{query}". Try different words once, or ask the person.'
    lines = []
    for result in results[:SEARCH_RESULTS]:
        snippet = " ".join(str(result.snippet or "").split())
        if len(snippet) > SEARCH_SNIPPET_CHARS:
            snippet = snippet[: SEARCH_SNIPPET_CHARS - 1].rstrip() + "…"
        lines.append(f"{result.position}. {result.title}\n   {result.url}" + (f"\n   {snippet}" if snippet else ""))
    return "\n".join(lines)


_TEMP_ID = re.compile(r"\$[A-Za-z_]\w*(?:\.node)?")
_TEMP_REF_FIELDS = ("connect_from", "connect_to", "agent_id", "node_id", "source", "target")
_PLAN_OPS = {"add_node", "add_tool", "set_node_field", "update_node", "connect", "disconnect", "remove_node"}


def _parse_plan(operations: Any) -> List[Dict[str, Any]]:
    if isinstance(operations, str):
        try:
            operations = json.loads(operations)
        except json.JSONDecodeError as exc:
            raise DraftError(f"operations must be a JSON array: {exc}") from exc
    if isinstance(operations, dict):
        operations = operations.get("operations", [operations])
    if not isinstance(operations, list) or not operations:
        raise DraftError("operations must be a non-empty JSON array of {\"op\": ..., ...} objects.")
    if not all(isinstance(op, dict) for op in operations):
        raise DraftError("Every operation must be a JSON object.")
    return operations


def _resolve_temp_ids(value: Any, known: Dict[str, str], field: str = "") -> Any:
    """
    Replace "$name" ids with the aliases they became. Reference fields are replaced
    whole; other strings only inside {{node_outputs.$name...}}, so a "$" in prose
    is left alone. An unknown "$name" raises, naming it.
    """
    def lookup(match: re.Match) -> str:
        token = match.group(0)
        if token in known:
            return known[token]
        base = token.split(".")[0]
        if base in known and token.endswith(".node"):
            raise DraftError(f"{token} refers to a node that was not created by add_tool.")
        raise DraftError(
            f"unknown reference {token}: no earlier operation created it, or that operation failed."
        )

    if isinstance(value, str):
        if field in _TEMP_REF_FIELDS:
            return _TEMP_ID.sub(lookup, value)
        return re.sub(
            r"(\{\{node_outputs\.)(\$[A-Za-z_]\w*(?:\.node)?)",
            lambda m: m.group(1) + lookup(_TEMP_ID.match(m.group(2))),
            value,
        )
    if isinstance(value, dict):
        return {k: _resolve_temp_ids(v, known, k if k in _TEMP_REF_FIELDS else "") for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_temp_ids(v, known) for v in value]
    return value


def apply_plan(draft: WorkflowDraft, operations: Any) -> str:
    """
    Apply a list of operations in order, resolving temporary ids as nodes are
    created. Failed operations are reported with their reason and skipped, so
    one bad step does not throw away the rest of the plan.
    """
    plan = _parse_plan(operations)
    known: Dict[str, str] = {}
    lines: List[str] = []
    failures = 0
    # Agents the plan created without choosing memory itself; decided once the plan's wiring is known.
    agents_with_default_memory: List[str] = []
    for index, raw in enumerate(plan, 1):
        op = str(raw.get("op") or raw.get("action") or "").strip()
        temp_id = raw.get("id")
        try:
            if op not in _PLAN_OPS:
                raise DraftError(f"unknown op '{op}'. Use one of: {', '.join(sorted(_PLAN_OPS))}.")
            if temp_id is not None and not re.fullmatch(r"\$[A-Za-z_]\w*", str(temp_id)):
                raise DraftError(f"id must look like \"$name\", got {temp_id!r}.")
            args = {k: v for k, v in raw.items() if k not in ("op", "action", "id") and v is not None}
            args = _resolve_temp_ids(args, known)
            if op == "add_node":
                result = draft.add_node(
                    args.get("node_type"), args.get("name"), args.get("config"),
                    args.get("connect_from"), args.get("connect_to"), args.get("system_prompt"),
                )
                if temp_id:
                    known[temp_id] = result["alias"]
                if args.get("node_type") == "agentNode" and "memory" not in (args.get("config") or {}):
                    agents_with_default_memory.append(result["node_id"])
            elif op == "add_tool":
                result = draft.add_tool(
                    args.get("agent_id"), args.get("node_type"), args.get("name") or "Tool",
                    args.get("description"), args.get("config"), args.get("parameters"),
                )
                if temp_id:
                    known[temp_id] = result["tool"]
                    known[f"{temp_id}.node"] = result["node"]
            elif op == "set_node_field":
                result = draft.set_field(args.get("node_id"), args.get("field"), args.get("value"))
            elif op == "update_node":
                result = draft.update_node(args.get("node_id"), args.get("config"), args.get("name"))
            elif op == "remove_node":
                result = draft.remove_node(args.get("node_id"))
            elif op == "connect":
                result = draft.connect(
                    args.get("source"), args.get("target"), args.get("source_handle"), args.get("target_handle")
                )
            else:
                result = draft.disconnect(args.get("source"), args.get("target"), args.get("source_handle"))
            lines.append(f"{index}. {result['message']}")
        except DraftError as exc:
            failures += 1
            label = f" ({temp_id})" if temp_id else ""
            lines.append(f"{index}. {op}{label} FAILED: {exc}")
    quieted = draft.quiet_parsing_agents(agents_with_default_memory)
    if quieted:
        lines.append(
            f"Memory turned off on {', '.join(quieted)}: the reply goes to a step that parses or compares it, "
            f"not to the person. Set memory to true only if it must remember the conversation."
        )
    applied = len(plan) - failures
    header = f"Applied {applied} of {len(plan)} operations." + (
        f" {failures} failed; fix only those (later operations that referenced them failed too)."
        if failures else ""
    )
    return "\n".join([header, *lines])


def _apply(draft: WorkflowDraft, name: str, args: Dict[str, Any]) -> str:
    if name == "get_workflow":
        return draft.render_outline()
    if name == "get_last_test_run":
        return draft.last_user_test or (
            "The person has not test-run this workflow on the canvas in this session. Use test_workflow "
            "to run it yourself with the message they describe."
        )
    if name == "get_node":
        return draft.render_node(args.get("node_id"))
    if name == "apply_plan":
        return apply_plan(draft, args.get("operations"))
    if name == "add_node":
        return draft.add_node(
            args.get("node_type"), args.get("name"), args.get("config"),
            args.get("connect_from"), args.get("connect_to"), args.get("system_prompt"),
        )["message"]
    if name == "add_tool":
        return draft.add_tool(
            args.get("agent_id"), args.get("node_type"), args.get("name") or "Tool",
            args.get("description"), args.get("config"), args.get("parameters"),
        )["message"]
    if name == "set_node_field":
        return draft.set_field(args.get("node_id"), args.get("field"), args.get("value"))["message"]
    if name == "update_node":
        return draft.update_node(args.get("node_id"), args.get("config"), args.get("name"))["message"]
    if name == "remove_node":
        return draft.remove_node(args.get("node_id"))["message"]
    if name == "connect":
        return draft.connect(
            args.get("source"), args.get("target"), args.get("source_handle"), args.get("target_handle")
        )["message"]
    if name == "disconnect":
        return draft.disconnect(args.get("source"), args.get("target"), args.get("source_handle"))["message"]
    if name == "finalize_workflow":
        return draft.finalize(args.get("summary") or "")["message"]
    raise DraftError(f"Unknown tool '{name}'.")


async def run_tool(
    thread_id: str,
    name: str,
    args: Dict[str, Any],
    usage_sink: Optional[list] = None,
) -> str:
    """
    Execute one builder tool for a conversation and return its text result.

    ``usage_sink`` collects the LLM usage of a test run, so it is accounted to
    the builder conversation that asked for it. On a streamed chat turn the call
    is narrated as one step ("Adding 3 steps"), so the person sees the work.
    """
    args = {k: v for k, v in (args or {}).items() if v is not None}
    narrator = StepNarrator(name, args)
    if not narrator.needs_node_name:
        narrator.start()
    try:
        result = await _run_tool(thread_id, name, args, usage_sink, narrator)
    except Exception:
        narrator.fail()
        raise
    narrator.end(result)
    return result


async def _run_tool(
    thread_id: str,
    name: str,
    args: Dict[str, Any],
    usage_sink: Optional[list],
    narrator: StepNarrator,
) -> str:
    # Catalog lookups do not touch the draft.
    if name == "lookup_node":
        return _lookup_node(str(args.get("query") or args.get("node_type") or ""))
    if name == "get_pattern":
        return patterns.describe(args.get("name"))

    if name == "search_web":
        return await _search_web(str(args.get("query") or ""))

    if name == "list_resources":
        draft = await load_draft(thread_id)
        if draft is None or not draft.authenticated:
            return (
                "Resources can only be looked up once the person is signed in and working on the canvas. "
                "Leave the field unset and tell them what they will need to select."
            )
        return await describe_resources(str(args.get("kind", "")))

    if name == "test_workflow":
        # The agent may send a change and this test in the same step, and the agent
        # loop runs the calls of one step concurrently. Reading under the lock waits
        # for a write that started first, so the run tests what was just written.
        # The run itself stays outside the lock: it can take a while and must not
        # block other tool calls.
        async with _lock_for(thread_id):
            draft = await load_draft(thread_id) or WorkflowDraft()
        if draft.failed_tests >= MAX_FAILED_TESTS:
            return (
                f"STOP: {draft.failed_tests} test runs in a row have failed, so no more runs are allowed "
                f"this turn. Do not change anything else. Reply to the person now: say plainly that the "
                f"workflow is not working yet, what the error is, and what you would try next."
            )
        result = await run_draft_test(draft, str(args.get("message", "")), usage_sink=usage_sink)
        if test_was_attempted(result):
            failure = error_signature(result)
            async with _lock_for(thread_id):
                latest = await load_draft(thread_id)
                if latest is not None:
                    if failure:
                        latest.failed_tests += 1
                        latest.same_failure_count = (
                            latest.same_failure_count + 1 if failure == latest.last_failure else 1
                        )
                        latest.last_failure = failure
                    else:
                        latest.failed_tests = latest.same_failure_count = 0
                        latest.last_failure = ""
                    # Only a run of the workflow as it still is, without a bug in a code step,
                    # counts as its test.
                    if latest.revision == draft.revision and not test_found_code_error(result):
                        latest.needs_test = False
                    await save_draft(thread_id, latest)
                    if latest.revision != draft.revision:
                        result += (
                            "\nNOTE: the workflow changed while this test was running, so this report is "
                            "for the version before that change. Run test_workflow again to check the "
                            "current version."
                        )
                    if failure and latest.same_failure_count >= MAX_SAME_FAILURE:
                        result += (
                            f"\nSTOP AND RETHINK: this is the same failure {latest.same_failure_count} times "
                            f"in a row, so your fixes are not addressing its cause. Do not send another "
                            f"variation of the same code. Either change the approach (a different kind of "
                            f"step, usually a language model step when the input is free text), or stop and "
                            f"tell the person what is failing."
                        )
        if test_passed(result) and str(args.get("finalize_if_ok", "")).strip().lower() in ("true", "1", "yes"):
            async with _lock_for(thread_id):
                latest = await load_draft(thread_id)
                if latest is not None and latest.revision == draft.revision:
                    try:
                        finalized = latest.finalize(str(args.get("summary") or ""))
                        await save_draft(thread_id, latest)
                        result += (
                            f"\n{finalized['message']} If the reply above is not what the person asked for, "
                            f"fix the cause and test again; the next passing test re-finalizes."
                        )
                    except DraftError as exc:
                        result += f"\nNot finalized: {exc}"
        return result

    if name == "get_workflow":
        return await workflow_outline(thread_id)

    if name == "ask_user":
        async with _lock_for(thread_id):
            draft = await load_draft(thread_id) or WorkflowDraft()
            try:
                result = draft.ask(args.get("question"), args.get("options"), args.get("recommended"))
            except DraftError as exc:
                return f"ERROR: {exc}"
            # The question rides on the draft without counting as a change to the workflow.
            await save_draft(thread_id, draft)
            return result

    async with _lock_for(thread_id):
        draft = await load_draft(thread_id) or WorkflowDraft()
        if narrator.needs_node_name:
            narrator.start(_node_name(draft, args.get("node_id")))
        try:
            result = _apply(draft, name, args)
        except DraftError as exc:
            return f"ERROR: {exc}"
        if name not in _READ_ONLY:
            await save_draft(thread_id, draft)
            if name != "finalize_workflow":
                result = f"{result}\n{draft.open_problems()}"
        return result


async def workflow_outline(thread_id: str) -> str:
    """The outline of the conversation's draft, with the workspace resources a signed-in build can use."""
    draft = await load_draft(thread_id) or WorkflowDraft()
    outline = draft.render_outline()
    if draft.authenticated:
        # Listed here so a build needs no separate lookup call.
        listing = await resources.summary()
        if listing:
            outline = f"{outline}\n{listing}"
    return outline


TURN_CONTEXT_HEADER = (
    "Current workflow, read for you before this turn (what get_workflow returns; call it again only "
    "when you need the whole picture after your changes):"
)
TURN_CONTEXT_FOOTER = "The person's message follows."


async def turn_context(thread_id: str) -> str:
    """
    The outline handed to the agent together with each message, so a turn starts
    with the work instead of a model call that only asks for it.
    """
    return f"{TURN_CONTEXT_HEADER}\n{await workflow_outline(thread_id)}\n\n{TURN_CONTEXT_FOOTER}"


def _node_name(draft: WorkflowDraft, ref: Any) -> Optional[str]:
    try:
        name = (draft.find(ref).get("data") or {}).get("name")
    except DraftError:
        return None
    return str(name) if name else None


def make_executor(
    thread_id_getter: Callable[[], str],
    name: str,
    usage_sink_getter: Optional[Callable[[], Optional[list]]] = None,
) -> Callable[[Dict[str, Any]], Awaitable[str]]:
    """Adapt ``run_tool`` to the ``function({"parameters": {...}})`` shape agent tools use."""

    async def execute(input_data: Dict[str, Any]) -> str:
        parameters = (input_data or {}).get("parameters") or {}
        try:
            usage_sink = usage_sink_getter() if usage_sink_getter else None
            return await run_tool(thread_id_getter(), name, parameters, usage_sink=usage_sink)
        except Exception as exc:  # never let a tool crash the agent loop
            logger.error("Workflow builder tool '%s' failed: %s", name, exc, exc_info=True)
            return json.dumps({"error": f"{name} failed unexpectedly: {exc}"})

    return execute
