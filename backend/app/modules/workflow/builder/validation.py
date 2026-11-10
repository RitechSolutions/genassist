"""
Structural validation of a workflow graph for the Workflow Builder.

Works on the stored workflow shape (React Flow nodes and edges), so the same
checks apply to a draft the builder agent is assembling and to a canvas the
user already has. Every issue names the node, the field and what to do about
it, so the agent can repair it and the UI can show it.

Severities:
- ``error``:   the workflow is wrong; finalizing is blocked.
- ``warning``: suspicious but runnable.
- ``setup``:   something only the user can provide in the canvas (credentials,
               a knowledge base); never blocks the build.
"""

import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from app.modules.workflow.builder import catalog

ERROR = "error"
WARNING = "warning"
SETUP = "setup"

# Canvas-only nodes that never execute.
VISUAL_NODE_TYPES = {"groupNode"}

# Nodes that cannot run until an LLM provider is selected.
PROVIDER_NODE_TYPES = {"agentNode", "subAgentNode", "llmModelNode", "voiceAgentNode"}

# Nodes that hang off an agent instead of sitting in the main flow.
ATTACHMENT_NODE_TYPES = {"subAgentNode", "mcpNode", "workflowBuilderToolsNode"}

# Back-edges a loop node is allowed to receive.
LOOP_BACK_HANDLES = {"input_loop"}

BUILTIN_SESSION_KEYS = {
    "message", "thread_id", "conversation_history", "user_id", "metadata",
    "language", "customer_id", "conversation_id", "agent_id", "workflow_id",
}

# Same shape the engine substitutes (no whitespace inside the braces).
_TEMPLATE_REF = re.compile(r"\{\{([A-Za-z_]\w*)(?:\.([^\s{}]+))?\}\}")

# What a variable path may start with; anything else resolves to nothing at run time.
VARIABLE_ROOTS = {"source", "session", "node_outputs", "direct_input", "webhook", "metadata"}

FILTER_OPERATORS_WITHOUT_VALUE = {"is_empty", "is_not_empty"}

# How much literal text an agent's userPrompt may carry around the variable before
# it is clearly being used for instructions.
USER_PROMPT_LITERAL_LIMIT = 40

# The keys a node's output has, as the node after it sees them in {{source.<key>}}.
# Only shapes the engine fixes are listed; a type missing here is not checked.
SOURCE_SHAPES: Dict[str, Set[str]] = {
    "agentNode": {"message", "steps", "tools_used"},
    "pythonCodeNode": {"result", "output", "errors", "script_error", "error"},
}
# The key a step after that node almost always wants.
SOURCE_HINTS = {"agentNode": "message", "pythonCodeNode": "result"}

# params.get("source.result") / params.get("node_outputs.n3.result") in Python code.
_CODE_PARAM_REF = re.compile(r'params?\.get\(\s*["\']([A-Za-z_]\w*)(?:\.([^"\']+))?["\']')


@dataclass
class Issue:
    code: str
    severity: str
    message: str
    node_id: Optional[str] = None
    field: Optional[str] = None

    @property
    def key(self) -> str:
        """Identity used to tell issues that were already there from new ones."""
        return f"{self.code}|{self.node_id or ''}|{self.field or ''}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def is_attachment_edge(edge: Dict[str, Any]) -> bool:
    return (
        edge.get("sourceHandle") in catalog.ATTACHMENT_SOURCE_HANDLES
        or edge.get("targetHandle") in catalog.ATTACHMENT_TARGET_HANDLES
    )


def is_subflow_edge(edge: Dict[str, Any]) -> bool:
    return edge.get("sourceHandle") == catalog.SUBFLOW_SOURCE_HANDLE


def is_main_edge(edge: Dict[str, Any]) -> bool:
    return not is_attachment_edge(edge) and not is_subflow_edge(edge)


