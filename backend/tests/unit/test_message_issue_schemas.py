"""Unit tests for the reported-issue partial update body"""

import pytest
from pydantic import ValidationError

from app.schemas.message_issue import IssueNoteCreate, IssueUpdate


def test_blank_text_becomes_null():
    assert IssueUpdate(fix_version="  ").model_dump(exclude_unset=True) == {"fix_version": None}


def test_status_cannot_be_null():
    with pytest.raises(ValidationError):
        IssueUpdate.model_validate({"status": None})


def test_note_body_is_trimmed_and_cannot_be_blank():
    assert IssueNoteCreate(body="  Fixed in 2.4.1 ").body == "Fixed in 2.4.1"
    with pytest.raises(ValidationError):
        IssueNoteCreate(body="   ")
