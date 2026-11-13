"""
Node catalog for the Workflow Builder.

Structural facts (node types, default data, handles) come from
``node_catalog.json``, which is generated from the canvas node registry by
``frontend/tests/views/AIAgents/Workflows/registry/builderNodeCatalog.test.ts``. Field metadata
(labels, select options, required flags) is merged in from the backend dialog
schemas. Only the usage notes below are hand-written.

Everything the builder agent is told about a node, and everything the validator
checks, is derived from here, so the agent, the validator and the canvas cannot
drift apart.
"""

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.dynamic_form_schemas.nodes import NODE_DIALOG_SCHEMAS

_CATALOG_PATH = Path(__file__).with_name("node_catalog.json")

ENTRY_NODE_TYPES = {"chatInputNode", "webhookTriggerNode"}
OUTPUT_NODE_TYPES = {"chatOutputNode"}
AGENT_NODE_TYPES = {"agentNode", "subAgentNode", "voiceAgentNode"}
# Nodes that attach to an agent instead of sitting in the main flow.
ATTACHMENT_SOURCE_HANDLES = {"output_tool", "output_sub_agent"}
ATTACHMENT_TARGET_HANDLES = {"input_tools", "input_sub_agents"}
SUBFLOW_SOURCE_HANDLE = "starter_processor"

# Never offered to the builder agent.
HIDDEN_NODE_TYPES = {"workflowBuilderToolsNode"}

# Keys the canvas stores on a node that are not configuration.
NON_CONFIG_KEYS = {"handlers", "label", "updateNodeData"}

# Config keys that are valid but appear in neither the canvas defaults nor the
# backend dialog schema (set by dialogs conditionally).
EXTRA_CONFIG_KEYS: Dict[str, set] = {
    "*": {"name", "deactivated"},
    "agentNode": {
        "providerId", "fallbackChainId", "maxMessages", "memoryTrimmingMode",
        "tokenBudget", "conversationHistoryTokens", "compactingThreshold",
        "compactingKeepRecent", "compactingModel", "compactingImportantEntities",
    },
    "subAgentNode": {
        "providerId", "fallbackChainId", "tokenBudget", "conversationHistoryTokens",
        "compactingThreshold", "compactingKeepRecent", "compactingModel",
        "compactingImportantEntities", "inputSchema",
    },
    "llmModelNode": {
        "providerId", "fallbackChainId", "maxMessages", "memoryTrimmingMode",
        "tokenBudget", "conversationHistoryTokens",
    },
    "toolBuilderNode": {"inputSchema", "returnDirect"},
    "pythonCodeNode": {"unwrap"},
    "dataMapperNode": {"mappings"},
    "zendeskTicketNode": {"app_settings_id", "custom_fields"},
    "slackMessageNode": {"app_settings_id"},
    "whatsappToolNode": {"app_settings_id"},
    "salesforceCaseNode": {"app_settings_id"},
    "jiraNode": {"app_settings_id"},
    "readMailsNode": {"dataSourceId"},
    "voiceAgentNode": {"providerId"},
}

# Fields the end user has to pick in the canvas (credentials, connections,
# resources). The builder leaves them empty; they are reported as setup steps
# rather than build errors.
SETUP_KEYS = {
    "providerId", "app_settings_id", "dataSourceId", "selectedBases", "modelId",
    "audioProviderId", "llm_provider_id", "apiToken", "authToken", "authPassword",
    "agentId",
}

SECRET_KEY_PATTERN = re.compile(r"(token|secret|password|api_?key)", re.IGNORECASE)

# Setup fields the builder can fill itself by looking the resource up.
LOOKUP_KEYS = {
    "selectedBases": "knowledge_bases",
    "app_settings_id": "integrations",
    "dataSourceId": "data_sources",
}

# Fields whose canvas default is example text. A node still holding it was never configured.
PLACEHOLDER_FIELDS: Dict[str, List[str]] = {
    "pythonCodeNode": ["code"],
    "dataMapperNode": ["pythonScript"],
    "templateNode": ["template"],
}

# Text fields that must not be empty for the node to do anything useful.
REQUIRED_CONFIG: Dict[str, List[str]] = {
    "agentNode": ["systemPrompt", "userPrompt"],
    "subAgentNode": ["systemPrompt", "description"],
    "llmModelNode": ["systemPrompt", "userPrompt"],
    "templateNode": ["template"],
    "routerNode": ["first_value", "second_value"],
    "filterNode": ["field"],
    "pythonCodeNode": ["code"],
    "knowledgeBaseNode": ["query"],
    "toolBuilderNode": ["description"],
    "slackMessageNode": ["message"],
    "webSearchNode": ["query"],
    "webScraperNode": ["url"],
    "apiToolNode": ["endpoint"],
}

