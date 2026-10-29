"""Unit tests for the configurable issue-status bodies"""

import pytest
from pydantic import ValidationError

from app.schemas.issue_status import IssueStatusCreate, IssueStatusEdit


@pytest.mark.parametrize("key", ["Needs Fix", "1abc", "a>b", "a", "needs-fix", "needs_fix\n"])
def test_keys_must_be_lower_snake_case(key):
    with pytest.raises(ValidationError):
        IssueStatusCreate(key=key, label="Needs fix", category="todo", color="red")


def test_all_is_reserved_but_keys_starting_with_it_are_not():
    with pytest.raises(ValidationError):
        IssueStatusCreate(key="all", label="All", category="todo", color="red")
    for key in ("al", "alt", "all_done"):
        assert IssueStatusCreate(key=key, label="Other", category="done", color="red").key == key


def test_create_trims_the_label_and_rejects_colours_outside_the_palette():
    created = IssueStatusCreate(key="needs_fix", label="  Needs fix ", category="todo", color="red")
    assert created.label == "Needs fix"
    with pytest.raises(ValidationError):
        IssueStatusCreate(key="needs_fix", label="Needs fix", category="todo", color="#ff0000")
    with pytest.raises(ValidationError):
        IssueStatusCreate(key="needs_fix", label="   ", category="todo", color="red")


def test_the_key_cannot_be_edited():
    assert IssueStatusEdit.model_validate({"key": "other"}).model_dump(exclude_unset=True) == {}
