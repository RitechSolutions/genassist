"""
Test runs for the Workflow Builder.

Runs the draft exactly as the canvas "Test" action would (the real engine, the
real nodes) and condenses what the canvas shows under Response, Debug and
Execution into text the builder agent can read: the reply, every node that ran
with its output or error, the tool calls agents made, and which nodes never ran.
"""

import asyncio
import json
import logging
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.utils.llm_usage_utils import BUILDER_TEST_RUN_PURPOSE
from app.modules.workflow.builder.assist import ACTION_NODE_TYPES
from app.modules.workflow.builder.draft import PROVIDER_NODE_TYPES, WorkflowDraft
from app.modules.workflow.builder.validation import VISUAL_NODE_TYPES, blocking

logger = logging.getLogger(__name__)

TEST_TIMEOUT_SECONDS = 120
OUTPUT_LIMIT = 500
RESPONSE_LIMIT = 2000
CODE_ERROR_MARKER = "CODE ERROR"


# Outputs this long are quoted once; a repeat points at the first quote instead.
DEDUPE_MIN_CHARS = 120


def _text(value: Any) -> str:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = str(value)
    return text.strip()


def _clip(value: Any, limit: int) -> str:
    text = _text(value)
    return text if len(text) <= limit else f"{text[:limit]}… (+{len(text) - limit} chars)"


def _quote_once(value: Any, limit: int, label: str, shown: Dict[str, str]) -> str:
    """
    ``value`` clipped, the first time it appears in the report; afterwards a pointer to
    where it was quoted. A passage a tool returned otherwise shows up three times: under
    the knowledge base step, under its tool wrapper and again under the agent's tool calls.
    """
    text = _text(value)
    if len(text) >= DEDUPE_MIN_CHARS:
        if text in shown:
            return f"(same output as {shown[text]})"
        shown[text] = label
    return _clip(text, limit)


def _reply_text(output: Any) -> Any:
    """The part of a run's output the user would actually read."""
    if isinstance(output, dict):
        for key in ("message", "output", "result", "response"):
            if output.get(key) not in (None, ""):
                return output[key]
    return output


async def _default_provider_id() -> Optional[str]:
    try:
        from app.dependencies.injector import injector
        from app.services.llm_providers import LlmProviderService

        provider = await injector.get(LlmProviderService).get_default()
        return str(provider.id)
    except Exception as exc:
        logger.info("Workflow builder test: no default LLM provider available: %s", exc)
        return None


def _initial_input(nodes: List[Dict[str, Any]], message: str) -> Dict[str, Any]:
    """The message plus the Chat Input's declared defaults, as the canvas test sends them."""
    input_data: Dict[str, Any] = {}
    for node in nodes:
        if node.get("type") == "chatInputNode":
            for key, spec in ((node.get("data") or {}).get("inputSchema") or {}).items():
                if isinstance(spec, dict) and spec.get("defaultValue") not in (None, ""):
                    input_data[key] = spec["defaultValue"]
    input_data["message"] = message
    return input_data


_CODE_FIELDS = {"pythonCodeNode": "code", "dataMapperNode": "pythonScript"}
_TRACE_LINE = re.compile(r'File "<string>", line (\d+), in (\w+)')


def _error_in_output(output: Any) -> str:
    """
    Nodes such as the Python executor report a crash as a normal, "successful" output:
    a failure to start as ``error``, an exception raised by the code as ``script_error``.
    """
    if not isinstance(output, dict):
        return ""
    if output.get("error"):
        return str(output["error"])
    if output.get("script_error") and output.get("result") is None:
        return str(output["script_error"])
    return ""


def _explain_code_error(draft: WorkflowDraft, node_id: str, error: str) -> str:
    """
    Reduce a Python traceback to what is needed to fix it: the exception, the line
    number in the step's own code, and that line. Without the line the builder
    rewrites the whole function blind and keeps the bug.
    """
    exception = next((ln.strip() for ln in reversed(error.splitlines()) if ln.strip()), error.strip())
    frames = [(int(n), fn) for n, fn in _TRACE_LINE.findall(error)]
    own = [n for n, fn in frames if fn != "<module>"]
    if not own:
        return exception
    line_no = own[-1]
    try:
        node = draft.find(node_id)
        code = (node.get("data") or {}).get(_CODE_FIELDS.get(node.get("type", ""), "code")) or ""
        source = code.splitlines()[line_no - 1].strip()
    except Exception:
        return f"{exception} (line {line_no})"
    return f"{exception} — at line {line_no} of its code: `{source[:160]}`"