# Hand-written usage notes: what the node is for and the wiring rules the
# schema alone does not convey.
NODE_NOTES: Dict[str, str] = {
    "chatInputNode": "Entry point of a chat workflow. Exactly one per workflow. Its inputSchema defines the session variables ({{session.message}} is always present).",
    "webhookTriggerNode": "Entry point for workflows started by an external HTTP request instead of a chat message.",
    "chatOutputNode": "Sends the reply to the user. Every branch of a chat workflow must end in its own Chat Output; branches are never merged into one output without an aggregatorNode.",
    "agentNode": "LLM agent that reasons, keeps memory and calls tools. Use type \"ReActAgentLC\". userPrompt is normally {{session.message}} (the user's message). Tools attach with add_tool; delegates attach as subAgentNode. providerId is filled in automatically. Its output is {\"message\": <the reply>, \"steps\": [...], \"tools_used\": [...]}: the next node reads the reply as {{source.message}} (in Python, params.get(\"source.message\")); there is no source.result or source.data. Memory is on by default; the builder turns it off for an agent whose reply goes to a code, switch, router or filter step, because a classifier must not be swayed by earlier messages.",
    "subAgentNode": "A focused agent a parent agentNode delegates to. It is not part of the main flow: connect it to the parent agent only (handles are inferred). description tells the parent when to delegate.",
    "llmModelNode": "A single LLM call without tools. Use it for classification, rewriting, translation, summarising. Its reply is plain text: the next node reads it as {{source}} (not {{source.message}}).",
    "templateNode": "Renders fixed text with variables. Use it for replies that must be worded exactly (refusals, confirmations, error messages) and for formatting a previous node's output. Every variable needs its full path, e.g. {{source.result.total}}, never a bare {{total}}. Its output is plain text: the next node reads it as {{source}}.",
    "routerNode": "Two-way branch (output_true / output_false) on a plain string comparison of first_value against second_value (both required). It cannot understand intent: put an llmModelNode classifier or a pythonCodeNode check before it and compare that node's output. The node after a router receives the routing decision, not the earlier data: read earlier results with {{node_outputs.<id>...}} or {{session.message}}.",
    "switchNode": "Multi-way branch. `cases` is a list of {label, value}; each case gets its own output handle (output_case_1, output_case_2, ...) plus output_default. Compares switchValue against each case value using matchMode. Prefer it over chains of routerNodes. The node after a switch receives the routing decision, not the earlier data: read earlier results with {{node_outputs.<id>...}} or {{session.message}}.",
    "filterNode": "A gate with one output: the flow continues only while `field` <operator> `value` holds, otherwise the run ends and stopMessage is returned to the user. `field` is a single text value (usually a classifier's or check's output), not a list. It does not filter items out of a list; use pythonCodeNode for that.",
    "aggregatorNode": "Merges several branches back into one. The only node whose input accepts more than one incoming connection. To rejoin branches of a router or switch (only one of them runs) set requireAllInputs to false and aggregationStrategy to \"merge\"; with requireAllInputs true it waits for every branch. Usually simpler: give each branch its own chatOutputNode.",
    "toolBuilderNode": "Wraps one node as a tool an agent can call. Do not add it directly: use add_tool, which creates it together with the wrapped node and both connections.",
    "knowledgeBaseNode": "Retrieves passages from the tenant's knowledge bases. Almost always used as an agent tool (add_tool). Set selectedBases to the ids of the knowledge bases to search: find them with list_resources(kind=\"knowledge_bases\"), matching the name the person gave. If they named none and several exist, ask which one.",
    "setStateNode": "Writes session variables that persist across turns. `states` is a list of {key, value}; read them later as {{session.key}}. Declare the key in the Chat Input inputSchema with stateful: true.",
    "pythonCodeNode": "Runs Python for exact logic an LLM should not be trusted with: validation, calculations, parsing, counting, formatting. The code must define `def executable_function(params):` and return a value. Inputs are read with params.get(\"<path>\"): the same dotted paths as variables, written as literal strings in the code (they are resolved before the code runs, so never build a path from other strings). Which path exists depends on the step before this one: after an agentNode or the chatInputNode the text is params.get(\"source.message\") (an agent's output is {\"message\": <reply>, \"steps\": [...], \"tools_used\": [...]}; it has no source.result or source.data); after an llmModelNode or templateNode the text is params.get(\"source\"); after another pythonCodeNode params.get(\"source.result\"); after an apiToolNode params.get(\"source.data\"). params.get(\"session.message\") and params.get(\"node_outputs.n3.message\") work anywhere. An agent's or model's reply is text even when it was asked for JSON: parse it with json.loads inside try/except and fall back to a safe default such as {\"category\": \"general\"}. The return value is available downstream as {{source.result}} (and its keys as {{source.result.<key>}} when it returns a dict). Always replace the whole placeholder code.",
    "dataMapperNode": "Reshapes the previous node's output with a Python script. Prefer pythonCodeNode for new logic.",
    "humanInTheLoopNode": "Pauses the run and shows the user a form (form_fields), then continues with the submitted values.",
    "apiToolNode": "Calls an HTTP endpoint (method, endpoint, headers, parameters as query string, requestBody). Variables work in every field, e.g. endpoint \"https://api.example.com/users/{{source.result.user_id}}/orders\". Its output is {status, data, headers}: read the body as {{source.data}} (in Python: params.get(\"source.data\")). Use it only when no dedicated integration node exists.",
    "mcpNode": "Exposes the tools of an MCP server to an agent. Connect it to the agent directly (handles are inferred); the user configures the server in the canvas.",
    "finalizeConversationNode": "Ends the conversation (marks it finalized). Place it before the Chat Output of a closing branch.",
    "workflowExecutorNode": "Runs another existing workflow as a step.",
    "webSearchNode": "Searches the web and returns results with content. Good as an agent tool.",
    "webScraperNode": "Fetches one web page as clean text/markdown. Good as an agent tool.",
}


