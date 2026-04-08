"""
Shared utilities for extracting custom workflow attributes from agent responses.

Used by both the real-time capture (chat_as_client_use_case) and the
backfill Celery task to ensure consistent extraction logic.
"""

# Keys from chatInputNode output or SetStateNode that are internal, not business attributes
INTERNAL_KEYS = frozenset({
    "message", "conversation_history", "node_outputs",
    "session.message", "session.thread_id", "thread_id",
    "error",
})


def is_valid_attr_value(v) -> bool:
    """Return True if the value is a non-empty scalar suitable for a custom attribute."""
    if not isinstance(v, (str, int, float, bool)):
        return False
    if isinstance(v, str) and v.strip().lower() in ("", "null", "none", "undefined"):
        return False
    return True


def extract_custom_attributes_from_state(node_statuses: dict) -> dict:
    """Extract custom attributes from nodeExecutionStatus dict.

    Reads chatInputNode output (validated inputSchema keys only),
    then merges SetStateNode updates (latest wins).
    Filters out internal keys and non-scalar values.
    """
    if not isinstance(node_statuses, dict):
        return {}

    attrs: dict = {}

    # Get custom attributes from chatInputNode output
    for node_info in node_statuses.values():
        if node_info.get("type") == "chatInputNode":
            output = node_info.get("output", {})
            if isinstance(output, dict):
                for k, v in output.items():
                    if k not in INTERNAL_KEYS and v is not None and is_valid_attr_value(v):
                        attrs[k] = v
            break  # Only one chatInputNode per workflow

    # Merge SetStateNode updates (latest wins)
    for node_info in node_statuses.values():
        if node_info.get("type") == "setStateNode":
            updated = node_info.get("output", {}).get("updated", {})
            if isinstance(updated, dict):
                for k, v in updated.items():
                    if k not in INTERNAL_KEYS and v is not None and is_valid_attr_value(v):
                        attrs[k] = v

    return attrs


def extract_custom_attributes(agent_response: dict) -> dict:
    """Extract custom attributes from a full agent response dict."""
    raw_state = agent_response.get("row_agent_response", {}).get("state", {})
    node_statuses = raw_state.get("nodeExecutionStatus", {})
    return extract_custom_attributes_from_state(node_statuses)
