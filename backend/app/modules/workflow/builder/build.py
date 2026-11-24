"""
Build a complete workflow from a structured specification.

The specification is the simplified format (nodes with ``uniqueId`` /
``node_name`` / ``function_of_node`` / ``config`` and optional explicit
``edges``). It is assembled through ``WorkflowDraft``, so every node type,
config key and handle is checked against the node catalog, and the finished
graph is validated before anything is returned. An invalid specification raises
``SpecValidationError`` carrying a list of actionable issues; nothing invalid
is ever handed back to be saved.
"""

import logging
from typing import Any, Dict, List, Optional

from app.modules.workflow.builder.draft import DraftError, WorkflowDraft
from app.modules.workflow.builder.validation import blocking

logger = logging.getLogger(__name__)

EMPTY_EXECUTION_STATE = {
    "source": {"message": None},
    "session": {"message": None},
    "nodeOutputs": {},
}


class SpecValidationError(ValueError):
    """The specification cannot be built. ``issues`` lists what to fix."""

    def __init__(self, issues: List[Dict[str, Any]]):
        self.issues = issues
        super().__init__("; ".join(issue["message"] for issue in issues) or "Invalid workflow specification")


def build_workflow_from_spec(
    spec: Dict[str, Any],
    workflow_name: str = "",
    workflow_description: str = "",
    user_id: str = "",
    agent_id: str = "",
    workflow_id: Optional[str] = None,
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Args:
        spec: ``{"workflow": [{"uniqueId", "node_name", "function_of_node", "config"?}, ...],
                 "edges"?: [{"from", "to", "sourceHandle"?, "targetHandle"?}, ...]}``.
            Without ``edges`` the nodes are chained in order (or by ``next_node_id``).
        defaults: tenant defaults filled into new nodes (``providerId``).

    Returns:
        Dict with keys: nodes, edges, executionState

    Raises:
        SpecValidationError: the spec has unknown node types, config keys or
            handles, or the resulting graph is not a valid workflow.
    """
    workflow_nodes = spec.get("workflow") or []
    explicit_edges = spec.get("edges")

    if not workflow_nodes:
        raise SpecValidationError([
            {"node": None, "field": "workflow", "message": "Workflow specification must contain at least one node"}
        ])

    draft = WorkflowDraft()
    draft.defaults = dict(defaults or {})
    errors: List[Dict[str, Any]] = []
    id_mapping: Dict[str, str] = {}
    failed_nodes: set = set()

    for index, node_spec in enumerate(workflow_nodes):
        unique_id = str(node_spec.get("uniqueId", index + 1))
        node_type = node_spec.get("node_name", "")
        if not node_type:
            errors.append({"node": unique_id, "field": "node_name", "message": f"Node {unique_id} has no node_name"})
            continue
        try:
            added = draft.add_node(node_type, node_spec.get("function_of_node"), node_spec.get("config"))
            id_mapping[unique_id] = added["node_id"]
        except DraftError as exc:
            failed_nodes.add(unique_id)
            errors.append({"node": unique_id, "field": "config", "message": f"Node {unique_id}: {exc}"})

    def connect(from_id: str, to_id: str, source_handle: Optional[str], target_handle: Optional[str]) -> None:
        source, target = id_mapping.get(from_id), id_mapping.get(to_id)
        if not source or not target:
            missing = from_id if not source else to_id
            if missing in failed_nodes:
                return  # already reported when the node itself was rejected
            errors.append({
                "node": missing, "field": "edges",
                "message": f"Edge {from_id} -> {to_id} references node {missing}, which was not created",
            })
            return
        try:
            draft.connect(source, target, source_handle, target_handle)
        except DraftError as exc:
            errors.append({"node": from_id, "field": "edges", "message": f"Edge {from_id} -> {to_id}: {exc}"})

    if explicit_edges is not None:
        for edge_spec in explicit_edges:
            connect(
                str(edge_spec.get("from", "")),
                str(edge_spec.get("to", "")),
                edge_spec.get("sourceHandle"),
                edge_spec.get("targetHandle"),
            )
    else:
        # Wizard format: follow next_node_id, otherwise chain the nodes in order.
        for index, node_spec in enumerate(workflow_nodes):
            unique_id = str(node_spec.get("uniqueId", index + 1))
            next_id = node_spec.get("next_node_id")
            if next_id is None and index < len(workflow_nodes) - 1:
                next_id = workflow_nodes[index + 1].get("uniqueId", index + 2)
            if next_id is not None:
                connect(unique_id, str(next_id), None, None)

    if not errors:
        reverse = {node_id: unique_id for unique_id, node_id in id_mapping.items()}
        errors.extend(
            {"node": reverse.get(issue.node_id), "field": issue.field, "message": issue.message}
            for issue in blocking(draft.issues())
        )
    if errors:
        raise SpecValidationError(errors)

    canvas = draft.to_canvas()
    return {
        "nodes": canvas["nodes"],
        "edges": canvas["edges"],
        "executionState": dict(EMPTY_EXECUTION_STATE),
    }
