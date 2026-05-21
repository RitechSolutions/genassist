"""Validation for synthetic notification ids used by the dashboard feed."""

from __future__ import annotations


NOTIFICATION_ID_PREFIXES: tuple[str, ...] = (
    "conversation_started:",
    "conversation_hostility:",
    "conversation_finalized_hostility:",
    "workflow_failed:",
)


def is_valid_notification_id(notification_id: str) -> bool:
    if not notification_id or len(notification_id) > 255:
        return False
    return any(notification_id.startswith(prefix) for prefix in NOTIFICATION_ID_PREFIXES)


def normalize_notification_ids(notification_ids: list[str]) -> list[str]:
    """Deduplicate while preserving order; drop empty/invalid ids."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in notification_ids:
        nid = (raw or "").strip()
        if not nid or nid in seen or not is_valid_notification_id(nid):
            continue
        seen.add(nid)
        out.append(nid)
        if len(out) >= 500:
            break
    return out