def format_test_result(
    draft: WorkflowDraft,
    message: str,
    response: Dict[str, Any],
    by: str = "",
) -> str:
    state = response.get("state") or {}
    statuses: Dict[str, Any] = state.get("nodeExecutionStatus") or {}
    node_ids = {n["id"] for n in draft.nodes}

    lines = [f"TEST RUN{' by ' + by if by else ''} — input: {_clip(message, 300)}"]
    soft_errors: List[str] = []

    status = response.get("status")
    if status == "awaiting_input":
        lines.append("Result: the run paused waiting for the user to fill in a form (human in the loop).")
    final_error = _error_in_output(response.get("output"))
    if final_error:
        lines.append("Response: none. The run ended with an error instead of a reply (see the failing step below).")
    else:
        lines.append(f"Response: {_clip(_reply_text(response.get('output')), RESPONSE_LIMIT) or '(empty)'}")

    lines.append("Execution (in order):")
    ran: set = set()
    shown: Dict[str, str] = {}
    for key, entry in statuses.items():
        if not isinstance(entry, dict):
            continue
        # Earlier runs of a re-executed node are archived as "<id>_<n>".
        node_id = key if key in node_ids else key.rsplit("_", 1)[0]
        ran.add(node_id)
        label = f"{draft.alias(node_id)} {entry.get('type', '')} \"{entry.get('name', '')}\""
        seconds = (entry.get("time_taken") or 0) / 1000
        soft_error = _error_in_output(entry.get("output"))
        if entry.get("status") == "failed":
            lines.append(f"- {label}: FAILED after {seconds:.1f}s — {_clip(entry.get('error'), OUTPUT_LIMIT)}")
        elif soft_error:
            if entry.get("type") in _CODE_FIELDS:
                soft_errors.append(draft.alias(node_id))
                detail = _explain_code_error(draft, node_id, soft_error)
                lines.append(f"- {label}: ERROR in {seconds:.1f}s — {_clip(detail, OUTPUT_LIMIT)}")
            else:
                # A later step that only passed the failed step's output along.
                lines.append(f"- {label}: received the error above and passed it on")
        else:
            lines.append(
                f"- {label}: {entry.get('status', 'unknown')} in {seconds:.1f}s → "
                f"{_quote_once(entry.get('output'), OUTPUT_LIMIT, draft.alias(node_id), shown) or '(no output)'}"
            )
    if len(lines) and lines[-1] == "Execution (in order):":
        lines.append("- nothing ran")

    tool_events = response.get("tool_events") or []
    failed_tools: List[str] = []
    if tool_events:
        lines.append("Tool calls made by agents:")
        for event in tool_events:
            if event.get("status") == "failed" or event.get("error"):
                failed_tools.append(str(event.get("tool_name")))
                lines.append(
                    f"- {event.get('tool_name')}({_clip(event.get('arguments'), 200)}) FAILED. "
                    f"The tool's own error: \"{_clip(event.get('error') or event.get('result'), 400)}\""
                )
            else:
                lines.append(
                    f"- {event.get('tool_name')}({_clip(event.get('arguments'), 200)}) "
                    f"{event.get('status')}: {_quote_once(event.get('result'), 300, str(event.get('tool_name')), shown)}"
                )
    if failed_tools:
        lines.append(
            f"{len(failed_tools)} tool call(s) failed. Report the quoted error to the person as it is; do not "
            f"guess a different cause. A missing selection is the cause only when the error says so and the "
            f"setup list below confirms it."
        )

    setup_issues = [i for i in draft.issues() if i.severity == "setup"]
    if setup_issues:
        lines.append(
            "Setup still missing on the canvas: "
            + "; ".join(sorted({f"{draft.alias(i.node_id)}.{i.field}" for i in setup_issues}))
        )
    else:
        lines.append(
            "Setup: every provider, knowledge base and credential field is filled in. A failure is not a "
            "missing selection."
        )

    # An agent answering without touching its tools is the usual reason a reply ignores the
    # knowledge base or skips an action, and it is invisible unless called out.
    called_by_agent = {event.get("agent_id") for event in tool_events}
    for node in draft.nodes:
        if node["id"] not in ran or node["id"] in called_by_agent:
            continue
        tools = [
            (draft.find(edge["source"]).get("data") or {}).get("name", "")
            for edge in draft.edges
            if edge["target"] == node["id"] and edge.get("targetHandle") == "input_tools"
        ]
        if tools:
            lines.append(
                f"Note: {draft.alias(node['id'])} \"{(node.get('data') or {}).get('name', '')}\" answered "
                f"without calling any of its tools ({', '.join(tools)}). If it should have, its system "
                f"prompt or the tool description does not make that clear enough."
            )

    not_run = [
        f"{draft.alias(n['id'])} \"{(n.get('data') or {}).get('name', '')}\""
        for n in draft.nodes
        if n.get("type") not in VISUAL_NODE_TYPES and n["id"] not in ran
    ]
    if not_run:
        lines.append(
            "Did not run (other branches, or tools the agent did not call): " + ", ".join(not_run)
        )

    failed = response.get("failed_nodes") or []
    if soft_errors:
        lines.append(
            f"{CODE_ERROR_MARKER}: {', '.join(dict.fromkeys(soft_errors))} raised an error (see above). Read "
            f"the quoted line and fix that line; do not rewrite the rest. If the step is trying to "
            f"understand free text (summarise, extract, classify), code is the wrong tool: replace it "
            f"with a language model step."
        )
    elif failed:
        lines.append(
            f"{len(failed)} node(s) failed. Fix the cause if it is in the workflow; if it is missing setup "
            f"(credentials, a knowledge base), tell the user what to select."
        )
    else:
        lines.append("No node failed. Check that the response is what the user asked for.")
    return "\n".join(lines)


