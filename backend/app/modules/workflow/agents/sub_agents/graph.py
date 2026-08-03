"""Sub-agent topology: build the delegation forest, validate it, fingerprint it"""

import hashlib
import json
import re
import unicodedata
from typing import Any, Dict, List

from app.modules.workflow.agents.base_tool import to_snake_case
from app.modules.workflow.agents.sub_agents.models import (
    DEFAULT_CHILD_TIMEOUT_SECONDS,
    clamp_child_timeout_seconds,
)

SUB_AGENT_SOURCE_HANDLE = "output_sub_agent"
SUB_AGENT_TARGET_HANDLE = "input_sub_agents"
TOOLS_TARGET_HANDLE = "input_tools"
STARTER_SOURCE_HANDLE = "starter_processor"

MAX_DELEGATION_DEPTH = 3
RESERVED_TOOL_NAMES = frozenset({"finish_task", "return_to_parent"})


def child_timeout_seconds(node_data: Dict[str, Any]) -> float:
    return clamp_child_timeout_seconds(node_data.get("timeoutSeconds", DEFAULT_CHILD_TIMEOUT_SECONDS))


class SubAgentTopologyError(ValueError):
    """Raised when a sub-agent wiring is invalid; carries all violations."""

    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__("; ".join(violations))


def sub_agent_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Delegation edges only (child ``output_sub_agent`` -> parent ``input_sub_agents``)."""
    return [e for e in edges if e.get("targetHandle") == SUB_AGENT_TARGET_HANDLE]


def _validate_sub_agent_isolation(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
    sub_ids = {n.get("id") for n in nodes if n.get("type") == "subAgentNode"}
    if not sub_ids:
        return []
    violations: List[str] = []
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if source in sub_ids and edge.get("sourceHandle") != SUB_AGENT_SOURCE_HANDLE:
            violations.append(f"sub-agent '{source}' can only connect through its delegation handle, not the main flow")
        if target in sub_ids and edge.get("targetHandle") not in (SUB_AGENT_TARGET_HANDLE, TOOLS_TARGET_HANDLE):
            violations.append(f"sub-agent '{target}' cannot receive a main-flow connection")
    return violations


def _clamp_tool_name(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name or "")
    folded = "".join(ch for ch in folded if not unicodedata.category(ch).startswith("M"))
    clamped = re.sub(r"[^a-z0-9_]+", "_", to_snake_case(folded))
    return re.sub(r"_+", "_", clamped).strip("_")


def delegation_tool_name(child_name: str) -> str:
    """Runtime name of the tool the parent calls to delegate to this child."""
    return f"request_task_{_clamp_tool_name(child_name)}"


class SubAgentGraph:
    """Parent<->child delegation structure derived from ``input_sub_agents`` edges."""

    def __init__(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        self.nodes_by_id: Dict[str, Dict[str, Any]] = {n["id"]: n for n in nodes}
        self.edges = edges
        self.children_of: Dict[str, List[str]] = {}
        self.parents_of: Dict[str, List[str]] = {}
        for edge in sub_agent_edges(edges):
            child_id, parent_id = edge.get("source"), edge.get("target")
            if not child_id or not parent_id:
                continue
            self.children_of.setdefault(parent_id, []).append(child_id)
            self.parents_of.setdefault(child_id, []).append(parent_id)

    @property
    def has_delegations(self) -> bool:
        return bool(self.parents_of)

    def node_type(self, node_id: str) -> str:
        return self.nodes_by_id.get(node_id, {}).get("type", "")

    def child_mode(self, child_id: str) -> str:
        return self.nodes_by_id.get(child_id, {}).get("data", {}).get("mode", "single_turn")

    def child_name(self, child_id: str) -> str:
        return self.nodes_by_id.get(child_id, {}).get("data", {}).get("name", child_id)

    def descendants(self, node_id: str, _seen: set | None = None) -> List[str]:
        _seen = _seen if _seen is not None else set()
        out: List[str] = []
        for child in self.children_of.get(node_id, []):
            if child in _seen:
                continue
            _seen.add(child)
            out.append(child)
            out.extend(self.descendants(child, _seen))
        return out

    def depth_of(self, child_id: str, _seen: set | None = None) -> int:
        """Delegation hops from a root agent down to this child"""
        _seen = _seen if _seen is not None else set()
        parents = self.parents_of.get(child_id, [])
        if not parents or child_id in _seen:
            return 1
        _seen.add(child_id)
        return 1 + max(self.depth_of(p, _seen) for p in parents)

    def _has_cycle(self) -> bool:
        color: Dict[str, int] = {}

        def visit(node_id: str) -> bool:
            color[node_id] = 1
            for child in self.children_of.get(node_id, []):
                state = color.get(child, 0)
                if state == 1 or (state == 0 and visit(child)):
                    return True
            color[node_id] = 2
            return False

        return any(visit(nid) for nid in self.children_of if color.get(nid, 0) == 0)

    def _parent_tool_names(self, parent_id: str) -> set:
        """Snake-cased names of tools the parent has attached via ``input_tools``."""
        names = set()
        for edge in self.edges:
            if edge.get("targetHandle") == TOOLS_TARGET_HANDLE and edge.get("target") == parent_id:
                src = self.nodes_by_id.get(edge.get("source"), {})
                names.add(to_snake_case(src.get("data", {}).get("name", "")))
        return names

    def _subflow_node_ids(self, tool_builder_id: str) -> set:
        """Nodes reachable inside a tool builder's sub-flow"""
        starts = [
            e["target"]
            for e in self.edges
            if e.get("source") == tool_builder_id and e.get("sourceHandle") == STARTER_SOURCE_HANDLE
        ]
        seen, stack = set(), list(starts)
        while stack:
            nid = stack.pop()
            if nid in seen:
                continue
            seen.add(nid)
            for e in self.edges:
                if e.get("source") != nid:
                    continue
                if e.get("sourceHandle") in (SUB_AGENT_SOURCE_HANDLE,):
                    continue
                if e.get("targetHandle") in (TOOLS_TARGET_HANDLE, SUB_AGENT_TARGET_HANDLE):
                    continue
                stack.append(e["target"])
        return seen

    def _tool_builders_of(self, node_id: str) -> List[str]:
        return [
            e["source"]
            for e in self.edges
            if e.get("targetHandle") == TOOLS_TARGET_HANDLE and e.get("target") == node_id
        ]

    def validate(self) -> None:
        """Raise SubAgentTopologyError with every violation, or return if clean."""
        if not self.has_delegations:
            return

        violations: List[str] = []

        for child_id, parents in self.parents_of.items():
            if self.node_type(child_id) != "subAgentNode":
                violations.append(f"'{child_id}' feeds a sub-agent handle but is not a subAgentNode")
            if len(parents) > 1:
                violations.append(f"sub-agent '{child_id}' is attached to more than one parent")
            for parent_id in parents:
                if self.node_type(parent_id) not in ("agentNode", "subAgentNode"):
                    violations.append(
                        f"sub-agent '{child_id}' must attach to an agent or sub-agent, not "
                        f"'{self.node_type(parent_id)}'"
                    )
                if parent_id == child_id:
                    violations.append(f"sub-agent '{child_id}' cannot attach to itself")

        if self._has_cycle():
            violations.append("sub-agent wiring contains a cycle")
        else:
            for child_id in self.parents_of:
                if self.depth_of(child_id) > MAX_DELEGATION_DEPTH:
                    violations.append(f"sub-agent '{child_id}' exceeds max delegation depth {MAX_DELEGATION_DEPTH}")

        # sibling delegation-name uniqueness + collisions with parent tools / reserved
        for parent_id, children in self.children_of.items():
            parent_tools = self._parent_tool_names(parent_id)
            seen_names: set = set()
            for child_id in children:
                child_name = self.child_name(child_id)
                clamped = _clamp_tool_name(child_name)
                if not clamped:
                    violations.append(f"sub-agent name '{child_name}' must contain at least one letter or number")
                name = delegation_tool_name(child_name)
                if name in seen_names:
                    violations.append(f"duplicate sub-agent name under one parent: '{name}'")
                seen_names.add(name)
                if clamped in RESERVED_TOOL_NAMES:
                    violations.append(f"sub-agent name '{child_name}' is reserved")
                if name in parent_tools:
                    violations.append(f"sub-agent tool '{name}' collides with a parent tool name")

        for child_id in self.parents_of:
            mode = self.child_mode(child_id)
            if mode == "task" and self.children_of.get(child_id):
                violations.append(f"task sub-agent '{child_id}' cannot have its own sub-agents")
            if mode in ("task", "chat") and any(
                self.node_type(p) == "subAgentNode" for p in self.parents_of.get(child_id, [])
            ):
                violations.append(
                    f"persistent (task/chat) sub-agent '{child_id}' must attach to a top-level agent, "
                    "not another sub-agent"
                )
            if mode == "single_turn":
                for desc in self.descendants(child_id):
                    if self.child_mode(desc) != "single_turn":
                        violations.append(f"single_turn sub-agent '{child_id}' cannot contain a persistent sub-agent")
                        break

        violations.extend(self._validate_subflows())

        if violations:
            raise SubAgentTopologyError(violations)

    def _validate_subflows(self) -> List[str]:
        """No HITL inside a child's tools; no task/chat parent inside a tool sub-flow."""
        violations: List[str] = []

        # tool sub-flows that reach a Human-in-the-Loop node can't pause+resume from a child
        for child_id in self.parents_of:
            for tb_id in self._tool_builders_of(child_id):
                if any(self.node_type(nid) == "humanInTheLoopNode" for nid in self._subflow_node_ids(tb_id)):
                    violations.append(f"sub-agent '{child_id}' has a Human-in-the-Loop node in its tools")
                    break

        # a parent inside a tool sub-flow cannot host a task/chat child
        subflow_nodes: set = set()
        for tb_id in {e["source"] for e in self.edges if e.get("sourceHandle") == STARTER_SOURCE_HANDLE}:
            subflow_nodes |= self._subflow_node_ids(tb_id)
        for child_id, parents in self.parents_of.items():
            if self.child_mode(child_id) in ("task", "chat"):
                if any(p in subflow_nodes for p in parents):
                    violations.append(f"task/chat sub-agent '{child_id}' cannot run under a tool sub-flow parent")
        return violations