def _dialog_fields(node_type: str) -> Dict[str, Any]:
    return {field.name: field for field in NODE_DIALOG_SCHEMAS.get(node_type) or []}


@lru_cache(maxsize=1)
def _load() -> Dict[str, Dict[str, Any]]:
    entries = json.loads(_CATALOG_PATH.read_text())
    return {entry["type"]: entry for entry in entries}


def all_node_types(include_hidden: bool = False) -> List[str]:
    return [t for t in _load() if include_hidden or t not in HIDDEN_NODE_TYPES]


def is_known(node_type: str) -> bool:
    return node_type in _load()


def entry(node_type: str) -> Optional[Dict[str, Any]]:
    return _load().get(node_type)


def label(node_type: str) -> str:
    found = entry(node_type)
    return found["label"] if found else node_type


def default_data(node_type: str) -> Dict[str, Any]:
    """A fresh copy of the data the canvas gives a new node of this type."""
    found = entry(node_type)
    if not found:
        raise KeyError(node_type)
    return deepcopy(found["defaultData"])


def _switch_handlers(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Mirrors buildSwitchHandlers in the canvas (nodeTypes/router/switchCases.ts).
    handlers: List[Dict[str, Any]] = [
        {"id": "input", "type": "target", "compatibility": "any", "position": "left"}
    ]
    for index, case in enumerate(data.get("cases") or []):
        if not isinstance(case, dict) or not case.get("id"):
            continue
        handlers.append({
            "id": f"output_{case['id']}",
            "type": "source",
            "compatibility": "any",
            "position": "right",
            "label": case.get("label") or f"Case {index + 1}",
        })
    handlers.append({
        "id": "output_default",
        "type": "source",
        "compatibility": "any",
        "position": "right",
        "label": "Default",
    })
    return handlers


_DYNAMIC_HANDLERS = {"switchNode": _switch_handlers}


def handlers_for(node_type: str, data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """The handles a node of this type has, given its config."""
    found = entry(node_type)
    if not found:
        return []
    derive = _DYNAMIC_HANDLERS.get(node_type)
    if derive:
        return derive(data if data is not None else found["defaultData"])
    return deepcopy(found["defaultData"].get("handlers") or [])


def handle_ids(node_type: str, data: Optional[Dict[str, Any]], kind: str) -> List[str]:
    return [h["id"] for h in handlers_for(node_type, data) if h.get("type") == kind]


def handle_compatibility(
    node_type: str, data: Optional[Dict[str, Any]], handle_id: str
) -> Optional[str]:
    for handler in handlers_for(node_type, data):
        if handler["id"] == handle_id:
            return handler.get("compatibility")
    return None


def allowed_config_keys(node_type: str) -> set:
    found = entry(node_type)
    if not found:
        return set()
    keys = set(found["defaultData"]) | set(_dialog_fields(node_type))
    keys |= EXTRA_CONFIG_KEYS["*"] | EXTRA_CONFIG_KEYS.get(node_type, set())
    return keys - NON_CONFIG_KEYS


def is_secret_key(key: str) -> bool:
    return bool(SECRET_KEY_PATTERN.search(key))


def config_fields(node_type: str) -> List[Dict[str, Any]]:
    """Config fields of a node: canvas defaults merged with dialog metadata."""
    found = entry(node_type)
    if not found:
        return []
    dialog = _dialog_fields(node_type)
    defaults = found["defaultData"]
    required = set(REQUIRED_CONFIG.get(node_type, []))

    fields: List[Dict[str, Any]] = []
    for key in sorted(allowed_config_keys(node_type) - {"deactivated"}):
        meta = dialog.get(key)
        field: Dict[str, Any] = {"name": key}
        if key in defaults:
            field["default"] = defaults[key]
        elif meta is not None and meta.default is not None:
            field["default"] = meta.default
        if meta is not None:
            if meta.options:
                field["options"] = [o.get("value") for o in meta.options if o.get("value") is not None]
            if meta.description:
                field["description"] = meta.description
            elif meta.label:
                field["description"] = meta.label
        if key in required:
            field["required"] = True
        if key in SETUP_KEYS:
            field["setup"] = True
        fields.append(field)
    return fields


def _short(value: Any, limit: int = 80) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else json.dumps(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe_handles(node_type: str, data: Optional[Dict[str, Any]] = None) -> str:
    inputs = handle_ids(node_type, data, "target")
    outputs = handle_ids(node_type, data, "source")
    return f"in: {', '.join(inputs) or '-'} | out: {', '.join(outputs) or '-'}"


def node_schema_text(node_type: str) -> str:
    """Everything the builder needs to configure one node type, as compact text."""
    found = entry(node_type)
    if not found or node_type in HIDDEN_NODE_TYPES:
        return unknown_type_message(node_type)

    lines = [f"{node_type} — {found['label']}", found["description"]]
    note = NODE_NOTES.get(node_type)
    if note:
        lines.append(f"Usage: {note}")
    lines.append(f"Handles ({describe_handles(node_type)})")
    if found.get("dynamicHandles"):
        lines.append("Handles depend on config; they are recomputed when the node is updated.")
    lines.append("Config:")
    for field in config_fields(node_type):
        if field["name"] == "name":
            continue
        parts = [f"- {field['name']}"]
        if field.get("required"):
            parts.append("(required)")
        if field.get("setup"):
            lookup = LOOKUP_KEYS.get(field["name"])
            if lookup:
                parts.append(f"(an id from list_resources(kind=\"{lookup}\"); leave unset if none fits)")
            elif field["name"] == "providerId":
                parts.append("(filled in automatically; leave unset)")
            else:
                parts.append("(chosen by the user in the canvas; leave unset)")
        if "default" in field and not field.get("setup"):
            parts.append(f"default {_short(field['default'])}")
        if field.get("options"):
            parts.append(f"one of {field['options']}")
        if field.get("description"):
            parts.append(f"— {field['description']}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def unknown_type_message(node_type: str) -> str:
    matches = search_nodes(node_type, limit=5)
    suggestion = ", ".join(m["type"] for m in matches) or "use search_nodes"
    return f"Unknown node type '{node_type}'. Closest: {suggestion}."


_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    # Split camelCase too, so "knowledgeBaseNode" matches "knowledge base".
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return _WORD.findall(spaced.lower())


def search_nodes(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Rank node types against a free-text query."""
    query_tokens = [t for t in _tokens(query or "") if t != "node"]
    if not query_tokens:
        return []

    scored = []
    for node_type, found in _load().items():
        if node_type in HIDDEN_NODE_TYPES:
            continue
        name_tokens = set(_tokens(node_type)) | set(_tokens(found["label"]))
        body_tokens = set(_tokens(found["description"])) | set(_tokens(NODE_NOTES.get(node_type, "")))
        body_tokens |= set(_tokens(found.get("category", "")))
        score = 0.0
        for token in query_tokens:
            if token in name_tokens:
                score += 3
            elif any(t.startswith(token) or token.startswith(t) for t in name_tokens if len(t) > 2):
                score += 2
            elif token in body_tokens:
                score += 1
        if score > 0:
            scored.append((score, node_type, found))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "type": node_type,
            "label": found["label"],
            "description": NODE_NOTES.get(node_type) or found["description"],
            "handles": describe_handles(node_type),
        }
        for _, node_type, found in scored[:limit]
    ]


def compact_index(names_only: bool = False) -> str:
    """
    Node types grouped by category. With ``names_only`` it is one line per
    category, for a system prompt that is paid for on every model call; the
    longer form (one described line per type) is for a search that found nothing.
    """
    by_category: Dict[str, List[str]] = {}
    for node_type, found in _load().items():
        if node_type in HIDDEN_NODE_TYPES:
            continue
        summary = found["description"].split(". ")[0].rstrip(".")
        by_category.setdefault(found.get("category", "other"), []).append(
            node_type if names_only else f"- {node_type}: {summary}"
        )
    lines: List[str] = []
    for category in sorted(by_category):
        if names_only:
            lines.append(f"{category}: {', '.join(sorted(by_category[category]))}")
        else:
            lines.append(f"[{category}]")
            lines.extend(sorted(by_category[category]))
    return "\n".join(lines)
