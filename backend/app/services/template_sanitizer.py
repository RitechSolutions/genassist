"""Sanitize & validate workflow graphs for the Template Marketplace.

GenAssist is database-per-tenant, so a template's node graph must never carry
values that only make sense in the source tenant:

* **Per-tenant references** (LLM provider / fallback chain / knowledge base /
  datasource / configuration var / ML model / workflow / agent / audio provider
  IDs) point at rows in another tenant's database and are blanked, so the
  installing user re-selects their own via the Setup Wizard.
* **Uploaded files** and the data previews made from them belong to the source
  tenant and are dropped.
* **Secrets** (inline auth tokens, MCP connection config, encrypted hidden
  Chat-Input defaults) must never travel inside a template and are stripped.

These helpers run when a template is saved (so stored graphs are always clean)
and again defensively on install.
"""
from __future__ import annotations

import copy
import logging
import re
from typing import Any, List, Optional, Tuple

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

logger = logging.getLogger(__name__)

# node.data fields that reference rows in the *source* tenant's DB, on any block.
# Covers every reference key in the builder's workflowReferences.ts.
PER_TENANT_REF_FIELDS = (
    "providerId",
    "fallbackChainId",
    "compactingModel",
    "llm_provider_id",
    "selectedBases",
    "audioProviderId",
    "voiceProviderId",
    "dataSourceId",
    "app_settings_id",
    "modelId",
    "workflowId",
    "agentId",
    "agent_id",
    "fixedThreadId",
    "fixed_thread_id",
)

# Uploaded files and the previews made from them (sample rows included).
UPLOADED_FILE_FIELDS = (
    "fileName",
    "filePath",
    "fileUrl",
    "fileId",
    "csvFileName",
    "csvFilePath",
    "csvFileUrl",
    "csvFileId",
    "originalFileName",
    "serverFilePath",
    "serverFileUrl",
    "analyzedFileUrl",
    "analysisResult",
    "stepAnalysisResults",
    "attachments",
)

# Values that describe the publisher's own objects, accounts or data, by block type.
PUBLISHER_ONLY_FIELDS = {
    "mlModelInferenceNode": ("modelName",),
    "workflowExecutorNode": ("workflowName",),
    "jiraNode": ("url", "email"),
    "mcpNode": ("availableTools", "whitelistedTools"),
    "webhookTriggerNode": ("samplePayload",),
}

# node.data fields that may hold plaintext secrets — must never live in a template.
# ``headers`` is a free-form JSON-object field (e.g. on webScraperNode) that
# commonly carries Authorization tokens, cookies, or API keys.
SECRET_DATA_FIELDS = (
    "authToken",
    "authPassword",
    "authUsername",
    "authHeader",
    "connectionConfig",
    "headers",
)

# Defense-in-depth: any node.data (or testInput) key whose name *contains* one
# of these substrings (case-insensitive) is stripped at any depth (unless its
# value is only a {{variable}}), even if it isn't in the curated
# SECRET_DATA_FIELDS list above. This catches
# secret-bearing fields on node types added later whose author forgot to extend
# SECRET_DATA_FIELDS. Kept deliberately narrow (no bare "key"/"auth") so
# ordinary config fields like ``publicKey`` or ``endpoint`` are never dropped
# by accident.
SECRET_KEY_SUBSTRINGS = (
    "token",
    "secret",
    "password",
    "passwd",
    "apikey",
    "api_key",
    "api-key",
    "credential",
    "private_key",
    "privatekey",
    "access_key",
    "accesskey",
    "authorization",
    "cookie",
    "bearer",
    "pwd",
    "jwt",
    "passphrase",
)

# Names that are secret only on their own: "auth" inside authType or authorUrl is not.
SECRET_KEY_NAMES = ("auth",)

# "token" also names counts and limits, such as maxOutputTokens or tokenBudget.
# Only these words make "tokens" a count, so apiTokens or refresh_tokens stay secret.
_TOKEN_COUNT_WORDS = frozenset(
    ("max", "min", "total", "num", "history", "context", "prompt", "completion", "input", "output", "reasoning", "thinking")
)
_TOKEN_LIMIT_WORDS = ("budget", "limit", "count")

