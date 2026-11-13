"""
Focused AI actions on a workflow: explain, improve a prompt, write code, suggest
tests, propose optimisations, review.

Each action is one model call with only the relevant part of the workflow in
context, so it costs a fraction of a builder turn (no tool loop, no agent
prefix). Actions that change the workflow return a proposal, an ``apply_plan``
operation list the canvas shows for approval and applies through
``apply_plan``; nothing here writes to the draft.

``review`` needs no model at all: it is the validator plus checks for the
mistakes real builder runs kept making (prompts that leak internals, unhandled
switch defaults, placeholders, nothing selected on a knowledge base).
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.modules.workflow.builder import catalog
from app.modules.workflow.builder.draft import WorkflowDraft
from app.modules.workflow.builder.patterns import STANDING_RULES
from app.modules.workflow.builder.validation import VISUAL_NODE_TYPES

logger = logging.getLogger(__name__)

PROMPT_NODE_TYPES = {"agentNode", "subAgentNode", "llmModelNode", "voiceAgentNode"}
CODE_FIELDS = {"pythonCodeNode": "code", "dataMapperNode": "pythonScript", "templateNode": "template"}
ACTION_NODE_TYPES = {
    "zendeskTicketNode", "slackMessageNode", "gmailNode", "whatsappToolNode",
    "salesforceCaseNode", "jiraNode", "calendarEventNode",
}

# Words in a customer-facing prompt that end up in replies ("it's not in my knowledge base").
LEAK_PATTERNS = [
    (re.compile(r"\bknowledge[- ]?base\b|\bKB\b", re.I), "names the knowledge base"),
    (re.compile(r"\b(my|the) (documents?|docs|tools?|instructions|prompt)\b", re.I), "refers to internal documents, tools or instructions"),
    (re.compile(r"\bnot (in|covered by|available in) (my|the|our) (knowledge|data|documents|docs)", re.I), "tells customers where information is missing from"),
]

ASSIST_SYSTEM = (
    "You help a person who builds AI workflows on a visual canvas and is not an engineer. "
    "You are given a compact outline of their workflow (nodes with ids like n3, settings, connections). "
    "Answer in plain language, concisely, in the person's language. Never mention node ids, node type "
    "names, JSON or tools by their internal names; describe steps as they appear on the canvas."
)


async def _chat_model(provider_id: Optional[str] = None):
    from app.dependencies.injector import injector
    from app.modules.workflow.llm.provider import LLMProvider
    from app.services.llm_providers import LlmProviderService

    if not provider_id:
        provider_id = str((await injector.get(LlmProviderService).get_default()).id)
    return await injector.get(LLMProvider).get_model(provider_id)


async def _ask(system: str, user: str, provider_id: Optional[str] = None) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = await _chat_model(provider_id)
    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    content = response.content
    if isinstance(content, list):
        content = "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )
    return str(content).strip()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _parse_json(text: str) -> Any:
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"[\[{].*[\]}]", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _node_context(draft: WorkflowDraft, node_ids: List[str]) -> str:
    return "\n\n".join(draft.render_node(draft.alias(node_id)) for node_id in node_ids)


def _names(draft: WorkflowDraft, node_ids: List[str]) -> str:
    return ", ".join(f"\"{(draft.find(i).get('data') or {}).get('name', '')}\"" for i in node_ids)


# ── Read-only explanations ─────────────────────────────────────────────────


async def explain_node(draft: WorkflowDraft, node_id: str) -> str:
    node = draft.find(node_id)
    user = (
        f"Workflow outline:\n{draft.render_outline()}\n\nThe step to explain, in full:\n"
        f"{draft.render_node(draft.alias(node['id']))}\n\n"
        "Explain this step in at most six short sentences: what it does, what it receives and from "
        "where, what it produces and which steps use that, and anything that looks incomplete or risky."
    )
    return await _ask(ASSIST_SYSTEM, user)


async def explain_group(draft: WorkflowDraft, node_ids: List[str]) -> str:
    user = (
        f"Workflow outline:\n{draft.render_outline()}\n\nThe steps to explain together: {_names(draft, node_ids)}.\n"
        f"Their details:\n{_node_context(draft, node_ids)}\n\n"
        "Explain what these steps do together as one short paragraph, then the path a message takes "
        "through them, then anything incomplete or risky. At most ten sentences."
    )
    return await _ask(ASSIST_SYSTEM, user)


async def describe_workflow(draft: WorkflowDraft) -> str:
    user = (
        f"Workflow outline:\n{draft.render_outline()}\n\n"
        "Describe this workflow for someone who has never seen it: what it is for, the paths a message "
        "can take, which external systems and knowledge it uses, and what still needs to be set up. "
        "Under 120 words, plain language, no step ids."
    )
    return await _ask(ASSIST_SYSTEM, user)


async def explain_step(draft: WorkflowDraft, node_id: str, run_report: str) -> str:
    node = draft.find(node_id)
    if not run_report:
        return "There is no test run to explain yet. Run the workflow from the Executions tab first."
    user = (
        f"Workflow outline:\n{draft.render_outline()}\n\nThe step in question:\n"
        f"{draft.render_node(draft.alias(node['id']))}\n\nThe test run:\n{run_report}\n\n"
        "Explain why this step ran (or did not run) in that test, what it received, why its output "
        "looks the way it does, and, if it failed, the exact cause as the error states it. "
        "At most eight sentences; quote the error as it is."
    )
    return await _ask(ASSIST_SYSTEM, user)


# ── Proposals (the canvas applies them through apply_plan) ─────────────────


def _proposal(title: str, why: str, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"title": title, "why": why, "operations": operations}


async def improve_prompt(draft: WorkflowDraft, node_id: str, instruction: str = "") -> Dict[str, Any]:
    node = draft.find(node_id)
    if node.get("type") not in PROMPT_NODE_TYPES:
        raise ValueError("This step has no system prompt to improve.")
    current = (node.get("data") or {}).get("systemPrompt") or ""
    tools = [
        (draft.find(e["source"]).get("data") or {}).get("description", "")
        for e in draft.edges if e["target"] == node["id"] and e.get("targetHandle") == "input_tools"
    ]
    user = (
        f"Rewrite the system prompt of the step \"{(node.get('data') or {}).get('name', '')}\" "
        f"({'an agent with tools' if tools else 'a model step'}).\n\nCurrent prompt:\n{current or '(empty)'}\n\n"
        + (f"Its tools (by description): {tools}\n\n" if tools else "")
        + (f"The person asked: {instruction}\n\n" if instruction else "")
        + "Keep every rule and fact the current prompt states. Make it a real brief: who the agent "
        "serves and for whom, what it must accomplish, when to use each tool, what to do when it cannot "
        "help, tone. Add these standing rules in your own words if they are missing:\n"
        f"{STANDING_RULES}\n"
        "Remove internal names (of knowledge bases, tools, files) and replace them with their purpose. "
        "Reply with the new prompt only, no preamble, no code fences."
    )
    text = _strip_fences(await _ask(
        "You write system prompts for customer-facing AI agents. You reply with the prompt text only.", user
    ))
    return _proposal(
        "Improved system prompt",
        "Rewritten as a full brief with the standing rules; internal names replaced by purpose.",
        [{"op": "set_node_field", "node_id": draft.alias(node["id"]), "field": "systemPrompt", "value": text}],
    )


async def generate_code(draft: WorkflowDraft, node_id: str, instruction: str) -> Dict[str, Any]:
    node = draft.find(node_id)
    field = CODE_FIELDS.get(node.get("type", ""))
    if not field:
        raise ValueError("This step has no code or template to generate.")
    if not instruction.strip():
        raise ValueError("Describe what the step should do.")
    upstream = [draft.alias(e["source"]) for e in draft.edges if e["target"] == node["id"]]
    context = _node_context(draft, [draft.find(a)["id"] for a in upstream]) if upstream else "(no step before it)"
    if field == "template":
        task = (
            "Write the template text. Variables are written {{source...}}, {{session.message}} or "
            "{{node_outputs.<id>...}} with the full path to the value (a previous Python step's result is "
            "{{source.result.<key>}}; a model step's reply is {{source}}). Reply with the template only."
        )
    else:
        task = (
            "Write Python that defines `def executable_function(params):` and returns the result "
            "(a dict when there are several values). Read inputs with params.get(\"session.message\"), "
            "params.get(\"source.data\") (an API body), params.get(\"source.result\") (a previous Python "
            "step), params.get(\"node_outputs.<id>.result\"). Handle missing or malformed input without "
            "raising. No network, no files. Reply with the code only."
        )
    user = (
        f"Step: \"{(node.get('data') or {}).get('name', '')}\" ({catalog.label(node['type'])}).\n"
        f"What the person wants it to do: {instruction}\n\nThe step(s) feeding it:\n{context}\n\n{task}"
    )
    text = _strip_fences(await _ask("You write small, robust pieces of workflow logic. Reply with code or text only.", user))
    if field != "template":
        # Same check the builder's own writes go through; a syntax error is refused here, not at run time.
        text = WorkflowDraft._clean_code(node["type"], field, text)
    return _proposal(
        f"Generated {field}",
        f"Written from: {instruction[:120]}",
        [{"op": "set_node_field", "node_id": draft.alias(node["id"]), "field": field, "value": text}],
    )


async def suggest_tests(draft: WorkflowDraft, node_id: Optional[str] = None) -> List[str]:
    focus = f"Focus on the step {draft.render_node(draft.alias(draft.find(node_id)['id']))}\n\n" if node_id else ""
    user = (
        f"Workflow outline:\n{draft.render_outline()}\n\n{focus}"
        "Write test messages a real user of this workflow would send, so that together they exercise "
        "every branch, every tool and the refusal or error paths. One message per line, written "
        "naturally, 3 to 6 messages. Reply with a JSON array of strings only."
    )
    text = await _ask(ASSIST_SYSTEM, user)
    try:
        parsed = _parse_json(text)
        return [str(m) for m in parsed if str(m).strip()][:8]
    except Exception:
        return [line.strip("-• ").strip() for line in text.splitlines() if line.strip()][:8]


OPTIMIZE_SYSTEM = (
    "You review AI workflows built on a canvas and propose structural improvements as apply_plan "
    "operations. Operations: {\"op\":\"add_node\",\"id\":\"$x\",\"node_type\",\"name\",\"system_prompt\"?,"
    "\"config\"?,\"connect_from\"?,\"connect_to\"?}, {\"op\":\"add_tool\",\"id\":\"$x\",\"agent_id\",\"node_type\","
    "\"name\",\"description\",\"config\"?,\"parameters\"?}, {\"op\":\"set_node_field\",\"node_id\",\"field\",\"value\"}, "
    "{\"op\":\"update_node\",\"node_id\",\"config\"?,\"name\"?}, {\"op\":\"connect\",\"source\",\"target\"}, "
    "{\"op\":\"disconnect\",\"source\",\"target\"}, {\"op\":\"remove_node\",\"node_id\"}. "
    "Existing nodes are referenced by their ids (n3); new ones by \"$name\". Branching nodes need the "
    "output named: \"n3.output_true\", \"n3.output_case_1\". Node types you may use: " + ", ".join(
        t for t in catalog.all_node_types()
    )
)


async def optimize(draft: WorkflowDraft, node_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    scope = f"Only the steps {_names(draft, node_ids)} and their immediate surroundings:\n{_node_context(draft, node_ids)}\n\n" if node_ids else ""
    user = (
        f"Workflow outline:\n{draft.render_outline()}\n\n{scope}"
        "Look for: a rule written in a prompt that a node should enforce (topic limits -> model step + "
        "filter; cases -> model step + switch; exact conditions -> Python + router); one output wired to "
        "several steps that both run; an agent in the middle of an exact procedure; a switch without a "
        "default branch; a branch that never reaches an output; a prompt that names internal things; a "
        "tool without a clear description; counting or list work asked of a model. Propose at most four "
        "improvements, each small and independent. Reply with a JSON array of "
        "{\"title\": string, \"why\": string, \"operations\": [...]} only; an empty array if nothing is worth changing."
    )
    text = await _ask(OPTIMIZE_SYSTEM, user)
    try:
        parsed = _parse_json(text)
    except Exception:
        logger.warning("optimize: model reply was not JSON: %s", text[:200])
        return []
    proposals = []
    for item in parsed if isinstance(parsed, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("operations"), list):
            continue
        proposals.append(_proposal(str(item.get("title") or "Improvement"), str(item.get("why") or ""), item["operations"]))
    return proposals[:4]


ADD_STEP_SYSTEM = (
    "You add one step to an AI workflow built on a canvas, for a person who is not an engineer. "
    "Reply with one JSON object only, an add_node operation: {\"op\":\"add_node\",\"id\":\"$new\","
    "\"node_type\":string,\"name\":string,\"system_prompt\"?:string,\"config\"?:object,\"connect_to\"?:string}. "
    "Choose the one node type that does what is asked. A language model step (llmModelNode, brief in "
    "system_prompt, replies plain text) understands or writes text; an agentNode holds a conversation "
    "and uses tools; pythonCodeNode handles exact data (code defines executable_function(params)); "
    "templateNode is fixed text (config {\"template\": ...}, variables as {{source}}); chatOutputNode "
    "sends the reply to the user; switchNode routes on a value. Give the step a short name as it "
    "will appear on the canvas and sensible settings; a prompt is a full brief. Node types, by "
    "category:\n" + catalog.compact_index()
)


async def add_step(
    draft: WorkflowDraft, source_node_id: str, source_handle: Optional[str], instruction: str
) -> Dict[str, Any]:
    """
    One new step after a given output of a step, from a sentence. The result is a
    proposal the canvas applies at once; the new step is connected from that output
    and, when it belongs in between, to what the output already led to.
    """
    if not instruction.strip():
        raise ValueError("Describe what the new step should do.")
    node = draft.find(source_node_id)
    data = node.get("data") or {}
    alias = draft.alias(node["id"])
    outputs = catalog.handle_ids(node["type"], data, "source")
    handle = (source_handle or "").strip() or (outputs[0] if outputs else "output")
    if outputs and handle not in outputs:
        raise ValueError(f"\"{data.get('name', '')}\" has no output \"{handle}\".")
    label = next(
        (h.get("label") for h in catalog.handlers_for(node["type"], data) if h.get("id") == handle), None
    ) or handle.replace("output_", "").replace("_", " ")
    downstream = [
        e["target"] for e in draft.edges
        if e["source"] == node["id"] and (e.get("sourceHandle") or (outputs[0] if outputs else "output")) == handle
    ]
    downstream_aliases = {draft.alias(t): t for t in downstream}
    leads_to = (
        f"That output currently leads to {_names(draft, downstream)} ({', '.join(downstream_aliases)}). "
        "If the new step belongs between them, set connect_to to that step's id; if it is a new branch "
        "that replies on its own, leave connect_to out.\n\n"
        if downstream
        else "That output leads nowhere yet.\n\n"
    )
    user = (
        f"Workflow outline:\n{draft.render_outline()}\n\n"
        f"The step it comes after, in full:\n{draft.render_node(alias)}\n\n"
        f"The new step follows \"{data.get('name', '')}\" from its output \"{label}\". {leads_to}"
        f"What the person wants the new step to do: {instruction.strip()}\n\n"
        "Reply with the add_node object only."
    )
    text = await _ask(ADD_STEP_SYSTEM, user)
    try:
        parsed = _parse_json(text)
    except Exception:
        raise ValueError("I could not work out a step for that. Try describing it differently.")
    if isinstance(parsed, list):
        parsed = next((item for item in parsed if isinstance(item, dict)), None)
    if not isinstance(parsed, dict) or not catalog.is_known(str(parsed.get("node_type") or "")):
        raise ValueError("I could not work out a step for that. Try describing it differently.")
    name = " ".join(str(parsed.get("name") or catalog.label(parsed["node_type"])).split())[:60]
    operation: Dict[str, Any] = {
        "op": "add_node",
        "id": "$new",
        "node_type": parsed["node_type"],
        "name": name,
        "connect_from": f"{alias}.{handle}" if outputs and len(outputs) > 1 else alias,
    }
    if isinstance(parsed.get("system_prompt"), str) and parsed["system_prompt"].strip():
        operation["system_prompt"] = parsed["system_prompt"]
    if isinstance(parsed.get("config"), dict):
        operation["config"] = parsed["config"]
    connect_to = str(parsed.get("connect_to") or "").strip()
    if connect_to in downstream_aliases:
        operation["connect_to"] = connect_to
    return _proposal(f"Add \"{name}\"", f"After \"{data.get('name', '')}\": {instruction.strip()[:120]}", [operation])


# ── Review: deterministic checks, each with a fix the canvas can request ──


def review(draft: WorkflowDraft) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    for issue in draft.issues():
        findings.append({
            "severity": issue.severity,
            "code": issue.code,
            "node_id": issue.node_id,
            "message": draft._with_aliases(issue.message),
            "fix": f"Fix this: {draft._with_aliases(issue.message)}" if issue.severity != "setup" else None,
        })

    for node in draft.nodes:
        node_type = node.get("type", "")
        data = node.get("data") or {}
        if node_type in VISUAL_NODE_TYPES:
            continue
        if node_type in PROMPT_NODE_TYPES:
            prompt = str(data.get("systemPrompt") or "")
            for pattern, what in LEAK_PATTERNS:
                if pattern.search(prompt):
                    findings.append({
                        "severity": "warning", "code": "prompt_leak", "node_id": node["id"],
                        "message": f"The prompt of \"{data.get('name', '')}\" {what}; customers will hear it in replies.",
                        "fix": f"Rewrite the system prompt of \"{data.get('name', '')}\" so it never mentions internal things; describe them by purpose.",
                    })
                    break
            if node_type != "llmModelNode" and len(prompt.strip()) < 200:
                findings.append({
                    "severity": "warning", "code": "thin_prompt", "node_id": node["id"],
                    "message": f"The prompt of \"{data.get('name', '')}\" is very short; the agent has little to go on.",
                    "fix": f"Improve the system prompt of \"{data.get('name', '')}\" into a full brief.",
                })
        if node_type == "switchNode":
            used = {e.get("sourceHandle") for e in draft.edges if e["source"] == node["id"]}
            if "output_default" not in used:
                findings.append({
                    "severity": "warning", "code": "switch_no_default", "node_id": node["id"],
                    "message": f"The switch \"{data.get('name', '')}\" has no branch for messages that match no case.",
                    "fix": f"Add a default branch to \"{data.get('name', '')}\" that replies to the user.",
                })
        if node_type == "toolBuilderNode" and len(str(data.get("description") or "")) < 40:
            findings.append({
                "severity": "warning", "code": "thin_tool_description", "node_id": node["id"],
                "message": f"The tool \"{data.get('name', '')}\" has a very short description; the agent cannot tell when to use it.",
                "fix": f"Write a clear description for the tool \"{data.get('name', '')}\": when to call it and what it returns.",
            })

    order = {"error": 0, "warning": 1, "setup": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 3))
    return findings


# ── Dispatch ───────────────────────────────────────────────────────────────

READ_ACTIONS = {"explain_node", "explain_group", "describe_workflow", "explain_step", "suggest_tests", "review"}
PROPOSAL_ACTIONS = {"improve_prompt", "generate_code", "optimize", "add_step"}
ACTIONS = READ_ACTIONS | PROPOSAL_ACTIONS


async def run_action(
    draft: WorkflowDraft,
    action: str,
    node_ids: Optional[List[str]] = None,
    instruction: str = "",
    source_handle: Optional[str] = None,
) -> Dict[str, Any]:
    node_ids = [n for n in (node_ids or []) if n]
    first = node_ids[0] if node_ids else None
    if action == "explain_node":
        return {"kind": "text", "text": await explain_node(draft, first)}
    if action == "explain_group":
        return {"kind": "text", "text": await explain_group(draft, node_ids)}
    if action == "describe_workflow":
        return {"kind": "text", "text": await describe_workflow(draft)}
    if action == "explain_step":
        return {"kind": "text", "text": await explain_step(draft, first, draft.last_user_test)}
    if action == "suggest_tests":
        return {"kind": "messages", "messages": await suggest_tests(draft, first)}
    if action == "review":
        return {"kind": "review", "findings": review(draft)}
    if action == "improve_prompt":
        return {"kind": "proposals", "proposals": [await improve_prompt(draft, first, instruction)]}
    if action == "generate_code":
        return {"kind": "proposals", "proposals": [await generate_code(draft, first, instruction)]}
    if action == "optimize":
        return {"kind": "proposals", "proposals": await optimize(draft, node_ids or None)}
    if action == "add_step":
        return {"kind": "proposals", "proposals": [await add_step(draft, first, source_handle, instruction)]}
    raise ValueError(f"Unknown action '{action}'. Use one of: {', '.join(sorted(ACTIONS))}.")
