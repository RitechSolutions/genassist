"""Tests for the shared comparisons used by the Switch and Filter nodes."""

import re

import pytest

from app.modules.workflow.engine.conditions import (
    OPERATORS,
    evaluate,
    is_empty_text,
    numbers_equal,
    parse_number,
    to_text,
)


@pytest.mark.parametrize(
    "actual, operator, expected, result",
    [
        ("Active", "equal", "active", True),
        (" active ", "equal", "active", True),
        ("active", "not_equal", "blocked", True),
        ("active", "not_equal", "ACTIVE", False),
        ("billing question", "contains", "BILLING", True),
        ("billing question", "not_contain", "refund", True),
        ("sales-42", "starts_with", "sales", True),
        ("sales-42", "not_starts_with", "sales", False),
        ("report.pdf", "ends_with", ".PDF", True),
        ("report.pdf", "not_ends_with", ".doc", True),
        ("SALES-42", "regex", r"^sales-\d+$", True),
    ],
)
def test_text_operators(actual, operator, expected, result):
    assert evaluate(actual, operator, expected) is result


def test_case_sensitive_text_comparison():
    assert evaluate("Active", "equal", "active", case_sensitive=True) is False
    assert evaluate("Active", "regex", "^active$", case_sensitive=True) is False


@pytest.mark.parametrize(
    "actual, operator, expected, result",
    [
        ("0.92", "greater_than", "0.8", True),
        ("80", "greater_than", "80", False),
        ("80", "greater_than_or_equal", "80.0", True),
        ("-5", "less_than", "0", True),
        ("1e3", "less_than_or_equal", "1000", True),
        ("10", "greater_than", "9", True),  # numeric, not text order
        ("12345678901234567891", "greater_than", "12345678901234567890", True),  # exact, no float rounding
    ],
)
def test_number_operators(actual, operator, expected, result):
    assert evaluate(actual, operator, expected) is result


@pytest.mark.parametrize("actual, expected", [("high", "5"), ("5", "a lot"), ("null", "0"), ("", "0")])
def test_number_operators_are_false_when_a_side_is_not_a_number(actual, expected):
    for operator in ("greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal"):
        assert evaluate(actual, operator, expected) is False


@pytest.mark.parametrize("value", ["", "   ", "null", "NULL", "[]", "{}"])
def test_presence_operators_treat_missing_values_as_empty(value):
    assert evaluate(value, "is_empty", "") is True
    assert evaluate(value, "is_not_empty", "") is False


@pytest.mark.parametrize("value", ["0", "false", "none", "[1]", "x"])
def test_presence_operators_keep_real_values(value):
    assert evaluate(value, "is_not_empty", "") is True


@pytest.mark.parametrize("operator", ["equal", "not_equal", "contains", "not_contain", "starts_with", "regex"])
def test_operators_needing_a_value_are_false_without_one(operator):
    assert evaluate("anything", operator, "  " if operator != "regex" else "") is False


def test_unknown_operator_and_bad_regex_raise_for_the_caller_to_report():
    with pytest.raises(ValueError):
        evaluate("a", "fuzzy", "a")
    with pytest.raises(re.error):
        evaluate("a", "regex", "(unclosed")


def test_equal_reconciles_number_formatting_only():
    assert numbers_equal("3.0", "3")
    assert not numbers_equal("007", "7")
    assert evaluate("3.0", "equal", "3") and not evaluate("3.0", "not_equal", "3")


def test_helpers():
    assert parse_number(" 2.50 ") == parse_number("2.5")
    assert parse_number("1_000") is None
    assert parse_number("inf") is None
    assert is_empty_text(" null ")
    assert to_text(True) == "true" and to_text({"a": 1}) == '{"a": 1}' and to_text(None) == ""
    assert len(OPERATORS) == len(set(OPERATORS)) == 15