# Maps keyed by field name: a secret-looking name keeps its field but not its default.
_FIELD_NAME_MAPS = ("inputSchema", "outputSchema")

# Fields that name a list entry in key/value lists, as in Set State or webhook field mappings.
_ENTRY_NAME_KEYS = ("key", "name", "header")


def _key_words(key: str) -> List[str]:
    # maxOutputTokens and max_output_tokens both give ["max", "output", "tokens"].
    return re.findall(r"[a-z0-9]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).lower())


def _is_token_count(words: List[str], i: int) -> bool:
    word = words[i]
    # tokenizer, tokenbudget
    if word.startswith("tokeniz") or (word.startswith("token") and word[len("token"):] in _TOKEN_LIMIT_WORDS):
        return True
    # token_budget, tokenLimit
    if word == "token":
        return i + 1 < len(words) and words[i + 1] in _TOKEN_LIMIT_WORDS
    # maxOutputTokens, max_tokens, maxtokens: a count word right before "tokens"
    if word.endswith("tokens"):
        return (word[: -len("tokens")] or (words[i - 1] if i else "")) in _TOKEN_COUNT_WORDS
    return False


def _is_secret_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    if lowered in SECRET_KEY_NAMES or any(sub in lowered for sub in SECRET_KEY_SUBSTRINGS if sub != "token"):
        return True
    words = _key_words(key)
    return any("token" in word and not _is_token_count(words, i) for i, word in enumerate(words))


# The workflow engine's variable syntax: {{name}} with no spaces inside the braces.
_WHOLE_VARIABLE = re.compile(r"\s*\{\{[^\s{}]+\}\}\s*")


def _is_whole_variable(value: Any) -> bool:
    # A value that is only a {{variable}} is filled in at run time, so it holds nothing from the source tenant.
    return isinstance(value, str) and _WHOLE_VARIABLE.fullmatch(value) is not None


def _is_secret_item(key: Any, item: Any) -> bool:
    if _is_whole_variable(item):
        return False
    # An "auth" block is walked like any other config; only a bare "auth" value is a secret.
    if isinstance(item, (dict, list)) and isinstance(key, str) and key.lower() in SECRET_KEY_NAMES:
        return False
    return _is_secret_key(key)


def _without_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _clean_field_map(item) if key in _FIELD_NAME_MAPS else _without_secrets(item)
            for key, item in value.items()
            if not _is_secret_item(key, item)
        }
    if isinstance(value, list):
        return [_without_entry_secret(_without_secrets(item)) for item in value]
    return value


def _without_entry_secret(entry: Any) -> Any:
    # A list entry named like a secret keeps its place but not its value or default.
    if not isinstance(entry, dict) or not any(_is_secret_key(entry.get(name)) for name in _ENTRY_NAME_KEYS):
        return entry
    if "value" in entry and not _is_whole_variable(entry["value"]):
        entry["value"] = "" if isinstance(entry["value"], str) else _blank(entry["value"])
    for field in ("default", "defaultValue"):
        if field in entry and not _is_whole_variable(entry[field]):
            del entry[field]
    return entry


def _clean_field_map(fields: Any) -> Any:
    if not isinstance(fields, dict):
        return _without_secrets(fields)
    cleaned = {}
    for name, schema in fields.items():
        schema = _without_secrets(schema)
        # Hidden Chat-Input defaults are encrypted secrets on read.
        if isinstance(schema, dict) and (schema.get("hidden") or _is_secret_key(name)):
            schema.pop("defaultValue", None)
        cleaned[name] = schema
    return cleaned


def _blank(value: Any) -> Any:
    if isinstance(value, list):
        return []
    if isinstance(value, dict):
        return {}
    return None


