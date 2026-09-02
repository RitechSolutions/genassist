"""Text and node-reference helpers shared by the evaluation grading modules.

Kept free of DB, engine and ORM imports so rule modules can use them without
importing the test-suite service (which imports the rule modules in turn).
"""

from __future__ import annotations

import re
from typing import Any, Dict

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    # Unwrap single-key string wrapper dicts produced by both the frontend
    # (expected_output fallback) and the execution engine (actual_output).
    # Supported keys: "value" (execution wrapper) and "text" (legacy frontend wrapper).
    if isinstance(value, dict):
        for key in ("value", "text"):
            if list(value.keys()) == [key] and isinstance(value[key], str):
                return value[key].strip()
    return str(value).strip()


def names_equal(first: Any, second: Any) -> bool:
    return normalize_text(first).lower() == normalize_text(second).lower()


def node_matches_selector(node: Dict[str, Any], selector: Any) -> bool:
    """Match a trace node by exact id or case-insensitive display label."""
    return node.get("id") == selector or names_equal(node.get("label"), selector)


def display_name(value: Any, labels: Dict[str, str], fallback: str = "unknown node") -> str:
    """Human name for a node/tool reference: its resolved label, the value itself
    when it already reads as a name, or a neutral fallback instead of a raw id."""
    text = str(value or "").strip()
    if not text:
        return fallback
    label = labels.get(text)
    if label:
        return label
    # MCP tool ids are "{nodeId}:{toolName}"; the tool name half is readable.
    prefix, _, suffix = text.partition(":")
    if suffix and _UUID_RE.match(prefix):
        return suffix
    return fallback if _UUID_RE.match(text) else text
