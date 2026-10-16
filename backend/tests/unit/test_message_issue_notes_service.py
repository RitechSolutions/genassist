"""Unit tests for the reported-issue note log, with a fake repository"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette_context import context, request_cycle_context

from app.schemas.message_issue import IssueNoteCreate
from app.services.transcript_message_service import TranscriptMessageService


def _note(feedback_id, author_id, body):
    return SimpleNamespace(
        id=uuid4(),
        message_feedback_id=feedback_id,
        author_user_id=author_id,
        body=body,
        created_at=datetime.now(timezone.utc),
    )


class FakeRepo:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.added = None

    async def list_issue_notes(self, message_feedback_id):
        return self.rows

    async def add_issue_note(self, message_feedback_id, author_user_id, body):
        self.added = (message_feedback_id, author_user_id, body)
        return _note(message_feedback_id, author_user_id, body), "admin"


@pytest.mark.asyncio
async def test_note_author_is_the_caller():
    repo, feedback_id, user_id = FakeRepo(), uuid4(), uuid4()
    with request_cycle_context():
        context["user_id"] = user_id
        note = await TranscriptMessageService(repo, repo).add_issue_note(feedback_id, IssueNoteCreate(body="Retested"))

    assert repo.added == (feedback_id, user_id, "Retested")
    assert (note.author_user_id, note.author_username) == (user_id, "admin")


@pytest.mark.asyncio
async def test_notes_keep_the_repository_order_and_usernames():
    feedback_id = uuid4()
    rows = [(_note(feedback_id, uuid4(), "first"), "ana"), (_note(feedback_id, uuid4(), "second"), None)]
    notes = await TranscriptMessageService(FakeRepo(rows), None).list_issue_notes(feedback_id)
    assert [(n.body, n.author_username) for n in notes] == [("first", "ana"), ("second", None)]