def sanitize_graph(
    nodes: Optional[List[dict]],
    edges: Optional[List[dict]],
) -> Tuple[List[dict], List[dict]]:
    """Return a deep-copied (nodes, edges) safe to store and share across tenants."""
    safe_nodes: List[dict] = copy.deepcopy(nodes or [])
    safe_edges: List[dict] = copy.deepcopy(edges or [])

    for node in safe_nodes:
        data = node.get("data") if isinstance(node, dict) else None
        if not isinstance(data, dict):
            continue

        # 1. Blank per-tenant references (forces re-selection via the Setup Wizard).
        for field in PER_TENANT_REF_FIELDS:
            if field in data and not _is_whole_variable(data[field]):
                data[field] = _blank(data[field])

        # 2. Drop uploaded files, their previews and the publisher's own values.
        for field in UPLOADED_FILE_FIELDS:
            if field not in data:
                continue
            value = data[field]
            if isinstance(value, list):
                # Only {{variables}} stay, such as attachments forwarded from the chat.
                variables = [item for item in value if _is_whole_variable(item)]
                if variables:
                    data[field] = variables
                    continue
            elif _is_whole_variable(value):
                continue
            del data[field]
        for field in PUBLISHER_ONLY_FIELDS.get(node.get("type"), ()):
            if field in data and not _is_whole_variable(data[field]):
                del data[field]

        # 3. Strip inline secrets (curated field names).
        for field in SECRET_DATA_FIELDS:
            data.pop(field, None)

        # 3b. Strip any other secret-looking field name at any depth (defense-in-depth).
        node["data"] = _without_secrets(data)

    return safe_nodes, [_without_secrets(edge) for edge in safe_edges]


def sanitize_test_input(
    nodes: Optional[List[dict]],
    test_input: Optional[dict],
) -> Optional[dict]:
    """Return a shareable copy of ``testInput``, or ``None``.

    ``testInput`` is the workflow's saved sample-run payload, keyed by Chat-Input
    field name (e.g. ``{"message": "hi", "apiKey": "sk-..."}``). A value typed
    into a *hidden* field — or any secret-looking key — is a per-tenant secret/PII
    and must never travel inside a shared template. ``sanitize_graph`` already
    blanks a hidden field's schema ``defaultValue``; this strips the matching
    ``testInput`` value so the two stay in sync. Visible, non-secret sample values
    are kept so the gallery's "try it" panel stays pre-filled.

    ``nodes`` should be the (already sanitized) graph nodes — they still carry the
    ``hidden`` flag in ``inputSchema``, which is what we key off here.
    """
    if not isinstance(test_input, dict):
        return None

    hidden_fields: set[str] = set()
    for node in nodes or []:
        data = node.get("data") if isinstance(node, dict) else None
        if not isinstance(data, dict):
            continue
        input_schema = data.get("inputSchema")
        if isinstance(input_schema, dict):
            for field_name, field_schema in input_schema.items():
                if isinstance(field_schema, dict) and field_schema.get("hidden"):
                    hidden_fields.add(field_name)

    safe: dict = {}
    for key, value in test_input.items():
        if key in hidden_fields or _is_secret_key(key):
            continue
        safe[key] = _without_secrets(value)
    return safe or None


def sanitize_template_graph(graph: Optional[dict]) -> dict:
    """Return a clean copy of a template graph: nodes, edges and any ``testInput``."""
    graph = graph if isinstance(graph, dict) else {}
    nodes, edges = sanitize_graph(graph.get("nodes"), graph.get("edges"))
    clean: dict = {"nodes": nodes, "edges": edges}
    test_input = sanitize_test_input(nodes, graph.get("testInput"))
    if test_input is not None:
        clean["testInput"] = test_input
    return clean


def _valid_node_types() -> set[str]:
    # Lazy import: routes import services, so importing the workflows route at
    # module load could create a cycle. By install time everything is loaded.
    from app.api.v1.routes.workflows import SUPPORTED_NODE_TYPES

    return set(SUPPORTED_NODE_TYPES)


def validate_node_types(nodes: Optional[List[dict]]) -> None:
    """Raise AppException(400) if the graph uses any unsupported node type."""
    valid = _valid_node_types()
    unknown = sorted(
        {
            n.get("type")
            for n in (nodes or [])
            if isinstance(n, dict) and n.get("type") not in valid
        }
        - {None}
    )
    if unknown:
        raise AppException(
            error_key=ErrorKey.TEMPLATE_INVALID,
            status_code=400,
            error_detail=f"Template uses unsupported node types: {', '.join(unknown)}",
        )
