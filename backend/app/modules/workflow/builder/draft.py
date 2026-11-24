"""
The Workflow Builder's working copy of a workflow.

A draft holds the real workflow (React Flow nodes and edges, exactly what the
canvas stores) plus the bookkeeping the builder agent needs: short node aliases
(n1, n2, ...), which issues were already present before the agent touched
anything, and a log of what changed this turn.

The agent never sees or writes the stored JSON. It reads the draft as a compact
outline (``render_outline``) and changes it through the operations below, each
of which is checked against the node catalog before it is applied.
"""

import ast
import json
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from app.modules.workflow.builder import catalog
from app.modules.workflow.builder.layout import auto_layout, place_new_nodes
from app.modules.workflow.builder.validation import (
    ERROR,
    Issue,
    VISUAL_NODE_TYPES,
    blocking,
    invalid_config_keys,
    is_subflow_edge,
    validate_workflow,
    VARIABLE_ROOTS,
)

DRAFT_METADATA_KEY = "workflow_builder_draft"

STATUS_DRAFT = "draft"
STATUS_READY = "ready"
# ask_user: how many answers a question may offer, and how long each may be.
MAX_OPTIONS = 4
MAX_OPTION_CHARS = 80

ORIGIN_NEW = "new"
ORIGIN_CANVAS = "canvas"

# What the builder writes into a new node on top of the canvas defaults.
BUILDER_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "agentNode": {"type": "ReActAgentLC", "memory": True, "userPrompt": "{{session.message}}"},
    "subAgentNode": {"type": "ReActAgentLC"},
    "templateNode": {"template": ""},
}

# Node types whose providerId is filled with the tenant's default LLM provider.
PROVIDER_NODE_TYPES = {"agentNode", "subAgentNode", "llmModelNode", "nlpNode"}

# Steps that parse or compare the reply they receive instead of showing it to a person.
PARSING_NODE_TYPES = {"pythonCodeNode", "dataMapperNode", "switchNode", "routerNode", "filterNode"}

# Tool Builder plumbing the agent never writes by hand (add_tool generates it);
# the outline shows the tool's parameter names instead.
TOOL_PLUMBING_KEYS = {"forwardTemplate", "inputSchema"}

SECRET_PLACEHOLDER = "<secret>"
OUTLINE_STRING_LIMIT = 140
OUTLINE_PREVIEW = 70
NODE_DETAIL_STRING_LIMIT = 6000

EDGE_STYLE = {"strokeWidth": 2, "stroke": "hsl(var(--brand-600))", "strokeDasharray": "7,7"}
EDGE_MARKER = {"type": "arrowclosed", "width": 16, "height": 16, "color": "hsl(var(--brand-600))"}

_NODE_OUTPUT_REF = re.compile(r"(\{\{\s*node_outputs\.)([^.}\s]+)")


class DraftError(Exception):
    """An operation the agent asked for cannot be applied; the message says why."""


def make_edge(source: str, target: str, source_handle: str, target_handle: str) -> Dict[str, Any]:
    return {
        "id": f"reactflow__edge-{source}{source_handle}-{target}{target_handle}",
        "source": source,
        "target": target,
        "sourceHandle": source_handle,
        "targetHandle": target_handle,
        "type": "default",
        "style": dict(EDGE_STYLE),
        "markerEnd": dict(EDGE_MARKER),
    }


def _starter_workflow_values() -> Dict[str, Dict[str, Any]]:
    """
    Per node type, the data the backend gives a brand-new agent's workflow
    (app.schemas.workflow.get_base_workflow). Those values are placeholders, not
    the person's work, even where they differ from the canvas defaults.
    """
    try:
        from app.schemas.workflow import get_base_workflow

        nodes = get_base_workflow("starter").nodes or []
    except Exception:  # the check must never break a turn
        return {}
    values: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        node = node if isinstance(node, dict) else getattr(node, "model_dump", lambda: {})()
        data = node.get("data") or {}
        values.setdefault(node.get("type", ""), {}).update(
            {k: v for k, v in data.items() if k not in catalog.NON_CONFIG_KEYS}
        )
    return values


_KNOWLEDGE_BASE_ALIASES = (
    "knowledgeBaseId", "knowledgeBaseIds", "knowledge_base_id", "knowledge_base_ids",
    "knowledgeBase", "knowledgeBases", "knowledge_bases", "selectedBase", "baseId", "kb_id",
)


def _alias_knowledge_base_fields(config: Dict[str, Any]) -> Dict[str, Any]:
    """Accept the obvious names for a knowledge base selection; the node's field is selectedBases."""
    ids: List[str] = list(config.get("selectedBases") or []) if isinstance(config.get("selectedBases"), list) else (
        [config["selectedBases"]] if isinstance(config.get("selectedBases"), str) and config["selectedBases"] else []
    )
    found = False
    for alias in _KNOWLEDGE_BASE_ALIASES:
        if alias not in config:
            continue
        found = True
        value = config.pop(alias)
        if isinstance(value, list):
            ids.extend(str(v) for v in value if v)
        elif value:
            ids.append(str(value))
    if found:
        config["selectedBases"] = list(dict.fromkeys(ids))
    return config


# {{name}} or {{parameters.name}} in a tool's config: the agent means "what I pass in",
# which the engine knows only as {{source.name}}.
_VARIABLE_ROOT_NAMES = set(VARIABLE_ROOTS)
_PARAMETER_PREFIXES = {"parameters", "params", "parameter", "input", "inputs", "args", "arguments", "tool_input"}
_BARE_PLACEHOLDER = re.compile(
    r"\{\{\s*(?:(" + "|".join(sorted(_PARAMETER_PREFIXES - _VARIABLE_ROOT_NAMES)) + r")\.)?([A-Za-z_]\w*)\s*\}\}"
)


