"""Strict JSON-object reading for LLM replies.
Stricter than engine/nodes/nlp_base.parse_json_object (accepts unbalanced fences).
Duplicated here to avoid importing the ML graph.
"""

import json
import math
import re


_FENCE_RE = re.compile(r"```(?:json)?(.*?)```", re.DOTALL)


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not valid JSON.")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{value} is out of range for JSON.")
    return number


def parse_json_object_reply(text: str) -> dict:
    """Extract one JSON object from a reply (optional Markdown fence).
    Raises:
        ValueError: array, nested object, scalar, prose, duplicates,
            unbalanced fence, or non-finite number.
    """
    candidate = (text or "").strip()
    fenced = _FENCE_RE.fullmatch(candidate)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        parsed = json.loads(
            candidate, parse_constant=_reject_constant, parse_float=_finite_float
        )
    except ValueError as exc:
        raise ValueError("Reply is not a single JSON object.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Reply is not a single JSON object.")
    return parsed
