"""
Canonical node-failure contract for the workflow engine.

Historically every node signalled "I could not do my job" in its own ad-hoc way:
some raised, most returned an error dict, and those dicts used ~20 incompatible
shapes (`{"error": ...}`, `{"status": 500, "data": {"error": ...}}`,
`{"status": "error", "output": ...}`, `{"success": False, ...}`, a bare `None`,
etc.). Because there was no single shape to check, the engine could never tell a
successful run from one where a node silently failed, so every run reported
"success".

This module introduces ONE way to signal a recoverable node failure —
``node_failure(...)`` — plus ``is_node_failure(...)`` which recognises both the
canonical envelope and the common legacy shapes (so partially-migrated nodes are
still detected). Detection is intentionally *additive*: a detected failure is
recorded (per-node status + run-level ``has_failures``) but the workflow keeps
flowing with the node's partial/last output, so the user still gets a response.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Marker key stamped onto the canonical failure envelope. Chosen to never collide
# with a real node output field.
NODE_FAILURE_MARKER = "__node_failed__"


def node_failure(
    message: str,
    *,
    code: Optional[Any] = None,
    details: Optional[Dict[str, Any]] = None,
    output: Any = None,
) -> Dict[str, Any]:
    """Build the canonical failure envelope a node returns to signal it did not
    complete its job, while letting the workflow continue.

    Args:
        message: Human-readable reason the node failed (shown to admins / agents).
        code: Optional machine code (e.g. an HTTP status) for context.
        details: Optional structured extra context.
        output: The flow-compatible value downstream nodes / the final response
            should receive (e.g. an agent's apology message). ``None`` means the
            node produced no usable output — downstream sees nothing, exactly as
            before, but the failure is now recorded.

    The engine (``BaseNode.execute``) detects this envelope, records the failure,
    stores ``output`` as the node output for downstream flow, and returns the raw
    envelope so a caller using the node AS A TOOL can also detect the failure.
    """
    return {
        NODE_FAILURE_MARKER: True,
        "error": message,
        "code": code,
        "details": details or {},
        "output": output,
    }


def _extract_error_message(result: Dict[str, Any]) -> str:
    """Best-effort human-readable message from a legacy error dict."""
    # Nested {"data": {"error": ...}} (api/jira/slack/gmail/whatsapp/zendesk/...)
    data = result.get("data")
    if isinstance(data, dict) and data.get("error"):
        return str(data["error"])
    # Top-level {"error": ...} (most nodes) / {"errors": [...]} (train_preprocess)
    if result.get("error"):
        return str(result["error"])
    if result.get("errors"):
        return str(result["errors"])
    # {"status": "error", "output": ...} (mcp execution errors)
    if result.get("status") == "error" and result.get("output"):
        return str(result["output"])
    code = result.get("status")
    return f"Node reported a failure (status={code})" if code is not None else "Node reported a failure"


def is_node_failure(result: Any) -> Optional[Dict[str, Any]]:
    """Return failure info if ``result`` signals a node failure, else ``None``.

    Recognises:
      * the canonical ``node_failure(...)`` envelope (precise), and
      * conservative legacy signals from not-yet-migrated nodes:
          - an integer ``status`` >= 400 (HTTP-style error),
          - a string ``status == "error"``,
          - ``success is False``.

    The returned dict always has ``error`` (str) and ``output`` (the value that
    should flow downstream). Kept conservative on purpose: bare ``{"error": ...}``
    shapes without a status are NOT auto-detected here (they can false-positive on
    pass-through API payloads); those nodes are detected once migrated to
    ``node_failure``.
    """
    if not isinstance(result, dict):
        return None

    # Canonical envelope — precise.
    if result.get(NODE_FAILURE_MARKER) is True:
        return {
            "error": result.get("error") or "Node reported a failure",
            "code": result.get("code"),
            "details": result.get("details") or {},
            "output": result.get("output"),
        }

    status = result.get("status")

    # HTTP-style integer status (guard against bool, which is a subclass of int).
    if isinstance(status, int) and not isinstance(status, bool) and status >= 400:
        return {"error": _extract_error_message(result), "code": status, "details": {}, "output": result}

    # String status of "error".
    if status == "error":
        return {"error": _extract_error_message(result), "code": "error", "details": {}, "output": result}

    # `success: False` convention (web_search / web_scraper / html_to_image / ...).
    if result.get("success") is False:
        return {"error": _extract_error_message(result), "code": None, "details": {}, "output": result}

    return None


def strip_failure_marker(value: Any) -> Any:
    """Return ``value`` without the internal failure marker key, in case a raw
    envelope ever reaches serialization. Non-dicts pass through unchanged."""
    if isinstance(value, dict) and NODE_FAILURE_MARKER in value:
        return {k: v for k, v in value.items() if k != NODE_FAILURE_MARKER}
    return value
