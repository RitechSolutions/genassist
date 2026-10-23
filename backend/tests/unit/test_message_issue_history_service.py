"""Unit tests for a reported issue's change history, read from audit rows with a fake repository"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.transcript_message_service import TranscriptMessageService

STAMP = datetime(2026, 10, 8, 10, 14, tzinfo=timezone.utc)


def _log(table_name, action_name, changes):
    json_changes = changes if changes is None or isinstance(changes, str) else json.dumps(changes)
    return SimpleNamespace(table_name=table_name, action_name=action_name, json_changes=json_changes, modified_at=STAMP)


class FakeRepo:
    def __init__(self, rows):
        self.rows = rows

    async def list_issue_history(self, message_feedback_id):
        return self.rows


async def _history(*logs, username="jane"):
    service = TranscriptMessageService(FakeRepo([(log, username) for log in logs]), None)
    return [(e.field, e.old, e.new) for e in await service.list_issue_history("f1")]


def _issue_insert(**values):
    return _log("message_issues", "Insert", {"id": "i1", "fields": sorted(values), "values": values})


@pytest.mark.asyncio
async def test_first_triage_is_read_against_the_defaults():
    triaged = _issue_insert(status="in_progress", fix_version="2.4.1", target_rollout_date=None, resolved_by=None)
    untouched = _issue_insert(status="open", fix_version=None, target_rollout_date=None)

    assert await _history(triaged) == [("status", "open", "in_progress"), ("fix_version", None, "2.4.1")]
    assert await _history(untouched) == []


@pytest.mark.asyncio
async def test_updates_keep_only_the_report_fields():
    update = _log("message_issues", "Update", {
        "status": {"old": "needs_help_desk_fix", "new": "resolved"},
        "resolved_by": {"old": None, "new": "u1"},
        "resolved_at": {"old": None, "new": "2026-10-08 10:14:00+00:00"},
        "updated_by": {"old": None, "new": "u1"},
    })
    service = TranscriptMessageService(FakeRepo([(update, "jane")]), None)

    [event] = await service.list_issue_history("f1")

    assert (event.field, event.old, event.new, event.by, event.at) == (
        "status", "needs_help_desk_fix", "resolved", "jane", STAMP,
    )


@pytest.mark.asyncio
async def test_comment_edits_carry_no_text():
    edited = _log("message_feedback", "Update", {
        "feedback_message": {"old": "Wrong plate", "new": "Wrong plate number"},
        "feedback_timestamp": {"old": "2026-10-01", "new": "2026-10-08"},
    })
    added_to_rating = _log("message_feedback", "Update", {"feedback_message": {"old": None, "new": "Wrong plate"}})
    rating_only = _log("message_feedback", "Update", {"feedback": {"old": "bad", "new": "good"}})
    created = _log("message_feedback", "Insert", {"id": "f1", "values": {"feedback_message": "Wrong plate"}})

    assert await _history(edited, added_to_rating, rating_only, created) == [("comment", None, None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("json_changes", ["not json", None, "[]", "null", '{"status": "resolved"}'])
async def test_unreadable_audit_rows_are_skipped(json_changes):
    assert await _history(_log("message_issues", "Update", json_changes)) == []
