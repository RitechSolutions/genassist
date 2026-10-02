"""Payload-to-input mapping for the Webhook Trigger node.

Kept free of engine and ORM imports so the public ingress route can validate a
delivery (and reject a bad one with 422 before any run row exists) using the
exact same rules the node applies when it runs.

The engine input built here is namespaced: the raw delivery lives under the
``webhook`` key and only the keys the user mapped are set at the top level.
That matters because every top-level key becomes an attribute on
``WorkflowState`` and ``message`` decides whether the turn is written to
conversation memory.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

ENVELOPE_KEY = "webhook"
IDEMPOTENCY_HEADER = "idempotency-key"

# Top-level engine input keys a mapping may never write. They are either set
# by the ingress itself or are attributes of the state object.
RESERVED_INPUT_KEYS = frozenset(
    {
        ENVELOPE_KEY,
        "thread_id",
        "status",
        "output",
        "workflow",
        "workflow_id",
        "memory",
        "session",
        "initial_values",
        "errors",
        "execution_id",
        "node_outputs",
        "is_executing",
    }
)

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MISSING = object()


def get_path(data: Any, path: str) -> Tuple[bool, Any]:
    """Resolve a dotted path over dicts and lists.

    Header names are matched case-insensitively (``headers.X-Foo`` finds
    ``x-foo``); list segments must be integers (``items.0.id``).
    Returns ``(found, value)`` so a legitimately-null value is distinguishable
    from an absent one.
    """
    if not path:
        return False, None
    current = data
    for segment in path.split("."):
        if isinstance(current, dict):
            if segment in current:
                current = current[segment]
                continue
            lowered = segment.lower()
            match = next((k for k in current if isinstance(k, str) and k.lower() == lowered), _MISSING)
            if match is _MISSING:
                return False, None
            current = current[match]
        elif isinstance(current, list):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError):
                return False, None
        else:
            return False, None
    return True, current


def build_envelope(
    *,
    method: str,
    headers: Dict[str, Any],
    query: Dict[str, Any],
    body: Any,
    is_test: bool = False,
    received_at: Optional[str] = None,
) -> Dict[str, Any]:
    """The ``webhook`` object every trigger run receives."""
    return {
        "method": (method or "POST").upper(),
        "headers": {str(k).lower(): v for k, v in (headers or {}).items()},
        "query": dict(query or {}),
        "body": body,
        "received_at": received_at or datetime.now(timezone.utc).isoformat(),
        "is_test": bool(is_test),
    }


def parse_sample_payload(node_data: Dict[str, Any]) -> Any:
    """The node's sample payload as data (it is stored as JSON text or an object)."""
    sample = node_data.get("samplePayload")
    if isinstance(sample, str):
        text = sample.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except ValueError:
            return {"raw": sample}
    return sample if sample is not None else {}


def extract_idempotency_key(envelope: Dict[str, Any], node_data: Dict[str, Any]) -> Optional[str]:
    """``Idempotency-Key`` header first, then the node's configured path."""
    value = (envelope.get("headers") or {}).get(IDEMPOTENCY_HEADER)
    if not value:
        path = (node_data.get("idempotencyPath") or "").strip()
        if path:
            found, value = get_path(envelope, path)
            if not found:
                value = None
    if value is None or value == "":
        return None
    return str(value)[:255]


def build_trigger_input(
    envelope: Dict[str, Any], node_data: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    """Map a delivery onto the engine input the trigger node's workflow expects.

    Returns ``(input_data, errors)``. ``input_data`` always carries the envelope
    under ``webhook``; ``message`` is set only when ``messagePath`` is
    configured (a missing optional value falls back to ``""``). Errors are
    human-readable and name the offending mapping so a 422 is actionable.
    """
    errors: List[str] = []
    input_data: Dict[str, Any] = {ENVELOPE_KEY: envelope}

    for index, mapping in enumerate(node_data.get("fieldMappings") or []):
        if not isinstance(mapping, dict):
            continue
        key = str(mapping.get("key") or "").strip()
        path = str(mapping.get("path") or "").strip()
        if not key and not path:
            continue  # an empty row in the editor
        if not _KEY_RE.match(key):
            errors.append(f"Mapping #{index + 1}: '{key}' is not a valid input key")
            continue
        if key in RESERVED_INPUT_KEYS:
            errors.append(f"Mapping #{index + 1}: '{key}' is reserved")
            continue
        found, value = get_path(envelope, path) if path else (False, None)
        if not found:
            if "default" in mapping and mapping.get("default") not in (None, ""):
                value = mapping["default"]
            elif mapping.get("required"):
                errors.append(f"Required field '{key}' not found at '{path}'")
                continue
            else:
                value = mapping.get("default")
        input_data[key] = value

    message_path = (node_data.get("messagePath") or "").strip()
    if message_path:
        found, value = get_path(envelope, message_path)
        if found and value is not None:
            input_data["message"] = value if isinstance(value, str) else json.dumps(value)
        elif node_data.get("messageRequired"):
            errors.append(f"Message not found at '{message_path}'")
        else:
            input_data["message"] = ""

    return input_data, errors


def resolve_thread_id(envelope: Dict[str, Any], node_data: Dict[str, Any]) -> Optional[str]:
    """The caller's thread id when a ``threadIdPath`` is configured and present."""
    path = (node_data.get("threadIdPath") or "").strip()
    if not path:
        return None
    found, value = get_path(envelope, path)
    if not found or value in (None, ""):
        return None
    return str(value)[:255]