def validate_sub_agent_topology(nodes: List[Dict[str, Any]] | None, edges: List[Dict[str, Any]] | None) -> None:
    """Check sub-agent isolation whenever a subAgentNode exists, and the full
    delegation topology when there are delegation edges"""
    nodes = nodes or []
    edges = edges or []
    graph = SubAgentGraph(nodes, edges)
    violations = _validate_sub_agent_isolation(nodes, edges)
    if graph.has_delegations:
        try:
            graph.validate()
        except SubAgentTopologyError as e:
            violations.extend(e.violations)
    if violations:
        raise SubAgentTopologyError(violations)


def _normalize_graph_for_fingerprint(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    norm_nodes = []
    for node in nodes:
        data = {k: v for k, v in node.get("data", {}).items() if k != "executionState"}
        norm_nodes.append({"id": node.get("id"), "type": node.get("type"), "data": data})
    norm_nodes.sort(key=lambda n: str(n["id"]))

    norm_edges = [
        {
            "source": e.get("source"),
            "sourceHandle": e.get("sourceHandle"),
            "target": e.get("target"),
            "targetHandle": e.get("targetHandle"),
        }
        for e in edges
    ]
    norm_edges.sort(key=lambda e: (str(e["source"]), str(e["sourceHandle"]), str(e["target"]), str(e["targetHandle"])))
    return {"nodes": norm_nodes, "edges": norm_edges}


def fingerprint(nodes: List[Dict[str, Any]] | None, edges: List[Dict[str, Any]] | None) -> str:
    normalized = _normalize_graph_for_fingerprint(nodes or [], edges or [])
    payload = json.dumps(normalized, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