def executable_nodes(nodes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [n for n in nodes if n.get("type") not in VISUAL_NODE_TYPES]


def _node_name(node: Dict[str, Any]) -> str:
    return (node.get("data") or {}).get("name") or node.get("type") or node.get("id", "")


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _source_shape(node: Optional[Dict[str, Any]]) -> Optional[Set[str]]:
    """The output keys of ``node`` when the engine fixes them, else None."""
    if not node:
        return None
    if node.get("type") == "pythonCodeNode" and (node.get("data") or {}).get("unwrap"):
        return None  # unwrap hands the raw return value on
    return SOURCE_SHAPES.get(node.get("type", ""))


def _data_refs(text: str) -> Iterable[tuple]:
    """(root, rest) of every variable in ``text``: {{root.rest}} and params.get("root.rest")."""
    for root, rest in _TEMPLATE_REF.findall(text):
        yield root, rest
    for root, rest in _CODE_PARAM_REF.findall(text):
        yield root, rest


def _iter_strings(value: Any, path: str = "") -> Iterable[tuple]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in catalog.NON_CONFIG_KEYS:
                continue
            yield from _iter_strings(child, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for child in value:
            yield from _iter_strings(child, path)


def _reachable(starts: Iterable[str], adjacency: Dict[str, List[str]]) -> Set[str]:
    seen: Set[str] = set()
    stack = list(starts)
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(adjacency.get(current, []))
    return seen


def find_cycle_edges(node_ids: Iterable[str], adjacency: Dict[str, List[str]]) -> List[tuple]:
    """Back-edges (source, target) that close a cycle, found by iterative DFS."""
    WHITE, GREY, BLACK = 0, 1, 2
    color: Dict[str, int] = defaultdict(int)
    back_edges: List[tuple] = []

    for root in node_ids:
        if color[root] != WHITE:
            continue
        color[root] = GREY
        stack = [(root, iter(adjacency.get(root, [])))]
        while stack:
            current, children = stack[-1]
            advanced = False
            for child in children:
                if color[child] == WHITE:
                    color[child] = GREY
                    stack.append((child, iter(adjacency.get(child, []))))
                    advanced = True
                    break
                if color[child] == GREY:
                    back_edges.append((current, child))
            if not advanced:
                color[current] = BLACK
                stack.pop()
    return back_edges


def validate_workflow(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Issue]:
    issues: List[Issue] = []
    exec_nodes = executable_nodes(nodes)
    by_id = {n["id"]: n for n in exec_nodes}

    def add(code: str, severity: str, message: str, node: Optional[Dict] = None, field: Optional[str] = None):
        issues.append(Issue(code, severity, message, node["id"] if node else None, field))

    if not exec_nodes:
        return [Issue("empty_workflow", ERROR, "The workflow has no nodes yet.")]

    # ── Node types ────────────────────────────────────────────────────────
    known = {}
    for node in exec_nodes:
        if catalog.is_known(node.get("type", "")):
            known[node["id"]] = node
        else:
            add("unknown_node_type", ERROR, catalog.unknown_type_message(node.get("type", "")), node, "type")

    # ── Edges: endpoints, handles, compatibility ──────────────────────────
    valid_edges: List[Dict[str, Any]] = []
    seen_edges: Set[tuple] = set()
    for edge in edges:
        source = by_id.get(edge.get("source"))
        target = by_id.get(edge.get("target"))
        if not source or not target:
            issues.append(Issue(
                "edge_unknown_node", ERROR,
                f"A connection references a node that does not exist "
                f"({edge.get('source')} -> {edge.get('target')}). Remove it.",
                (source or target or {}).get("id"), "edge",
            ))
            continue

        source_handle = edge.get("sourceHandle") or "output"
        target_handle = edge.get("targetHandle") or "input"
        signature = (source["id"], source_handle, target["id"], target_handle)
        if signature in seen_edges:
            add("duplicate_edge", WARNING,
                f"'{_node_name(source)}' is connected to '{_node_name(target)}' twice on the same handles.",
                source, f"edge.{source_handle}")
            continue
        seen_edges.add(signature)

        ok = True
        if source["id"] in known:
            outputs = catalog.handle_ids(source["type"], source.get("data"), "source")
            if source_handle not in outputs:
                add("unknown_source_handle", ERROR,
                    f"'{_node_name(source)}' ({source['type']}) has no output handle '{source_handle}'. "
                    f"Available: {', '.join(outputs) or 'none (this node has no outputs)'}.",
                    source, f"edge.{source_handle}")
                ok = False
        if target["id"] in known:
            inputs = catalog.handle_ids(target["type"], target.get("data"), "target")
            if target_handle not in inputs:
                add("unknown_target_handle", ERROR,
                    f"'{_node_name(target)}' ({target['type']}) has no input handle '{target_handle}'. "
                    f"Available: {', '.join(inputs) or 'none (this node has no inputs)'}.",
                    target, f"edge.{target_handle}")
                ok = False
        if ok and source["id"] in known and target["id"] in known:
            source_kind = catalog.handle_compatibility(source["type"], source.get("data"), source_handle)
            target_kind = catalog.handle_compatibility(target["type"], target.get("data"), target_handle)
            special = {"tools", "sub_agents"}
            if (source_kind in special or target_kind in special) and source_kind != target_kind:
                add("incompatible_handles", ERROR,
                    f"'{_node_name(source)}'.{source_handle} ({source_kind}) cannot connect to "
                    f"'{_node_name(target)}'.{target_handle} ({target_kind}). Tool handles connect only to "
                    f"input_tools, sub-agent handles only to input_sub_agents.",
                    source, f"edge.{source_handle}")
                ok = False
        if ok:
            valid_edges.append({**edge, "sourceHandle": source_handle, "targetHandle": target_handle})

    main_edges = [e for e in valid_edges if is_main_edge(e)]
    main_children: Dict[str, List[str]] = defaultdict(list)
    incoming_main: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for edge in main_edges:
        main_children[edge["source"]].append(edge["target"])
        incoming_main[edge["target"]].append(edge)

    # ── Entry and output ──────────────────────────────────────────────────
    entries = [n for n in exec_nodes if n.get("type") in catalog.ENTRY_NODE_TYPES]
    chat_inputs = [n for n in entries if n["type"] == "chatInputNode"]
    if not entries:
        add("no_entry_node", ERROR,
            "The workflow has no entry point. Add a chatInputNode (or a webhookTriggerNode) and start the flow from it.")
    if len(chat_inputs) > 1:
        for extra in chat_inputs[1:]:
            add("multiple_chat_inputs", ERROR,
                "A workflow can have only one chatInputNode. Remove this one.", extra, "type")

    # ── Tool sub-flows and attachments ────────────────────────────────────
    subflow_starts = [e["target"] for e in valid_edges if is_subflow_edge(e)]
    subflow_nodes = _reachable(subflow_starts, main_children)
    attached_to_agent = {e["source"] for e in valid_edges if is_attachment_edge(e)}

    for node in exec_nodes:
        node_type = node.get("type")
        if node_type == "toolBuilderNode":
            outgoing = [e for e in valid_edges if e["source"] == node["id"]]
            if not any(e["sourceHandle"] == "output_tool" for e in outgoing):
                add("tool_not_attached", ERROR,
                    f"Tool '{_node_name(node)}' is not attached to an agent. Connect its output_tool "
                    f"to an agent's input_tools.", node, "edge.output_tool")
            if not any(e["sourceHandle"] == "starter_processor" for e in outgoing):
                add("tool_without_action", WARNING,
                    f"Tool '{_node_name(node)}' does not run anything. Connect its starter_processor "
                    f"to the node it should execute.", node, "edge.starter_processor")
        elif node_type in ATTACHMENT_NODE_TYPES and node["id"] not in attached_to_agent:
            add("attachment_not_attached", ERROR,
                f"'{_node_name(node)}' ({node_type}) is not attached to an agent. Connect it to the agent "
                f"that should use it.", node, "edge")

    # ── Single-input rule ─────────────────────────────────────────────────
    for target_id, incoming in incoming_main.items():
        target = by_id[target_id]
        plain = [e for e in incoming if e["targetHandle"] not in LOOP_BACK_HANDLES]
        by_handle: Dict[str, int] = defaultdict(int)
        for edge in plain:
            by_handle[edge["targetHandle"]] += 1
        if target.get("type") != "aggregatorNode" and any(count > 1 for count in by_handle.values()):
            sources = ", ".join(f"'{_node_name(by_id[e['source']])}'" for e in plain)
            add("multiple_inputs", ERROR,
                f"'{_node_name(target)}' receives {len(plain)} incoming connections ({sources}). A node accepts "
                f"one input: give each branch its own node, or merge the branches with an aggregatorNode first.",
                target, "edge.input")

    # ── Unconditional fan-out ─────────────────────────────────────────────
    # One output wired to several nodes runs all of them on every message. That is
    # only meaningful when the branches are merged again; otherwise it is a branch
    # the builder meant to be conditional.
    by_output: Dict[tuple, List[str]] = defaultdict(list)
    for edge in main_edges:
        if edge["targetHandle"] not in LOOP_BACK_HANDLES:
            by_output[(edge["source"], edge["sourceHandle"])].append(edge["target"])
    for (source_id, _handle), targets in by_output.items():
        if len(targets) < 2 or source_id in subflow_nodes:
            continue
        reach = [_reachable([target], main_children) for target in targets]
        merged = any(
            by_id[node_id].get("type") == "aggregatorNode"
            for node_id in set.intersection(*reach)
        )
        if not merged:
            names = ", ".join(f"'{_node_name(by_id[t])}'" for t in targets)
            add("parallel_branches", ERROR,
                f"'{_node_name(by_id[source_id])}' is connected to {len(targets)} nodes at once ({names}), "
                f"so all of them run on every message and the user can get several replies. To choose "
                f"one path, put a routerNode or switchNode there and connect each branch to one of its "
                f"outputs. Remove any branch that is a leftover.",
                by_id[source_id], "edge.output")

    # ── Cycles ────────────────────────────────────────────────────────────
    acyclic_children: Dict[str, List[str]] = defaultdict(list)
    for edge in main_edges:
        if edge["targetHandle"] not in LOOP_BACK_HANDLES:
            acyclic_children[edge["source"]].append(edge["target"])
    for source_id, target_id in find_cycle_edges(by_id.keys(), acyclic_children):
        add("cycle", ERROR,
            f"The connection '{_node_name(by_id[source_id])}' -> '{_node_name(by_id[target_id])}' creates a loop. "
            f"Remove it.", by_id[source_id], "edge")

    # ── Reachability and dead ends ────────────────────────────────────────
    reachable = _reachable([n["id"] for n in entries], main_children)
    off_flow = subflow_nodes | attached_to_agent | {
        n["id"] for n in exec_nodes if n.get("type") in ATTACHMENT_NODE_TYPES | {"toolBuilderNode"}
    }
    if entries:
        for node in exec_nodes:
            if node["id"] in reachable or node["id"] in off_flow:
                continue
            add("unreachable_node", ERROR,
                f"'{_node_name(node)}' is not connected to the flow, so it never runs. Connect the step "
                f"before it to it, or remove it if it is a leftover.",
                node, "edge")

    if chat_inputs:
        chat_reach = _reachable([chat_inputs[0]["id"]], main_children)
        if not any(by_id[i].get("type") in catalog.OUTPUT_NODE_TYPES for i in chat_reach):
            add("no_output_node", ERROR,
                "Nothing sends a reply to the user. End the flow in a chatOutputNode.", chat_inputs[0], "edge")
        for node_id in chat_reach:
            node = by_id[node_id]
            if node.get("type") in catalog.OUTPUT_NODE_TYPES or node_id not in known:
                continue
            has_output_handle = bool(catalog.handle_ids(node["type"], node.get("data"), "source"))
            if has_output_handle and not main_children.get(node_id):
                add("dead_end", ERROR,
                    f"The branch ending at '{_node_name(node)}' never reaches a chatOutputNode, so the user "
                    f"gets no reply on that path. Connect it to a chatOutputNode.", node, "edge.output")

    # ── Config ────────────────────────────────────────────────────────────
    session_keys = set(BUILTIN_SESSION_KEYS)
    for node in exec_nodes:
        data = node.get("data") or {}
        if node.get("type") in catalog.ENTRY_NODE_TYPES:
            session_keys |= set((data.get("inputSchema") or {}).keys())
            session_keys |= {m.get("name") for m in data.get("fieldMappings") or [] if isinstance(m, dict)}
        if node.get("type") == "setStateNode":
            session_keys |= {s.get("key") for s in data.get("states") or [] if isinstance(s, dict)}
    session_keys.discard(None)

    for node in known.values():
        data = node.get("data") or {}
        node_type = node["type"]

        smart = str(data.get("smartModeEnabled")).lower() == "true"
        for field in catalog.REQUIRED_CONFIG.get(node_type, []):
            if smart and field in ("first_value",):
                continue
            if _is_empty(data.get(field)):
                add("missing_required_config", ERROR,
                    f"'{_node_name(node)}' ({node_type}) needs a value for '{field}'.", node, field)

        for field in catalog.PLACEHOLDER_FIELDS.get(node_type, []):
            default = catalog.entry(node_type)["defaultData"].get(field)
            if default and data.get(field) == default:
                add("placeholder_config", ERROR,
                    f"'{_node_name(node)}' ({node_type}) still has the example {field} it was created "
                    f"with, so it does nothing useful. Write its real {field}, or remove the node if it "
                    f"is a leftover.", node, field)

        if node_type == "filterNode":
            operator = data.get("operator") or "equal"
            if operator not in FILTER_OPERATORS_WITHOUT_VALUE and _is_empty(data.get("value")):
                add("missing_required_config", ERROR,
                    f"Filter '{_node_name(node)}' compares `field` with operator '{operator}' but has no "
                    f"`value` to compare against.", node, "value")

        if node_type == "agentNode":
            user_prompt = str(data.get("userPrompt") or "")
            literal = _TEMPLATE_REF.sub("", user_prompt).strip()
            if len(literal) > USER_PROMPT_LITERAL_LIMIT:
                add("instructions_in_user_prompt", ERROR,
                    f"'{_node_name(node)}'.userPrompt contains instructions. userPrompt is only the "
                    f"message the agent receives, normally just {{{{session.message}}}}; everything "
                    f"about how the agent should behave belongs in systemPrompt.", node, "userPrompt")

        if node_type == "switchNode":
            cases = data.get("cases") or []
            if not cases:
                add("switch_without_cases", ERROR,
                    f"Switch '{_node_name(node)}' has no cases. Set `cases` to a list of {{label, value}}.",
                    node, "cases")
            if not smart and _is_empty(data.get("switchValue")):
                add("missing_required_config", ERROR,
                    f"Switch '{_node_name(node)}' needs `switchValue`, the value compared against each case.",
                    node, "switchValue")

        setup_candidates = set(data)
        if node_type in PROVIDER_NODE_TYPES:
            setup_candidates.add("providerId")
        for key in sorted(setup_candidates):
            if key in catalog.SETUP_KEYS and _is_empty(data.get(key)):
                if key == "providerId" and node_type in ("routerNode", "switchNode") and not smart:
                    continue
                if key == "providerId" and node_type == "sqlNode":
                    continue
                add("needs_setup", SETUP,
                    f"'{_node_name(node)}' needs '{key}' to be selected in the canvas.", node, key)

        placeholders = {
            field for field in catalog.PLACEHOLDER_FIELDS.get(node_type, [])
            if data.get(field) == catalog.entry(node_type)["defaultData"].get(field)
        }
        for path, text in _iter_strings(data):
            if path in placeholders:
                continue  # already reported as a placeholder; its example variables are noise
            for root, rest in _TEMPLATE_REF.findall(text):
                if root not in VARIABLE_ROOTS:
                    written = f"{root}.{rest}" if rest else root
                    add("unknown_variable", ERROR,
                        f"'{_node_name(node)}'.{path} uses {{{{{written}}}}}, which is not a valid variable "
                        f"and will be empty at run time. A variable is a full path starting with source, "
                        f"session or node_outputs, for example {{{{source.result.{written.split('.')[-1]}}}}} "
                        f"for a value returned by the previous pythonCodeNode.", node, path)
                    continue
                if not rest:
                    continue
                if root == "node_outputs":
                    referenced = rest.split(".")[0]
                    if referenced not in by_id:
                        add("unknown_node_reference", ERROR,
                            f"'{_node_name(node)}'.{path} references the output of a node that does not exist "
                            f"({{{{node_outputs.{referenced}…}}}}).", node, path)
                elif root == "session":
                    key = rest.split(".")[0]
                    if key not in session_keys:
                        add("unknown_session_variable", WARNING,
                            f"'{_node_name(node)}'.{path} reads {{{{session.{key}}}}}, which nothing defines. "
                            f"Declare it in the Chat Input inputSchema or write it with a setStateNode.",
                            node, path)
                elif root == "source":
                    if (
                        node["id"] not in subflow_nodes
                        and not incoming_main.get(node["id"])
                        and node_type not in ("toolBuilderNode", "subAgentNode")
                    ):
                        add("source_without_input", WARNING,
                            f"'{_node_name(node)}'.{path} reads {{{{source.…}}}} but the node has no incoming "
                            f"connection.", node, path)

        # ── Reading a key the previous node never outputs ─────────────────
        # {{source.result}} after an agent, or params.get("source.data") in code after
        # one, is empty at run time; the builder then rewrites the step blind.
        incoming = incoming_main.get(node["id"]) or []
        previous = by_id.get(incoming[0]["source"]) if len(incoming) == 1 and node["id"] not in subflow_nodes else None
        for path, text in _iter_strings(data):
            if path in placeholders:
                continue
            for root, rest in _data_refs(text):
                if not rest:
                    continue
                if root == "source":
                    producer = previous
                    key, written = rest.split(".")[0], f"source.{rest.split('.')[0]}"
                elif root == "node_outputs":
                    parts = rest.split(".")
                    if len(parts) < 2:
                        continue
                    producer, key = by_id.get(parts[0]), parts[1]
                    written = f"node_outputs.{parts[0]}.{key}"
                else:
                    continue
                shape = _source_shape(producer)
                if shape is None or key in shape:
                    continue
                hint = SOURCE_HINTS.get(producer.get("type", ""), sorted(shape)[0])
                base = written.rsplit(".", 1)[0]
                # Ids are shown to the builder as aliases only inside {{node_outputs.…}}.
                python_hint = f'params.get("{base}.{hint}")' if root == "source" else "the same path in params.get"
                add("source_shape_mismatch", ERROR,
                    f"'{_node_name(node)}'.{path} reads {{{{{written}}}}}, but '{_node_name(producer)}' "
                    f"({producer['type']}) outputs {{{', '.join(sorted(shape))}}}, so that value is always "
                    f"empty. Read {{{{{base}.{hint}}}}} instead (in Python {python_hint}).", node, path)

    return _dedupe(issues)


def _dedupe(issues: List[Issue]) -> List[Issue]:
    seen: Set[tuple] = set()
    unique: List[Issue] = []
    for issue in issues:
        signature = (issue.key, issue.message)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(issue)
    return unique


def blocking(issues: Iterable[Issue]) -> List[Issue]:
    return [i for i in issues if i.severity == ERROR]


def invalid_config_keys(node_type: str, config: Dict[str, Any]) -> List[str]:
    """Config keys the node type does not have (checked when the agent writes config)."""
    if not catalog.is_known(node_type):
        return []
    allowed = catalog.allowed_config_keys(node_type)
    return sorted(key for key in config if key not in allowed)