async def run_draft_test(
    draft: WorkflowDraft,
    message: str,
    usage_sink: Optional[list] = None,
    simulate_actions: Optional[bool] = None,
) -> str:
    """Execute the draft once with ``message`` and describe what happened."""
    message = (message or "").strip()
    if not message:
        return "ERROR: message is required: the user message to test the workflow with."
    errors = blocking(draft.issues())
    if errors:
        listing = "\n".join(f"- {draft.describe_issue(i)}" for i in errors)
        return f"ERROR: the workflow cannot run until these errors are fixed:\n{listing}"

    # Run a copy: filling in the default provider for the test must not change the draft.
    nodes, edges = deepcopy(draft.nodes), deepcopy(draft.edges)
    simulate = draft.simulate_actions if simulate_actions is None else simulate_actions
    simulated: List[str] = []
    if simulate:
        # Bypassed steps pass their input through, so the tool call still happens and
        # shows its arguments in the report; only the external action is skipped.
        for node in nodes:
            if node.get("type") in ACTION_NODE_TYPES and not (node.get("data") or {}).get("deactivated"):
                node["data"]["deactivated"] = True
                simulated.append(f"{draft.alias(node['id'])} \"{node['data'].get('name', '')}\"")
    missing_provider = [
        n for n in nodes
        if n.get("type") in PROVIDER_NODE_TYPES and not (n.get("data") or {}).get("providerId")
    ]
    if missing_provider:
        provider_id = draft.defaults.get("providerId") or await _default_provider_id()
        if not provider_id:
            return (
                "ERROR: the workflow cannot be tested yet because no AI provider is configured. "
                "Tell the user to add an LLM provider, then select it on the AI nodes."
            )
        for node in missing_provider:
            node["data"]["providerId"] = provider_id

    from app.modules.workflow.engine.workflow_engine import WorkflowEngine

    # The run's LLM calls are collected here, tagged as test-run usage, then handed to
    # the caller's sink, so the builder's own cost and the cost of what it built stay apart.
    collected: list = []
    try:
        engine = WorkflowEngine({"id": "workflow-builder-test", "nodes": nodes, "edges": edges})
        state = await asyncio.wait_for(
            engine.execute_from_node(
                input_data=_initial_input(nodes, message),
                # A throwaway thread, so test turns never mix with a real conversation's memory.
                thread_id=f"workflow-builder-test-{uuid4()}",
                persist=False,
                usage_sink=collected,
            ),
            timeout=TEST_TIMEOUT_SECONDS,
        )
        response = state.format_state_as_response()
    except asyncio.TimeoutError:
        return f"ERROR: the test run did not finish within {TEST_TIMEOUT_SECONDS} seconds."
    except Exception as exc:
        logger.warning("Workflow builder test run failed: %s", exc, exc_info=True)
        return f"ERROR: the workflow could not be executed: {exc}"
    finally:
        if usage_sink is not None:
            for entry in collected:
                if isinstance(entry, dict) and not entry.get("purpose"):
                    entry["purpose"] = BUILDER_TEST_RUN_PURPOSE
            usage_sink.extend(collected)

    report = format_test_result(draft, message, response)
    if simulated:
        report += (
            f"\nSimulated (nothing was really sent or created): {', '.join(simulated)}. The agent's tool "
            f"calls above show what would have been sent. The person can turn simulation off on the canvas."
        )
    return report


def test_was_attempted(result: str) -> bool:
    """A run counts as the required test unless it was refused for an invalid workflow or empty input."""
    return not result.startswith("ERROR:")


def test_passed(result: str) -> bool:
    """No step or tool failed and the run produced a reply."""
    return (
        test_was_attempted(result)
        and not test_found_code_error(result)
        and ": FAILED after " not in result
        and " FAILED. The tool's own error" not in result
        and "Response: none" not in result
    )


def test_found_code_error(result: str) -> bool:
    """The run hit a bug in a code step: the workflow is not done, whatever else passed."""
    return CODE_ERROR_MARKER in result


def error_signature(result: str) -> str:
    """Identity of a failing run, to notice the same failure coming back."""
    lines = [ln for ln in result.splitlines() if ": ERROR in " in ln or ": FAILED after " in ln]
    return re.sub(r" in \d+\.\ds| after \d+\.\ds", "", " | ".join(lines))[:400]
