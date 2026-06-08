"""
Core utility for building workflows from a structured specification.

This function is used both by the API endpoint and by the pythonCodeNode
in the Workflow Builder Agent's workflow.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.modules.workflow.manage.workflow_manager import WorkflowManager
from app.modules.workflow.builder.layout import auto_layout

logger = logging.getLogger(__name__)


def build_workflow_from_spec(
    spec: Dict[str, Any],
    workflow_name: str,
    workflow_description: str = "",
    user_id: str = "",
    agent_id: str = "",
    workflow_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a complete workflow from a structured specification.

    The spec format supports both the legacy wizard format (linear chains via
    next_node_id) and the enhanced builder format (explicit edges with handles).

    Args:
        spec: The workflow specification. Expected shape:
            {
                "workflow": [
                    {
                        "uniqueId": "1",
                        "node_name": "chatInputNode",
                        "function_of_node": "Chat Input",
                        "config": { ... }  # optional overrides
                    },
                    ...
                ],
                "edges": [  # optional, if absent falls back to linear chain
                    {
                        "from": "1",
                        "to": "2",
                        "sourceHandle": "output",  # optional, defaults to "output"
                        "targetHandle": "input"     # optional, defaults to "input"
                    },
                    ...
                ]
            }
        workflow_name: Name for the workflow
        workflow_description: Description for the workflow
        user_id: Owner user ID
        agent_id: Associated agent ID
        workflow_id: Optional existing workflow ID to update

    Returns:
        Dict with keys: nodes, edges, executionState
    """
    workflow_nodes = spec.get("workflow", [])
    explicit_edges = spec.get("edges", None)

    if not workflow_nodes:
        raise ValueError("Workflow specification must contain at least one node")

    # Create WorkflowManager instance
    wm = WorkflowManager(
        name=workflow_name,
        description=workflow_description,
        user_id=user_id,
        agent_id=agent_id,
        workflow_id=workflow_id,
    )

    # Map uniqueId -> generated UUID for edge resolution
    id_mapping: Dict[str, str] = {}

    # ── Phase 1: Create nodes ─────────────────────────────────────────────
    for index, node_spec in enumerate(workflow_nodes):
        unique_id = str(node_spec.get("uniqueId", str(index + 1)))
        node_type = node_spec.get("node_name", "")
        node_name = node_spec.get("function_of_node", node_type)
        config_overrides = node_spec.get("config", {})

        if not node_type:
            raise ValueError(f"Node at index {index} has no node_name")

        # Generate the full node from type (uses NODE_DIALOG_SCHEMAS defaults)
        full_node = wm._gen_node_from_type(node_type, node_name, index)
        node_id = full_node["id"]
        id_mapping[unique_id] = node_id

        # Add node to workflow
        wm.add_node(full_node)

        # Apply config overrides
        if config_overrides:
            wm.update_node_properties(node_id, config_overrides)

    # ── Phase 2: Create edges ─────────────────────────────────────────────
    if explicit_edges is not None:
        # Enhanced format: use explicit edge definitions
        for edge_spec in explicit_edges:
            from_id = str(edge_spec.get("from", ""))
            to_id = str(edge_spec.get("to", ""))
            source_handle = edge_spec.get("sourceHandle", "output")
            target_handle = edge_spec.get("targetHandle", "input")

            source_node_id = id_mapping.get(from_id)
            target_node_id = id_mapping.get(to_id)

            if not source_node_id:
                logger.warning(f"Edge source uniqueId '{from_id}' not found, skipping")
                continue
            if not target_node_id:
                logger.warning(f"Edge target uniqueId '{to_id}' not found, skipping")
                continue

            wm.add_edge(source_node_id, target_node_id, source_handle, target_handle)
    else:
        # Legacy wizard format: infer linear chain from next_node_id or order
        for index, node_spec in enumerate(workflow_nodes):
            unique_id = str(node_spec.get("uniqueId", str(index + 1)))
            next_id = node_spec.get("next_node_id")

            if next_id is not None:
                source_node_id = id_mapping.get(unique_id)
                target_node_id = id_mapping.get(str(next_id))
                if source_node_id and target_node_id:
                    wm.add_edge(source_node_id, target_node_id)
            elif index < len(workflow_nodes) - 1:
                # Fall back to sequential ordering
                current_uid = str(node_spec.get("uniqueId", str(index + 1)))
                next_uid = str(
                    workflow_nodes[index + 1].get("uniqueId", str(index + 2))
                )
                source_node_id = id_mapping.get(current_uid)
                target_node_id = id_mapping.get(next_uid)
                if source_node_id and target_node_id:
                    wm.add_edge(source_node_id, target_node_id)

    # ── Phase 3: Auto-layout ──────────────────────────────────────────────
    workflow_dict = wm.to_dict()
    workflow_dict["nodes"] = auto_layout(
        workflow_dict["nodes"], workflow_dict["edges"]
    )

    # ── Phase 4: Generate execution state ─────────────────────────────────
    execution_state = {
        "source": {"message": None},
        "session": {"message": None},
        "nodeOutputs": {},
    }

    return {
        "nodes": workflow_dict["nodes"],
        "edges": workflow_dict["edges"],
        "executionState": execution_state,
    }
