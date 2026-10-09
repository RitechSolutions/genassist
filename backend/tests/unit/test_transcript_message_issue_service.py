"""Unit tests for reported-issue updates and the status summary, with fake repositories"""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette_context import context, request_cycle_context

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.issue_status_enum import DEFAULT_ISSUE_STATUSES
from app.schemas.filter import MessageIssueSummaryFilter
from app.schemas.message_issue import IssueUpdate
from app.services.transcript_message_service import TranscriptMessageService

STATUSES = [
    SimpleNamespace(key=key, category=category, is_active=1) for key, _, category, _, _ in DEFAULT_ISSUE_STATUSES
] + [SimpleNamespace(key="escalated", category="in_progress", is_active=0)]


class FakeRepo:
    def __init__(self, counts=()):
        self.values = None
        self.counts = list(counts)

    async def upsert_issue(self, message_feedback_id, values):
        self.values = values
        row = dict(
            status="open",
            fix_version=None,
            target_rollout_date=None,
            resolved_by=None,
            resolved_at=None,
            updated_at=None,
        )
        return SimpleNamespace(id=uuid4(), message_feedback_id=message_feedback_id, **{**row, **values})

    async def count_message_issues_by_status(self, **_):
        return self.counts

    async def list_ordered(self):
        return STATUSES

    async def get_by_key(self, key):
        return next((status for status in STATUSES if status.key == key), None)


def _service(repo):
    return TranscriptMessageService(repo, repo)


@pytest.mark.asyncio
async def test_fix_version_only_patch_leaves_resolution_untouched():
    repo = FakeRepo()
    await _service(repo).update_issue(uuid4(), IssueUpdate(fix_version="2.4.1"))
    assert repo.values == {"fix_version": "2.4.1"}


@pytest.mark.asyncio
async def test_done_status_stamps_resolution():
    repo = FakeRepo()
    user_id = uuid4()
    with request_cycle_context():
        context["user_id"] = user_id
        issue = await _service(repo).set_issue_status(uuid4(), "resolved")

    assert repo.values["status"] == "resolved"
    assert repo.values["resolved_by"] == user_id
    assert isinstance(repo.values["resolved_at"], datetime)
    assert issue.resolved_by == user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["open", "in_progress", "needs_help_desk_fix", "qa_approved"])
async def test_status_outside_done_clears_resolution(status):
    repo = FakeRepo()
    await _service(repo).update_issue(uuid4(), IssueUpdate(status=status))
    assert repo.values == {"status": status, "resolved_at": None, "resolved_by": None}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["nope", "escalated"])
async def test_unknown_or_retired_status_is_rejected(status):
    repo = FakeRepo()
    with pytest.raises(AppException) as error:
        await _service(repo).update_issue(uuid4(), IssueUpdate(status=status))

    assert error.value.error_key == ErrorKey.ISSUE_STATUS_NOT_FOUND
    assert error.value.status_code == 422
    assert repo.values is None


@pytest.mark.asyncio
async def test_explicit_null_is_passed_through():
    repo = FakeRepo()
    await _service(repo).update_issue(uuid4(), IssueUpdate(fix_version=None))
    assert repo.values == {"fix_version": None}


@pytest.mark.asyncio
async def test_summary_zero_fills_the_configured_statuses_and_keeps_legacy_keys():
    repo = FakeRepo(counts=[("open", 3), ("resolved", 2), ("legacy", 1)])
    summary = await _service(repo).get_issue_status_summary(MessageIssueSummaryFilter())

    assert list(summary.by_status.items()) == [
        ("open", 3),
        ("in_progress", 0),
        ("needs_help_desk_fix", 0),
        ("qa_approved", 0),
        ("resolved", 2),
        ("wont_fix", 0),
        ("escalated", 0),
        ("legacy", 1),
    ]
    assert summary.total == 6
