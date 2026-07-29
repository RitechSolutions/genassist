"""
Shared workflow tool-catalogue resolver.

Walks a workflow graph to find each agent and the tools connected to it, using the
same rule the runtime uses to attach tools (an edge whose ``targetHandle`` contains
"tools"; the edge source is the tool node, the target is the agent). Keeping one
resolver means the catalogue UI, rule validation and legacy-name conversion can
never disagree with what actually runs.

Tool ids match the ids recorded on tool events:
  * single tool node  -> the tool node's id
  * MCP tool          -> "{mcpNodeId}:{toolName}"

Pure and synchronous over a single workflow. Nested-workflow expansion needs to load
other workflows (async, DB), so this module only reports the nested references; the
caller recurses with its own loader and cycle protection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.workflow.agents.base_tool import to_snake_case

MCP_NODE_TYPE = "mcpNode"
WORKFLOW_EXECUTOR_NODE_TYPE = "workflowExecutorNode"
_TOOLS_HANDLE = "tools"


def _nodes(workflow: Any) -> List[Dict[str, Any]]:
    nodes = workflow.get("nodes") if isinstance(workflow, dict) else getattr(workflow, "nodes", None)
    return nodes or []


def _edges(workflow: Any) -> List[Dict[str, Any]]:
    edges = workflow.get("edges") if isinstance(workflow, dict) else getattr(workflow, "edges", None)
    return edges or []


def _node_data(node: Dict[str, Any]) -> Dict[str, Any]:
    return node.get("data") or {}


def _node_label(node: Dict[str, Any]) -> str:
    return _node_data(node).get("name") or f"Node_{node.get('id')}"


def _tools_for_node(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Metadata for the tool(s) a source node exposes (an MCP node exposes many)."""
    node_id = node.get("id")
    node_type = node.get("type", "")
    if node_type == MCP_NODE_TYPE:
        whitelisted = _node_data(node).get("whitelistedTools") or []
        return [
            {"id": f"{node_id}:{name}", "name": name, "label": name, "type": MCP_NODE_TYPE}
            for name in whitelisted
        ]
    label = _node_label(node)
    return [{"id": node_id, "name": to_snake_case(label), "label": label, "type": node_type}]


def _agent_entry(node: Dict[str, Any], workflow_path: List[str]) -> Dict[str, Any]:
    return {
        "id": node.get("id"),
        "label": _node_label(node),
        "type": node.get("type", ""),
        "workflow_path": list(workflow_path),
        "tools": [],
    }


def resolve_agents(workflow: Any, workflow_path: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Return this workflow's agents, each with the tools connected to it."""
    workflow_path = workflow_path or []
    nodes_by_id = {n.get("id"): n for n in _nodes(workflow)}
    agents: Dict[str, Dict[str, Any]] = {}
    seen_tools: Dict[str, set] = {}

    for edge in _edges(workflow):
        target_handle = edge.get("targetHandle") or ""
        if _TOOLS_HANDLE not in target_handle:
            continue
        agent_node = nodes_by_id.get(edge.get("target"))
        tool_node = nodes_by_id.get(edge.get("source"))
        if not agent_node or not tool_node:
            continue

        agent_id = agent_node.get("id")
        if agent_id not in agents:
            agents[agent_id] = _agent_entry(agent_node, workflow_path)
            seen_tools[agent_id] = set()
        for tool in _tools_for_node(tool_node):
            if tool["id"] in seen_tools[agent_id]:
                continue
            seen_tools[agent_id].add(tool["id"])
            agents[agent_id]["tools"].append(tool)

    return list(agents.values())


def nested_workflow_refs(workflow: Any) -> List[Dict[str, Any]]:
    """Executor nodes that run another workflow, for the caller to expand recursively."""
    refs = []
    for node in _nodes(workflow):
        if node.get("type") != WORKFLOW_EXECUTOR_NODE_TYPE:
            continue
        workflow_id = _node_data(node).get("workflowId")
        if workflow_id:
            refs.append({
                "node_id": node.get("id"),
                "label": _node_label(node),
                "workflow_id": str(workflow_id),
            })
    return refs


def _normalize_name(value: Any) -> str:
    return str(value).strip().lower()


def build_tool_index(agents: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Map each tool id/name/label (normalized) to the tool id(s) that use it.

    A name or label shared by several tools maps to several ids; ``resolve_in_index``
    treats that as ambiguous rather than silently choosing the first match.
    """
    index: Dict[str, set] = {}
    for agent in agents:
        for tool in agent["tools"]:
            for key in (tool["id"], tool["name"], tool["label"]):
                if key:
                    index.setdefault(_normalize_name(key), set()).add(tool["id"])
    return {key: sorted(ids) for key, ids in index.items()}


def build_agent_index(agents: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Map each agent id/label (normalized) to the agent id(s) using it."""
    index: Dict[str, set] = {}
    for agent in agents:
        for key in (agent["id"], agent["label"]):
            if key:
                index.setdefault(_normalize_name(key), set()).add(agent["id"])
    return {key: sorted(ids) for key, ids in index.items()}


def resolve_in_index(index: Dict[str, List[str]], value: Optional[str], kind: str = "name") -> Optional[str]:
    """Resolve a legacy name/label/id to a single id, case-insensitively.

    Returns None when the value is unknown; raises ``ValueError`` when it is
    ambiguous (shared by more than one id) instead of picking one.
    """
    if value is None:
        return None
    ids = index.get(_normalize_name(value))
    if not ids:
        return None
    if len(ids) > 1:
        raise ValueError(f"ambiguous {kind} name {value!r}: matches ids {ids}")
    return ids[0]