class WorkflowDraft:
    def __init__(
        self,
        nodes: Optional[List[Dict[str, Any]]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        origin: str = ORIGIN_NEW,
    ):
        self.nodes: List[Dict[str, Any]] = nodes or []
        self.edges: List[Dict[str, Any]] = edges or []
        self.origin = origin
        self.status = STATUS_DRAFT
        self.revision = 0
        self.summary = ""
        self.aliases: Dict[str, str] = {}  # node id -> alias
        self.next_alias = 1
        self.baseline_keys: List[str] = []
        self.new_node_ids: List[str] = []
        self.changes: List[Dict[str, Any]] = []
        self.defaults: Dict[str, Any] = {}
        self.selected_node_id: Optional[str] = None
        # True once a signed-in user has opened this draft from a canvas. Tenant
        # resources are only listed for such drafts, never for the pre-login chat.
        self.authenticated = False
        # Set by any change that can alter behaviour, cleared by a test run. Finalizing
        # is refused while it is set, so a workflow is never declared done unrun.
        self.needs_test = False
        # The person's most recent test run on the canvas, already condensed to text.
        self.last_user_test = ""
        # True when this turn began on a new agent's starter canvas (placeholders already removed).
        self.starter_cleared = False
        # Failing test runs in a row, and the failure they share, to stop a fix-and-retest loop.
        self.failed_tests = 0
        self.same_failure_count = 0
        self.last_failure = ""
        # Builder test runs bypass steps that send or create things (tickets, emails,
        # messages) unless the person turns simulation off on the canvas.
        self.simulate_actions = True
        # A question the builder asked with ask_user, shown on the canvas as options
        # to click: {"question", "options", "recommended"}. Cleared when the next
        # turn starts from the canvas.
        self.question: Optional[Dict[str, Any]] = None
        self._assign_aliases()

    # ── Construction / persistence ────────────────────────────────────────

    @classmethod
    def from_canvas(
        cls,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        defaults: Optional[Dict[str, Any]] = None,
        selected_node_id: Optional[str] = None,
        previous: Optional["WorkflowDraft"] = None,
        last_test_run: Optional[Dict[str, Any]] = None,
    ) -> "WorkflowDraft":
        """Start a turn from the canvas as the user currently has it."""
        # A connection whose node is gone is invisible on the canvas and nothing the
        # builder can act on, so it is dropped here rather than reported as an error.
        ids = {n["id"] for n in nodes}
        live_edges = [e for e in edges if e.get("source") in ids and e.get("target") in ids]
        draft = cls(deepcopy(nodes), deepcopy(live_edges), origin=ORIGIN_CANVAS if nodes else ORIGIN_NEW)
        if previous:
            # Keep aliases stable across turns so the agent's memory of "n4" stays true.
            live_ids = {n["id"] for n in draft.nodes}
            draft.aliases = {i: a for i, a in previous.aliases.items() if i in live_ids}
            draft.next_alias = previous.next_alias
            draft.revision = previous.revision
            draft._assign_aliases()
        draft.defaults = dict(defaults or {})
        draft.selected_node_id = selected_node_id
        draft.authenticated = True
        draft.last_user_test = draft._condense_user_test(last_test_run)
        if draft.is_starter_template():
            # Nothing on a starter canvas is the user's work. Its placeholder steps are
            # cleared up front, so the builder starts from Start and one output instead
            # of spending model calls discovering and removing them.
            draft._clear_starter_placeholders()
            draft.baseline_keys = []
        else:
            draft.baseline_keys = sorted({i.key for i in draft.issues()})
        return draft

    def _clear_starter_placeholders(self) -> None:
        keep = catalog.ENTRY_NODE_TYPES | catalog.OUTPUT_NODE_TYPES | VISUAL_NODE_TYPES
        removed = [n for n in self.nodes if n.get("type") not in keep]
        if not removed:
            return
        removed_ids = {n["id"] for n in removed}
        self.nodes = [n for n in self.nodes if n["id"] not in removed_ids]
        self.edges = [
            e for e in self.edges if e["source"] not in removed_ids and e["target"] not in removed_ids
        ]
        # A starter canvas has no history to stay consistent with: number what is left from n1.
        self.aliases, self.next_alias = {}, 1
        self._assign_aliases()
        # Shown with the builder's own changes once it builds something; on its own it
        # does not count as a change, so a turn that only answers a question leaves
        # the canvas exactly as it was.
        self.changes.append({
            "op": "remove_node",
            "summary": f"Removed {', '.join(self._name(n) for n in removed)}",
            "node_ids": sorted(removed_ids),
        })
        self.starter_cleared = True

    def _condense_user_test(self, run: Optional[Dict[str, Any]]) -> str:
        """Turn the canvas's raw test response (often 100 KB+) into the short report the builder reads."""
        if not run or not isinstance(run, dict):
            return ""
        from app.modules.workflow.builder.testing import format_test_result

        inputs = run.get("inputs") or {}
        message = inputs.get("message") if isinstance(inputs, dict) else None
        message = message or json.dumps(inputs, ensure_ascii=False)
        response = run.get("response")
        if not isinstance(response, dict):
            return f"TEST RUN by the person — input: {str(message)[:300]}\nIt failed before producing a result: {run.get('error') or 'unknown error'}"
        try:
            return format_test_result(self, str(message), response, by="the person on the canvas")
        except Exception as exc:  # a malformed payload must never block the turn
            return f"TEST RUN by the person could not be read: {exc}"

    def _revision_at_load(self) -> int:
        """The revision before the builder changed anything this turn (one bump per recorded change)."""
        builder_changes = len(self.changes) - (1 if self.starter_cleared else 0)
        return self.revision - builder_changes

    def is_starter_template(self) -> bool:
        """
        True for the canvas a new agent starts with: an entry node, an output and
        nothing but unconfigured placeholder nodes in between.
        """
        nodes = [n for n in self.nodes if n.get("type") not in VISUAL_NODE_TYPES]
        if not nodes or len(nodes) > 4:
            return False
        starter_values = _starter_workflow_values()
        for node in nodes:
            node_type = node.get("type", "")
            if node_type in catalog.ENTRY_NODE_TYPES or node_type in catalog.OUTPUT_NODE_TYPES:
                continue
            if not catalog.is_known(node_type):
                return False
            defaults = catalog.entry(node_type)["defaultData"]
            placeholder_values = starter_values.get(node_type, {})
            data = node.get("data") or {}
            configured = any(
                data.get(key) not in (None, "", [], {})
                and data.get(key) != defaults.get(key)
                and data.get(key) != placeholder_values.get(key)
                for key in data
                if key not in catalog.NON_CONFIG_KEYS and key not in ("name", "providerId", "deactivated")
            )
            if configured:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "origin": self.origin,
            "status": self.status,
            "revision": self.revision,
            "summary": self.summary,
            "aliases": self.aliases,
            "next_alias": self.next_alias,
            "baseline_keys": self.baseline_keys,
            "new_node_ids": self.new_node_ids,
            "changes": self.changes,
            "defaults": self.defaults,
            "selected_node_id": self.selected_node_id,
            "authenticated": self.authenticated,
            "needs_test": self.needs_test,
            "last_user_test": self.last_user_test,
            "starter_cleared": self.starter_cleared,
            "failed_tests": self.failed_tests,
            "same_failure_count": self.same_failure_count,
            "last_failure": self.last_failure,
            "simulate_actions": self.simulate_actions,
            "question": self.question,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WorkflowDraft":
        draft = cls.__new__(cls)
        draft.nodes = payload.get("nodes") or []
        draft.edges = payload.get("edges") or []
        draft.origin = payload.get("origin", ORIGIN_NEW)
        draft.status = payload.get("status", STATUS_DRAFT)
        draft.revision = payload.get("revision", 0)
        draft.summary = payload.get("summary", "")
        draft.aliases = payload.get("aliases") or {}
        draft.next_alias = payload.get("next_alias", 1)
        draft.baseline_keys = payload.get("baseline_keys") or []
        draft.new_node_ids = payload.get("new_node_ids") or []
        draft.changes = payload.get("changes") or []
        draft.defaults = payload.get("defaults") or {}
        draft.selected_node_id = payload.get("selected_node_id")
        draft.authenticated = bool(payload.get("authenticated"))
        draft.needs_test = bool(payload.get("needs_test"))
        draft.last_user_test = payload.get("last_user_test") or ""
        draft.starter_cleared = bool(payload.get("starter_cleared"))
        draft.failed_tests = int(payload.get("failed_tests") or 0)
        draft.same_failure_count = int(payload.get("same_failure_count") or 0)
        draft.last_failure = payload.get("last_failure") or ""
        draft.simulate_actions = bool(payload.get("simulate_actions", True))
        question = payload.get("question")
        draft.question = question if isinstance(question, dict) else None
        draft._assign_aliases()
        return draft

    # ── Aliases ───────────────────────────────────────────────────────────

    def _assign_aliases(self) -> None:
        for node in self.nodes:
            if node.get("type") in VISUAL_NODE_TYPES or node["id"] in self.aliases:
                continue
            self.aliases[node["id"]] = f"n{self.next_alias}"
            self.next_alias += 1

    def alias(self, node_id: str) -> str:
        return self.aliases.get(node_id, node_id)

    def find(self, ref: Optional[str]) -> Dict[str, Any]:
        """Resolve a node reference: an alias, a real id, or an exact node name."""
        if not ref:
            raise DraftError("A node id is required (for example \"n2\").")
        ref = str(ref).strip()
        by_alias = {alias: node_id for node_id, alias in self.aliases.items()}
        node_id = by_alias.get(ref, ref)
        for node in self.nodes:
            if node["id"] == node_id:
                return node
        matches = [
            n for n in self.nodes
            if str((n.get("data") or {}).get("name", "")).lower() == ref.lower()
        ]
        if len(matches) == 1:
            return matches[0]
        known = ", ".join(sorted(by_alias, key=lambda a: int(a[1:]) if a[1:].isdigit() else 0)) or "none"
        raise DraftError(f"No node '{ref}' in the workflow. Existing ids: {known}.")

    def _split_ref(self, ref: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """Accept "n3" or "n3.output_true"."""
        ref = str(ref or "").strip()
        if "." in ref:
            node_ref, handle = ref.split(".", 1)
            try:
                return self.find(node_ref), handle
            except DraftError:
                pass
        return self.find(ref), None

    # ── Issues ────────────────────────────────────────────────────────────

    def issues(self) -> List[Issue]:
        return validate_workflow(self.nodes, self.edges)

    def new_issues(self, issues: Optional[List[Issue]] = None) -> List[Issue]:
        baseline = set(self.baseline_keys)
        return [i for i in (issues if issues is not None else self.issues()) if i.key not in baseline]

    def describe_issue(self, issue: Issue) -> str:
        where = f"[{self.alias(issue.node_id)}] " if issue.node_id else ""
        return f"{issue.severity.upper()} {issue.code}: {where}{self._with_aliases(issue.message)}"

    # ── Mutation bookkeeping ──────────────────────────────────────────────

    def _touch(
        self,
        op: str,
        summary: str,
        node_ids: Optional[List[str]] = None,
        behavioural: bool = True,
    ) -> None:
        self.revision += 1
        self.status = STATUS_DRAFT
        if behavioural:
            self.needs_test = True
        self.changes.append({"op": op, "summary": summary, "node_ids": node_ids or []})

    def open_problems(self, limit: int = 6) -> str:
        """
        What still stands between the draft and a valid workflow, as a short list.
        Appended to the result of every change so the builder always sees what is left.
        """
        errors = blocking(self.new_issues())
        if not errors:
            return "No open errors."
        lines = [f"Open errors ({len(errors)}) to fix before finalize_workflow:"]
        lines.extend(f"- {self.describe_issue(issue)[:260]}" for issue in errors[:limit])
        if len(errors) > limit:
            lines.append(f"- … and {len(errors) - limit} more (get_workflow lists all)")
        return "\n".join(lines)

    @staticmethod
    def _clean_code(node_type: str, field: str, code: Any) -> Any:
        """
        Normalize and check Python written by the builder.

        Code that arrives as one line full of literal ``\n`` was escaped once too often
        on its way through a tool call; it is restored. Code that does not parse is
        rejected with the syntax error, instead of failing later inside a run.
        """
        if not isinstance(code, str) or not code.strip():
            return code
        if "\n" not in code and "\\n" in code:
            code = code.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            line = (exc.text or "").strip()
            raise DraftError(
                f"The {field} is not valid Python: {exc.msg} (line {exc.lineno}: {line[:120]}). "
                f"Send the code as plain text with real line breaks."
            ) from exc
        if node_type == "pythonCodeNode":
            defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if "executable_function" not in defined:
                raise DraftError(
                    "The code must define `def executable_function(params):` at the top level and "
                    "return the result from it."
                )
        return code

    def _node_edges(self, node_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.edges if e.get("source") == node_id or e.get("target") == node_id]

    def _name(self, node: Dict[str, Any]) -> str:
        return (node.get("data") or {}).get("name") or node.get("type", "")

    # ── Config translation ────────────────────────────────────────────────

    def _with_aliases(self, text: str) -> str:
        return _NODE_OUTPUT_REF.sub(lambda m: m.group(1) + self.alias(m.group(2)), text)

    def _with_ids(self, value: Any) -> Any:
        """Turn {{node_outputs.n3...}} written by the agent into real node ids."""
        by_alias = {alias: node_id for node_id, alias in self.aliases.items()}
        if isinstance(value, str):
            return _NODE_OUTPUT_REF.sub(lambda m: m.group(1) + by_alias.get(m.group(2), m.group(2)), value)
        if isinstance(value, dict):
            return {k: self._with_ids(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._with_ids(v) for v in value]
        return value

    def _clean_config(self, node_type: str, config: Any) -> Dict[str, Any]:
        if config is None or config == "":
            return {}
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError as exc:
                raise DraftError(f"config must be a JSON object: {exc}") from exc
        if not isinstance(config, dict):
            raise DraftError("config must be an object of field -> value.")

        config = {k: v for k, v in config.items() if v != SECRET_PLACEHOLDER}
        config.pop("handlers", None)
        if node_type == "knowledgeBaseNode":
            config = _alias_knowledge_base_fields(config)
        unknown = invalid_config_keys(node_type, config)
        if unknown:
            allowed = ", ".join(sorted(catalog.allowed_config_keys(node_type) - {"name", "deactivated"}))
            raise DraftError(
                f"{node_type} has no config field(s) {unknown}. Valid fields: {allowed}. "
                f"Call lookup_node(\"{node_type}\") for details."
            )
        for field in catalog.PLACEHOLDER_FIELDS.get(node_type, []):
            if node_type in ("pythonCodeNode", "dataMapperNode") and field in config:
                config[field] = self._clean_code(node_type, field, config[field])
        for field in catalog.config_fields(node_type):
            options = field.get("options")
            value = config.get(field["name"])
            if options and isinstance(value, str) and value and value not in options:
                raise DraftError(
                    f"'{value}' is not a valid {field['name']} for {node_type}. Use one of {options}."
                )
        return self._with_ids(config)

    @staticmethod
    def _normalize_cases(cases: Any, existing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Give every Switch case a stable id, reusing ids of cases that keep their label."""
        if not isinstance(cases, list):
            raise DraftError("cases must be a list of {label, value}.")
        by_label = {str(c.get("label", "")).lower(): c.get("id") for c in existing if isinstance(c, dict)}
        used: set = set()
        normalized: List[Dict[str, Any]] = []

        def next_id() -> str:
            numbers = [
                int(i.replace("case_", "")) for i in used | set(by_label.values())
                if isinstance(i, str) and i.replace("case_", "").isdigit()
            ]
            return f"case_{max(numbers, default=0) + 1}"

        for raw in cases:
            if isinstance(raw, str):
                raw = {"label": raw, "value": raw}
            if not isinstance(raw, dict):
                raise DraftError("Each case must be {label, value}.")
            label = str(raw.get("label") or raw.get("value") or "")
            value = raw.get("value", label)
            case_id = raw.get("id") or by_label.get(label.lower())
            if not case_id or case_id in used:
                case_id = next_id()
            used.add(case_id)
            normalized.append({"id": case_id, "label": label, "value": value})
        return normalized

    def _refresh_handlers(self, node: Dict[str, Any]) -> List[str]:
        """Recompute config-derived handles; drop edges left on handles that no longer exist."""
        node["data"]["handlers"] = catalog.handlers_for(node["type"], node["data"])
        valid = {h["id"] for h in node["data"]["handlers"]}
        dropped: List[str] = []
        kept: List[Dict[str, Any]] = []
        for edge in self.edges:
            stale = (
                (edge.get("source") == node["id"] and (edge.get("sourceHandle") or "output") not in valid)
                or (edge.get("target") == node["id"] and (edge.get("targetHandle") or "input") not in valid)
            )
            if stale:
                dropped.append(self._edge_text(edge))
            else:
                kept.append(edge)
        self.edges = kept
        return dropped

    # ── Operations ────────────────────────────────────────────────────────

    def _missing_required(self, node: Dict[str, Any]) -> List[str]:
        data = node.get("data") or {}
        return [
            field for field in catalog.REQUIRED_CONFIG.get(node.get("type", ""), [])
            if data.get(field) in (None, "", [], {})
        ]

    def add_node(
        self,
        node_type: str,
        name: Optional[str] = None,
        config: Any = None,
        connect_from: Optional[str] = None,
        connect_to: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        node_type = str(node_type or "").strip()
        if not catalog.is_known(node_type) or node_type in catalog.HIDDEN_NODE_TYPES:
            raise DraftError(catalog.unknown_type_message(node_type))
        if node_type == "chatInputNode" and any(n.get("type") == "chatInputNode" for n in self.nodes):
            existing = next(n for n in self.nodes if n.get("type") == "chatInputNode")
            raise DraftError(
                f"The workflow already has a chatInputNode ({self.alias(existing['id'])}). Use that one."
            )

        cleaned = self._clean_config(node_type, config)
        if system_prompt and str(system_prompt).strip():
            if "systemPrompt" not in catalog.allowed_config_keys(node_type):
                raise DraftError(f"{node_type} has no system prompt; leave system_prompt out.")
            cleaned["systemPrompt"] = self._with_ids(str(system_prompt))
        # Resolve connection endpoints before changing anything, so a bad reference adds nothing.
        source = self._split_ref(connect_from) if connect_from else None
        target = self._split_ref(connect_to) if connect_to else None

        data = catalog.default_data(node_type)
        data.update(deepcopy(BUILDER_DEFAULTS.get(node_type, {})))
        if node_type in PROVIDER_NODE_TYPES and self.defaults.get("providerId"):
            data["providerId"] = self.defaults["providerId"]
        if node_type == "switchNode" and "cases" in cleaned:
            cleaned["cases"] = self._normalize_cases(cleaned["cases"], [])
        data.update(cleaned)
        data["name"] = (name or cleaned.get("name") or catalog.label(node_type)).strip()
        data["label"] = catalog.label(node_type)
        data["handlers"] = catalog.handlers_for(node_type, data)

        node = {"id": str(uuid4()), "type": node_type, "position": {"x": 0, "y": 0}, "data": data}
        self.nodes.append(node)
        self._assign_aliases()
        self.new_node_ids.append(node["id"])

        notes: List[str] = []
        try:
            if source and target:
                # Inserting between two connected nodes replaces their direct connection.
                removed = self._remove_edges(source[0]["id"], target[0]["id"], source[1])
                if removed:
                    notes.append(f"replaced {removed[0]}")
            if source:
                notes.append(self._connect(source[0], node, source[1], None))
            if target:
                # A branching node placed in front of something continues to it on its
                # first output (output_true, output_case_1); the other outputs stay free.
                outputs = catalog.handle_ids(node_type, data, "source")
                first_output = outputs[0] if len(outputs) > 1 and "output" not in outputs else None
                notes.append(self._connect(node, target[0], first_output, target[1]))
        except DraftError:
            self.nodes.remove(node)
            self.aliases.pop(node["id"], None)
            self.next_alias -= 1
            self.new_node_ids.remove(node["id"])
            raise

        alias = self.alias(node["id"])
        self._touch("add_node", f"Added {data['name']}", [node["id"]])
        handles = catalog.describe_handles(node_type, data)
        message = f"Added {alias} ({node_type} \"{data['name']}\"). Handles ({handles})."
        if notes:
            message += " " + "; ".join(notes) + "."
        attaches = bool(
            set(catalog.handle_ids(node_type, data, "source")) & catalog.ATTACHMENT_SOURCE_HANDLES
        )
        if not self._node_edges(node["id"]) and node_type not in catalog.ENTRY_NODE_TYPES:
            if attaches:
                message += f" NOT ATTACHED YET: connect it to its agent with connect(source=\"{alias}\", target=<agent id>)."
            else:
                message += (
                    f" NOT CONNECTED YET: nothing leads into {alias}, so it will never run. Connect it "
                    f"now with connect(source=<the step before it>, target=\"{alias}\")."
                )
        missing = self._missing_required(node)
        if missing:
            message += (
                f" Still required before the workflow is valid: {', '.join(missing)}. "
                f"Set each with set_node_field(node_id=\"{alias}\", field=..., value=...)."
            )
        return {"message": message, "node_id": node["id"], "alias": alias}

    def quiet_parsing_agents(self, node_ids: List[str]) -> List[str]:
        """
        Turn memory off on these agents when every step their reply goes to parses
        or compares it. A classifier that remembers earlier messages drifts and
        costs tokens on every run; memory is for agents that talk to the person.
        Returns the aliases changed.
        """
        changed: List[str] = []
        for node_id in node_ids:
            node = next((n for n in self.nodes if n["id"] == node_id), None)
            if not node or node.get("type") != "agentNode" or not (node.get("data") or {}).get("memory"):
                continue
            readers = [
                next((n for n in self.nodes if n["id"] == edge["target"]), None)
                for edge in self.edges
                if edge["source"] == node_id and (edge.get("sourceHandle") or "output") == "output"
            ]
            if readers and all(r is not None and r.get("type") in PARSING_NODE_TYPES for r in readers):
                node["data"]["memory"] = False
                changed.append(self.alias(node_id))
        return changed

    def set_field(self, ref: str, field: str, value: Any) -> Dict[str, Any]:
        """Set one config field. ``value`` may arrive as text even for non-text fields."""
        node = self.find(ref)
        field = str(field or "").strip()
        if not field:
            raise DraftError("field is required, e.g. \"systemPrompt\".")
        if value is None:
            raise DraftError("value is required.")
        if field == "name":
            return self.update_node(ref, name=str(value))
        if field == "parameters" and node.get("type") == "toolBuilderNode":
            return self.update_node(ref, {"parameters": value})

        if isinstance(value, str) and catalog.is_known(node.get("type", "")):
            # Text stays text. Anything else (numbers, booleans, lists, objects) is sent as
            # JSON text by the agent; decide by what the field currently holds.
            current = (node.get("data") or {}).get(field, catalog.default_data(node["type"]).get(field))
            if current is not None and not isinstance(current, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError as exc:
                    raise DraftError(
                        f"{field} holds a {type(current).__name__}; send its value as JSON "
                        f"(for example {json.dumps(current)[:60]}). Could not parse: {exc}"
                    ) from exc
        return self.update_node(ref, {field: value})

    def update_node(self, ref: str, config: Any = None, name: Optional[str] = None) -> Dict[str, Any]:
        node = self.find(ref)
        if not catalog.is_known(node.get("type", "")):
            raise DraftError(f"{self.alias(node['id'])} has an unknown type and cannot be edited.")
        if isinstance(config, str) and config.strip():
            try:
                config = json.loads(config)
            except json.JSONDecodeError as exc:
                raise DraftError(f"config must be a JSON object: {exc}") from exc
        tool_parameters = None
        if node["type"] == "toolBuilderNode" and isinstance(config, dict):
            config = dict(config)
            plumbing = sorted(TOOL_PLUMBING_KEYS & set(config))
            if plumbing:
                raise DraftError(
                    f"{plumbing} of a tool are generated and must not be edited directly; they are not "
                    f"why an agent ignores a tool. To change which arguments the agent passes, set the "
                    f"field \"parameters\" to a JSON object of {{name: description}}. If the agent is not "
                    f"calling the tool, improve the tool's description and the agent's system prompt."
                )
            if "parameters" in config:
                tool_parameters = config.pop("parameters")
        cleaned = self._clean_config(node["type"], config)
        if tool_parameters is not None:
            input_schema, forward = self._tool_plumbing(tool_parameters)
            cleaned["inputSchema"] = input_schema
            cleaned["forwardTemplate"] = json.dumps(forward)
        if name:
            cleaned["name"] = str(name).strip()
        if not cleaned:
            raise DraftError(
                "Nothing to update: pass config (a JSON object of field -> value) and/or name. "
                "For one field use set_node_field."
            )

        data = node.setdefault("data", {})
        if node["type"] == "switchNode" and "cases" in cleaned:
            cleaned["cases"] = self._normalize_cases(cleaned["cases"], data.get("cases") or [])
        data.update(cleaned)
        dropped = self._refresh_handlers(node) if catalog.entry(node["type"]).get("dynamicHandles") else []

        alias = self.alias(node["id"])
        shown = set(cleaned)
        if tool_parameters is not None:
            shown = (shown - TOOL_PLUMBING_KEYS) | {"parameters"}
        fields = ", ".join(sorted(shown))
        self._touch(
            "update_node", f"Updated {self._name(node)} ({fields})", [node["id"]],
            behavioural=shown != {"name"},
        )
        message = f"Updated {alias}: {fields}."
        if catalog.entry(node["type"]).get("dynamicHandles"):
            message += f" Handles ({catalog.describe_handles(node['type'], data)})."
        if dropped:
            message += f" Removed connections on handles that no longer exist: {'; '.join(dropped)}."
        return {"message": message, "node_id": node["id"], "alias": alias}

    def remove_node(self, ref: str) -> Dict[str, Any]:
        node = self.find(ref)
        to_remove = [node]
        if node.get("type") == "toolBuilderNode":
            # A tool's wrapped sub-flow has no meaning without the tool.
            children = {e["source"]: [] for e in self.edges}
            for edge in self.edges:
                children.setdefault(edge["source"], []).append(edge)
            stack = [e["target"] for e in self.edges if e["source"] == node["id"] and is_subflow_edge(e)]
            seen = set()
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                stack.extend(e["target"] for e in children.get(current, []))
            to_remove.extend(n for n in self.nodes if n["id"] in seen)

        removed_ids = {n["id"] for n in to_remove}
        names = ", ".join(f"{self.alias(n['id'])} \"{self._name(n)}\"" for n in to_remove)
        self.nodes = [n for n in self.nodes if n["id"] not in removed_ids]
        self.edges = [e for e in self.edges if e["source"] not in removed_ids and e["target"] not in removed_ids]
        self.new_node_ids = [i for i in self.new_node_ids if i not in removed_ids]
        self._touch("remove_node", f"Removed {', '.join(self._name(n) for n in to_remove)}", list(removed_ids))
        return {"message": f"Removed {names} and their connections."}

    def _edge_text(self, edge: Dict[str, Any]) -> str:
        return (
            f"{self.alias(edge['source'])}.{edge.get('sourceHandle') or 'output'} -> "
            f"{self.alias(edge['target'])}.{edge.get('targetHandle') or 'input'}"
        )

    def _infer_handles(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any],
        source_handle: Optional[str],
        target_handle: Optional[str],
    ) -> Tuple[str, str]:
        outputs = catalog.handle_ids(source["type"], source.get("data"), "source")
        inputs = catalog.handle_ids(target["type"], target.get("data"), "target")
        source_alias, target_alias = self.alias(source["id"]), self.alias(target["id"])

        if not outputs:
            raise DraftError(f"{source_alias} ({source['type']}) has no outputs, so nothing can follow it.")
        if not inputs:
            raise DraftError(f"{target_alias} ({target['type']}) has no inputs, so nothing can connect into it.")

        if not source_handle:
            if source["type"] == "toolBuilderNode":
                source_handle = "output_tool" if "input_tools" in inputs else "starter_processor"
            elif len(outputs) == 1:
                source_handle = outputs[0]
            elif "output" in outputs:
                source_handle = "output"
            else:
                raise DraftError(
                    f"{source_alias} ({source['type']}) has several outputs: {', '.join(outputs)}. "
                    f"Say which one, e.g. source=\"{source_alias}.{outputs[0]}\"."
                )
        if source_handle not in outputs:
            raise DraftError(
                f"{source_alias} ({source['type']}) has no output '{source_handle}'. Available: {', '.join(outputs)}."
            )

        if not target_handle:
            kind = catalog.handle_compatibility(source["type"], source.get("data"), source_handle)
            if kind == "tools":
                target_handle = "input_tools"
            elif kind == "sub_agents":
                target_handle = "input_sub_agents"
            elif "input" in inputs:
                target_handle = "input"
            else:
                target_handle = inputs[0]
        if target_handle not in inputs:
            hint = ""
            if target_handle in ("input_tools", "input_sub_agents"):
                hint = " Only agent nodes accept tools and sub-agents."
            raise DraftError(
                f"{target_alias} ({target['type']}) has no input '{target_handle}'. "
                f"Available: {', '.join(inputs)}.{hint}"
            )

        source_kind = catalog.handle_compatibility(source["type"], source.get("data"), source_handle)
        target_kind = catalog.handle_compatibility(target["type"], target.get("data"), target_handle)
        special = {"tools", "sub_agents"}
        if (source_kind in special or target_kind in special) and source_kind != target_kind:
            raise DraftError(
                f"{source_alias}.{source_handle} ({source_kind}) cannot connect to "
                f"{target_alias}.{target_handle} ({target_kind})."
            )
        return source_handle, target_handle

    def _connect(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any],
        source_handle: Optional[str],
        target_handle: Optional[str],
    ) -> str:
        if source["id"] == target["id"]:
            raise DraftError("A node cannot connect to itself.")
        for node in (source, target):
            if not catalog.is_known(node.get("type", "")):
                raise DraftError(f"{self.alias(node['id'])} has an unknown type and cannot be connected.")
        source_handle, target_handle = self._infer_handles(source, target, source_handle, target_handle)

        for edge in self.edges:
            if (
                edge["source"] == source["id"] and edge["target"] == target["id"]
                and (edge.get("sourceHandle") or "output") == source_handle
                and (edge.get("targetHandle") or "input") == target_handle
            ):
                return f"{self._edge_text(edge)} already exists"

        if target_handle == "input" and target["type"] != "aggregatorNode":
            existing = [
                e for e in self.edges
                if e["target"] == target["id"] and (e.get("targetHandle") or "input") == "input"
            ]
            if existing:
                raise DraftError(
                    f"{self.alias(target['id'])} \"{self._name(target)}\" already receives input from "
                    f"{self.alias(existing[0]['source'])}. A node accepts one input: disconnect that first, "
                    f"give this branch its own node, or merge branches with an aggregatorNode."
                )
        if source_handle == "starter_processor":
            existing = [
                e for e in self.edges
                if e["source"] == source["id"] and e.get("sourceHandle") == "starter_processor"
            ]
            if existing:
                raise DraftError(
                    f"Tool {self.alias(source['id'])} already runs {self.alias(existing[0]['target'])}. "
                    f"A tool wraps one node; create another tool with add_tool."
                )

        edge = make_edge(source["id"], target["id"], source_handle, target_handle)
        self.edges.append(edge)
        return f"connected {self._edge_text(edge)}"

    def connect(
        self,
        source: str,
        target: str,
        source_handle: Optional[str] = None,
        target_handle: Optional[str] = None,
    ) -> Dict[str, Any]:
        source_node, inline_source = self._split_ref(source)
        target_node, inline_target = self._split_ref(target)
        text = self._connect(
            source_node, target_node, source_handle or inline_source, target_handle or inline_target
        )
        if not text.endswith("already exists"):
            self._touch(
                "connect",
                f"Connected {self._name(source_node)} to {self._name(target_node)}",
                [source_node["id"], target_node["id"]],
            )
        return {"message": text[0].upper() + text[1:] + "."}

    def _remove_edges(self, source_id: str, target_id: str, source_handle: Optional[str]) -> List[str]:
        removed, kept = [], []
        for edge in self.edges:
            match = (
                edge["source"] == source_id and edge["target"] == target_id
                and (not source_handle or (edge.get("sourceHandle") or "output") == source_handle)
            )
            (removed if match else kept).append(edge)
        self.edges = kept
        return [self._edge_text(e) for e in removed]

    def disconnect(self, source: str, target: str, source_handle: Optional[str] = None) -> Dict[str, Any]:
        source_node, inline_source = self._split_ref(source)
        target_node, _ = self._split_ref(target)
        removed = self._remove_edges(source_node["id"], target_node["id"], source_handle or inline_source)
        if not removed:
            raise DraftError(
                f"There is no connection from {self.alias(source_node['id'])} to {self.alias(target_node['id'])}."
            )
        self._touch(
            "disconnect",
            f"Disconnected {self._name(source_node)} from {self._name(target_node)}",
            [source_node["id"], target_node["id"]],
        )
        return {"message": f"Removed {'; '.join(removed)}."}

    @staticmethod
    def _tool_plumbing(parameters: Any) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """A tool's argument schema and the template that forwards the arguments to its node."""
        if isinstance(parameters, str) and parameters.strip():
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError as exc:
                raise DraftError(f"parameters must be a JSON object: {exc}") from exc
        parameters = parameters or {}
        if not isinstance(parameters, dict):
            raise DraftError("parameters must be an object of parameter name -> description.")
        input_schema: Dict[str, Any] = {}
        forward: Dict[str, str] = {}
        for param, spec in parameters.items():
            if not re.fullmatch(r"[A-Za-z_]\w*", str(param)):
                raise DraftError(f"Parameter name '{param}' must be letters, digits and underscores.")
            spec = spec if isinstance(spec, dict) else {"description": str(spec)}
            input_schema[param] = {
                "type": spec.get("type", "string"),
                "required": bool(spec.get("required", True)),
                "stateful": False,
                "description": spec.get("description", ""),
                "useInFilter": False,
                "defaultValue": "",
            }
            forward[f"source.{param}"] = f"{{{{direct_input.parameters.{param}}}}}"
        return input_schema, forward

    def add_tool(
        self,
        agent: str,
        node_type: str,
        name: str,
        description: str,
        config: Any = None,
        parameters: Any = None,
    ) -> Dict[str, Any]:
        """Give an agent a tool: a toolBuilderNode wrapping one node, with both connections."""
        agent_node = self.find(agent)
        if "input_tools" not in catalog.handle_ids(agent_node.get("type", ""), agent_node.get("data"), "target"):
            raise DraftError(
                f"{self.alias(agent_node['id'])} ({agent_node.get('type')}) cannot use tools. "
                f"Tools attach to agentNode, subAgentNode or voiceAgentNode."
            )
        node_type = str(node_type or "").strip()
        if not catalog.is_known(node_type) or node_type in catalog.HIDDEN_NODE_TYPES:
            raise DraftError(catalog.unknown_type_message(node_type))
        if "input" not in catalog.handle_ids(node_type, None, "target"):
            raise DraftError(f"{node_type} cannot be wrapped as a tool (it has no input).")
        if not description or not str(description).strip():
            raise DraftError("description is required: it tells the agent when to call the tool.")

        cleaned = self._clean_config(node_type, config)
        if isinstance(parameters, str) and parameters.strip():
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError as exc:
                raise DraftError(f"parameters must be a JSON object: {exc}") from exc
        parameters = parameters or {}
        if not isinstance(parameters, dict):
            raise DraftError("parameters must be an object of parameter name -> description.")
        if node_type == "knowledgeBaseNode" and not parameters:
            parameters = {"query": "What to search for, as a short self-contained question."}
            cleaned.setdefault("query", "{{source.query}}")

        parameters, cleaned, declared = self._declare_bare_placeholders(parameters, cleaned)
        input_schema, forward = self._tool_plumbing(parameters)

        before_nodes, before_edges = list(self.nodes), list(self.edges)
        before_new, before_aliases, before_next = list(self.new_node_ids), dict(self.aliases), self.next_alias
        before_changes, before_revision = list(self.changes), self.revision
        try:
            tool = self.add_node(
                "toolBuilderNode",
                name,
                {
                    "description": str(description).strip(),
                    "forwardTemplate": json.dumps(forward),
                    **({"inputSchema": input_schema} if input_schema else {}),
                },
            )
            wrapped = self.add_node(node_type, cleaned.get("name") or name, cleaned)
            self._connect(self.find(tool["node_id"]), agent_node, "output_tool", "input_tools")
            self._connect(self.find(tool["node_id"]), self.find(wrapped["node_id"]), "starter_processor", "input")
        except DraftError:
            self.nodes, self.edges = before_nodes, before_edges
            self.new_node_ids, self.aliases, self.next_alias = before_new, before_aliases, before_next
            self.changes, self.revision = before_changes, before_revision
            raise

        # Collapse the two add_node entries into one user-facing change.
        self.changes = before_changes
        self.revision = before_revision
        self._touch(
            "add_tool",
            f"Added tool {name} to {self._name(agent_node)}",
            [tool["node_id"], wrapped["node_id"]],
        )
        message = (
            f"Added tool {tool['alias']} (\"{name}\") for {self.alias(agent_node['id'])}, "
            f"running {wrapped['alias']} ({node_type})."
        )
        if parameters:
            refs = ", ".join(f"{{{{source.{p}}}}}" for p in parameters)
            message += f" The agent passes: {', '.join(parameters)}. Read them in {wrapped['alias']}'s config as {refs}."
        if declared:
            message += (
                f" ({', '.join(declared)} were declared from the {{{{...}}}} placeholders in the config and "
                f"rewritten to {{{{source.…}}}}.)"
            )
        return {"message": message, "tool": tool["alias"], "node": wrapped["alias"]}

    @staticmethod
    def _declare_bare_placeholders(
        parameters: Any, config: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """
        {{city}} in a tool's config can only mean "what the agent passes in": declare
        it as a tool parameter and read it as {{source.city}}, instead of failing the
        plan on an unknown variable and spending a model call on the correction.
        """
        if isinstance(parameters, str) and parameters.strip():
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError as exc:
                raise DraftError(f"parameters must be a JSON object: {exc}") from exc
        parameters = dict(parameters or {}) if isinstance(parameters, dict) else parameters
        names = [
            name for prefix, name in dict.fromkeys(_BARE_PLACEHOLDER.findall(json.dumps(config)))
            if prefix or name not in _VARIABLE_ROOT_NAMES
        ]
        names = list(dict.fromkeys(names))
        if not names or not isinstance(parameters, dict):
            return parameters, config, []
        declared = [n for n in names if n not in parameters]
        for name in declared:
            parameters[name] = {"description": f"The {name.replace('_', ' ')}."}

        def rewrite(value: Any) -> Any:
            if isinstance(value, str):
                return _BARE_PLACEHOLDER.sub(
                    lambda m: f"{{{{source.{m.group(2)}}}}}" if m.group(2) in names else m.group(0), value
                )
            if isinstance(value, dict):
                return {k: rewrite(v) for k, v in value.items()}
            if isinstance(value, list):
                return [rewrite(v) for v in value]
            return value

        return parameters, rewrite(config), declared

    def finalize(self, summary: str = "") -> Dict[str, Any]:
        errors = blocking(self.new_issues()) if self.origin == ORIGIN_CANVAS else blocking(self.issues())
        if errors:
            listing = "\n".join(f"- {self.describe_issue(i)}" for i in errors)
            raise DraftError(
                f"The workflow cannot be finalized while these errors remain:\n{listing}\n"
                f"Fix them and call finalize_workflow again."
            )
        if self.needs_test:
            raise DraftError(
                "The workflow has changed since it was last run. Call test_workflow with a message a "
                "real user would send, check that the response is what the person asked for, fix what "
                "is wrong, and then call finalize_workflow."
            )
        self.status = STATUS_READY
        self.summary = (summary or "").strip()
        message = "Workflow finalized. Tell the user what you built or changed in one or two sentences."
        warnings = [i for i in self.new_issues() if i.severity == "warning"]
        if warnings:
            listing = "\n".join(f"- {self.describe_issue(i)}" for i in warnings)
            message += f"\nIt still has warnings; fix them first if they are mistakes:\n{listing}"
        return {"message": message}

    def ask(self, question: Any, options: Any, recommended: Any = None) -> str:
        """
        Record a question for the person, with the answers they can click. The
        reply tells the agent to end its turn: nothing is built until they answer.
        """
        text = " ".join(str(question or "").split())
        if not text:
            raise DraftError("ask_user needs the question text.")
        choices = options
        if isinstance(choices, str):
            try:
                choices = json.loads(choices)
            except (ValueError, TypeError):
                choices = [part.strip() for part in choices.split("|")]
        if not isinstance(choices, list):
            raise DraftError("ask_user options must be a JSON array of 2 to 4 short answers.")
        cleaned: List[str] = []
        for choice in choices:
            label = " ".join(str(choice or "").split())[:MAX_OPTION_CHARS]
            if label and label.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(label)
        if not 2 <= len(cleaned) <= MAX_OPTIONS:
            raise DraftError(f"ask_user needs 2 to {MAX_OPTIONS} different options; got {len(cleaned)}.")
        picked = " ".join(str(recommended or "").split())
        match = next((c for c in cleaned if c.lower() == picked.lower()), None) if picked else None
        self.question = {"question": text, "options": cleaned, "recommended": match}
        return (
            "Question recorded; the person sees the options as buttons and can type their own answer. "
            "End your turn now: reply with the question in one sentence and nothing else. Do not list "
            "the options and do not change the workflow until they answer."
        )

    def apply_defaults(self, defaults: Dict[str, Any]) -> None:
        """Fill tenant defaults (the LLM provider) into nodes that still lack them."""
        self.defaults.update({k: v for k, v in (defaults or {}).items() if v})
        provider_id = self.defaults.get("providerId")
        if not provider_id:
            return
        for node in self.nodes:
            data = node.get("data") or {}
            if node.get("type") in PROVIDER_NODE_TYPES and not data.get("providerId"):
                data["providerId"] = provider_id

    # ── Views ─────────────────────────────────────────────────────────────

    def _render_value(self, key: str, value: Any, limit: int, preview: int) -> str:
        if catalog.is_secret_key(key) and value not in (None, "", [], {}):
            return SECRET_PLACEHOLDER
        if isinstance(value, str):
            text = self._with_aliases(value)
            if len(text) > limit:
                head = text[:preview].replace("\n", " ")
                return f"<{len(text)} chars: {json.dumps(head + '…', ensure_ascii=False)}>"
            return json.dumps(text, ensure_ascii=False)
        text = self._with_aliases(json.dumps(value, ensure_ascii=False))
        if len(text) > limit:
            return f"<{len(text)} chars: {text[:preview]}…>"
        return text

    def _visible_config(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Config worth showing: values that differ from the node's defaults."""
        data = node.get("data") or {}
        defaults = catalog.entry(node["type"])["defaultData"] if catalog.is_known(node.get("type", "")) else {}
        visible = {}
        for key, value in data.items():
            if key in catalog.NON_CONFIG_KEYS or key in ("name", "deactivated"):
                continue
            if value in (None, "", [], {}) or defaults.get(key) == value:
                continue
            if node.get("type") == "toolBuilderNode" and key in TOOL_PLUMBING_KEYS:
                continue
            visible[key] = value
        if node.get("type") == "toolBuilderNode" and data.get("inputSchema"):
            visible["parameters"] = sorted(data["inputSchema"])
        return visible

    def render_outline(self) -> str:
        nodes = [n for n in self.nodes if n.get("type") not in VISUAL_NODE_TYPES]
        if not nodes:
            return "WORKFLOW (empty): no nodes yet. Start with a chatInputNode."

        lines = [f"WORKFLOW — {len(nodes)} nodes, {len(self.edges)} connections"]
        if self.starter_cleared and self.revision == self._revision_at_load():
            lines.append(
                "This is a new, empty agent: only the Start node and an output exist, not yet connected. "
                "Build the workflow between them, e.g. add_node(..., connect_from=<Start id>, "
                "connect_to=<output id>)."
            )
        if self.selected_node_id and self.selected_node_id in self.aliases:
            lines.append(f"Selected in the canvas: {self.alias(self.selected_node_id)}")
        if self.last_user_test:
            lines.append(
                "The person has test-run this workflow on the canvas. If they say it is not working, "
                "call get_last_test_run to see exactly what they saw."
            )
        lines.append("Nodes:")
        for node in nodes:
            data = node.get("data") or {}
            config = " ".join(
                f"{key}={self._render_value(key, value, OUTLINE_STRING_LIMIT, OUTLINE_PREVIEW)}"
                for key, value in self._visible_config(node).items()
            )
            off = " [deactivated]" if data.get("deactivated") else ""
            line = f"{self.alias(node['id'])} {node.get('type')} \"{data.get('name', '')}\"{off}"
            lines.append(f"{line} {config}".rstrip())
        lines.append("Connections:")
        if self.edges:
            lines.extend(self._edge_text(e) for e in self.edges)
        else:
            lines.append("(none)")

        issues = self.issues()
        baseline = set(self.baseline_keys)
        shown = [i for i in issues if i.severity != "setup"]
        if shown:
            lines.append("Issues:")
            for issue in shown:
                tag = " (was already there)" if issue.key in baseline else ""
                lines.append(f"- {self.describe_issue(issue)}{tag}")
        setup = [i for i in issues if i.severity == "setup"]
        if setup:
            lines.append(
                f"Setup the user completes in the canvas ({len(setup)}): "
                + "; ".join(sorted({f"{self.alias(i.node_id)}.{i.field}" for i in setup}))
            )
        return "\n".join(lines)

    def render_node(self, ref: str) -> str:
        node = self.find(ref)
        data = node.get("data") or {}
        alias = self.alias(node["id"])
        lines = [f"{alias} {node.get('type')} \"{data.get('name', '')}\""]
        if catalog.is_known(node.get("type", "")):
            lines.append(f"Handles ({catalog.describe_handles(node['type'], data)})")
        lines.append("Config:")
        for key, value in data.items():
            if key in catalog.NON_CONFIG_KEYS or key == "name":
                continue
            lines.append(f"- {key}: {self._render_value(key, value, NODE_DETAIL_STRING_LIMIT, 400)}")
        incoming = [self._edge_text(e) for e in self.edges if e["target"] == node["id"]]
        outgoing = [self._edge_text(e) for e in self.edges if e["source"] == node["id"]]
        lines.append(f"In: {'; '.join(incoming) or 'none'}")
        lines.append(f"Out: {'; '.join(outgoing) or 'none'}")
        return "\n".join(lines)

    def to_canvas(self) -> Dict[str, Any]:
        """Nodes and edges ready for the canvas, with positions for anything new."""
        nodes, edges = deepcopy(self.nodes), deepcopy(self.edges)
        if self.origin == ORIGIN_NEW:
            nodes = auto_layout(nodes, edges)
        elif self.new_node_ids:
            nodes = place_new_nodes(nodes, edges, set(self.new_node_ids))
        return {"nodes": nodes, "edges": edges}

    def to_spec(self) -> Dict[str, Any]:
        """
        The draft in the simplified specification format ``build_workflow_from_spec``
        accepts: enough to rebuild it elsewhere, and small enough to preview.
        """
        workflow = []
        for node in self.nodes:
            if node.get("type") in VISUAL_NODE_TYPES:
                continue
            data = node.get("data") or {}
            defaults = (
                catalog.entry(node["type"])["defaultData"] if catalog.is_known(node.get("type", "")) else {}
            )
            config = {
                key: value for key, value in data.items()
                if key not in catalog.NON_CONFIG_KEYS and key != "name" and defaults.get(key) != value
            }
            workflow.append({
                "uniqueId": self.alias(node["id"]),
                "node_name": node.get("type", ""),
                "function_of_node": data.get("name") or node.get("type", ""),
                "config": config,
            })
        edges = [
            {
                "from": self.alias(edge["source"]),
                "to": self.alias(edge["target"]),
                "sourceHandle": edge.get("sourceHandle") or "output",
                "targetHandle": edge.get("targetHandle") or "input",
            }
            for edge in self.edges
        ]
        return {"workflow": workflow, "edges": edges}

    def client_payload(self) -> Dict[str, Any]:
        """What the frontend needs after a turn."""
        issues = self.issues()
        baseline = set(self.baseline_keys)
        return {
            **self.to_canvas(),
            "status": self.status,
            "revision": self.revision,
            "origin": self.origin,
            "summary": self.summary,
            "changes": self.changes,
            "issues": [
                {**i.to_dict(), "message": self._with_aliases(i.message), "pre_existing": i.key in baseline}
                for i in issues
            ],
            "has_errors": any(i.severity == ERROR for i in issues),
            "question": self.question,
        }


# ── Storage ───────────────────────────────────────────────────────────────


async def load_draft(thread_id: str) -> Optional[WorkflowDraft]:
    from app.modules.workflow.agents.memory import ConversationMemory

    payload = await ConversationMemory.get_instance(thread_id=str(thread_id)).get_metadata(DRAFT_METADATA_KEY)
    return WorkflowDraft.from_dict(payload) if payload else None


async def save_draft(thread_id: str, draft: WorkflowDraft) -> None:
    from app.modules.workflow.agents.memory import ConversationMemory

    await ConversationMemory.get_instance(thread_id=str(thread_id)).set_metadata(
        DRAFT_METADATA_KEY, draft.to_dict()
    )
