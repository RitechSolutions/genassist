"""
Shared utilities for extracting custom workflow attributes from agent responses.

Used by both the real-time capture (chat_as_client_use_case) and the
backfill Celery task to ensure consistent extraction logic.

Only parameters marked as ``useInFilter: true`` in the workflow's chatInputNode
inputSchema (or written by a SetStateNode targeting a filterable key) are
considered custom attributes.
"""

from __future__ import annotations


def is_valid_attr_value(v) -> bool:
    """Return True if the value is a non-empty scalar suitable for a custom attribute."""
    if not isinstance(v, (str, int, float, bool)):
        return False
    if isinstance(v, str) and v.strip().lower() in ("", "null", "none", "undefined"):
        return False
    return True


def get_filterable_keys(workflow_nodes: list[dict] | None) -> set[str]:
    """Return the set of parameter names marked as ``useInFilter`` in the workflow.

    Scans the chatInputNode's ``inputSchema`` for fields with
    ``useInFilter: true``.
    """
    if not workflow_nodes:
        return set()

    keys: set[str] = set()
    for node in workflow_nodes:
        if not isinstance(node, dict):
            continue
        # ReactFlow stores type at root level, inputSchema inside data
        if node.get("type") == "chatInputNode":
            input_schema = node.get("data", {}).get("inputSchema", {})
            if isinstance(input_schema, dict):
                for key, field in input_schema.items():
                    if isinstance(field, dict) and field.get("useInFilter", False):
                        keys.add(key)
            break  # Only one chatInputNode per workflow
    return keys


def _collect_filterable_values(
    node_statuses: dict,
    filterable_keys: set[str],
) -> tuple[dict, dict]:
    """Collect filterable values from chatInputNode and setStateNodes separately.

    Returns:
        (chat_input_values, set_state_values) — two dicts of key→value,
        each containing only keys present in *filterable_keys* with valid values.
    """
    chat_input_values: dict = {}
    set_state_values: dict = {}

    for node_info in node_statuses.values():
        node_type = node_info.get("type")

        if node_type == "chatInputNode":
            output = node_info.get("output", {})
            if isinstance(output, dict):
                for k, v in output.items():
                    if k in filterable_keys and v is not None and is_valid_attr_value(v):
                        chat_input_values[k] = v

        elif node_type == "setStateNode":
            updated = node_info.get("output", {}).get("updated", {})
            if isinstance(updated, dict):
                for k, v in updated.items():
                    if k in filterable_keys and v is not None and is_valid_attr_value(v):
                        set_state_values[k] = v

    return chat_input_values, set_state_values


def extract_custom_attributes_from_state(
    node_statuses: dict,
    workflow_nodes: list[dict] | None = None,
) -> dict:
    """Extract custom attributes from nodeExecutionStatus dict.

    Only includes keys that are marked as ``useInFilter`` in the workflow's
    chatInputNode inputSchema.  SetStateNode values take precedence over
    chatInputNode values for the same key.

    Args:
        node_statuses: The ``nodeExecutionStatus`` dict from the agent response state.
        workflow_nodes: The workflow's ``nodes`` list (from WorkflowModel.nodes)
            used to determine which parameters are filterable.  When *None*,
            no attributes are extracted.
    """
    if not isinstance(node_statuses, dict):
        return {}

    filterable_keys = get_filterable_keys(workflow_nodes)
    if not filterable_keys:
        return {}

    chat_input_values, set_state_values = _collect_filterable_values(
        node_statuses, filterable_keys
    )

    # chatInputNode provides base values; setStateNode overrides take precedence
    return {**chat_input_values, **set_state_values}


def extract_custom_attributes(
    agent_response: dict,
    workflow_nodes: list[dict] | None = None,
) -> dict:
    """Extract custom attributes from a full agent response dict.

    Args:
        agent_response: The full agent response dictionary.
        workflow_nodes: The workflow's ``nodes`` list used to identify
            stateful parameters.
    """
    raw_state = agent_response.get("row_agent_response", {}).get("state", {})
    node_statuses = raw_state.get("nodeExecutionStatus", {})
    return extract_custom_attributes_from_state(node_statuses, workflow_nodes=workflow_nodes)
