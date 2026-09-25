"""
Value comparisons shared by the condition-based workflow nodes (Switch, Filter).

Values reach these nodes after template resolution, i.e. as text: numbers in
their serialized form (``3.0``), flags as ``true``/``false`` and a variable that
resolved to nothing as ``null``. Every comparison works on that text.

Text comparisons trim both sides and, unless ``case_sensitive``, ignore case.
A comparison that needs a value but has none is false, as is a numeric
comparison where either side is not a number: these nodes fail closed rather
than guessing.
"""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

TEXT_OPERATORS = (
    "equal",
    "not_equal",
    "contains",
    "not_contain",
    "starts_with",
    "not_starts_with",
    "ends_with",
    "not_ends_with",
    "regex",
)
NUMBER_OPERATORS = (
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
)
PRESENCE_OPERATORS = ("is_empty", "is_not_empty")
OPERATORS = TEXT_OPERATORS + NUMBER_OPERATORS + PRESENCE_OPERATORS

# What an absent value looks like once resolved into a config: nothing at all,
# ``null`` (a variable that resolved to None) or an empty JSON list/object.
_EMPTY_TEXTS = frozenset({"", "null", "[]", "{}"})

_NUMBER_LITERAL = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def parse_bool(raw: Any) -> bool:
    """Accept bool or common string forms from UI / JSON without mis-treating str."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return raw != 0
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return False


def to_text(value: Any) -> str:
    """A config value as text, so non-string outputs (numbers, flags, objects) can be compared."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def is_empty_text(text: str) -> bool:
    """Whether a resolved value means "nothing there" (see ``_EMPTY_TEXTS``)."""
    return text.strip().lower() in _EMPTY_TEXTS


def parse_number(text: str) -> Optional[Decimal]:
    """The number a text spells out, or None. Exact (Decimal), so no float rounding."""
    stripped = text.strip()
    if not _NUMBER_LITERAL.fullmatch(stripped):
        return None
    try:
        return Decimal(stripped)
    except InvalidOperation:
        return None


def numbers_equal(actual: str, expected: str) -> bool:
    """Whether two texts are the same number written differently (``3.0`` and ``3``).

    Upstream numbers arrive in their serialized form, so an integer-valued float
    reads ``3.0`` while the configured value says ``3``. Only formatting is
    reconciled: at least one side must have a fractional or exponent part, so
    plain digit strings such as ``007`` and ``7`` (ids, codes) still compare as text.
    """
    if not any(ch in text for text in (actual, expected) for ch in ".eE"):
        return False
    a, b = parse_number(actual), parse_number(expected)
    return a is not None and b is not None and a == b


def evaluate(actual: str, operator: str, expected: str, case_sensitive: bool = False) -> bool:
    """Compare ``actual`` against ``expected`` with ``operator``.

    Raises ValueError for an unknown operator and ``re.error`` for an invalid
    regex, so the calling node can log which of its settings is broken.
    """
    if operator not in OPERATORS:
        raise ValueError(f"unsupported operator: {operator}")

    actual = actual.strip()

    if operator == "is_empty":
        return is_empty_text(actual)
    if operator == "is_not_empty":
        return not is_empty_text(actual)

    if operator in NUMBER_OPERATORS:
        a, b = parse_number(actual), parse_number(expected)
        if a is None or b is None:
            return False
        if operator == "greater_than":
            return a > b
        if operator == "greater_than_or_equal":
            return a >= b
        if operator == "less_than":
            return a < b
        return a <= b

    if operator == "regex":
        if not expected:
            return False
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(expected, actual, flags) is not None

    expected = expected.strip()
    if not expected:
        return False
    if not case_sensitive:
        actual, expected = actual.casefold(), expected.casefold()

    if operator == "equal":
        return actual == expected or numbers_equal(actual, expected)
    if operator == "not_equal":
        return not (actual == expected or numbers_equal(actual, expected))
    if operator == "contains":
        return expected in actual
    if operator == "not_contain":
        return expected not in actual
    if operator == "starts_with":
        return actual.startswith(expected)
    if operator == "not_starts_with":
        return not actual.startswith(expected)
    if operator == "ends_with":
        return actual.endswith(expected)
    return not actual.endswith(expected)
