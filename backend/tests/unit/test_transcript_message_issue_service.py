"""Unit tests for reported-issue updates and the status summary, with fake repositories"""

from datetime import datetime, timezone
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


STAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)
RESOLVER = uuid4()


def _issue(**fields):
    row = dict(
        id=uuid4(),
        message_feedback_id=uuid4(),
        status="open",
        fix_version=None,
        target_rollout_date=None,
        resolved_by=None,
        resolved_at=None,
        updated_at=None,
    )
    return SimpleNamespace(**{**row, **fields})


def _resolved_issue(**fields):
    return _issue(status="resolved", resolved_at=STAMP, resolved_by=RESOLVER, **fields)


class FakeRepo:
    def __init__(self, counts=(), issue=None):
        self.counts = list(counts)
        self.issue = issue
        self.saved = None

    async def get_or_add_issue(self, message_feedback_id):
        if self.issue is None:
            self.issue = _issue(message_feedback_id=message_feedback_id)
        return self.issue

    async def update(self, issue):
        self.saved = issue
        return issue

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
    repo = FakeRepo(issue=_resolved_issue())
    await _service(repo).update_issue(uuid4(), IssueUpdate(fix_version="2.4.1"))
    assert repo.saved.fix_version == "2.4.1"
    assert (repo.saved.status, repo.saved.resolved_at, repo.saved.resolved_by) == ("resolved", STAMP, RESOLVER)


@pytest.mark.asyncio
async def test_done_status_stamps_resolution():
    repo = FakeRepo()
    user_id = uuid4()
    with request_cycle_context():
        context["user_id"] = user_id
        issue = await _service(repo).update_issue(uuid4(), IssueUpdate(status="resolved"))

    assert repo.saved.status == "resolved"
    assert repo.saved.resolved_by == user_id
    assert isinstance(repo.saved.resolved_at, datetime)
    assert issue.resolved_by == user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["open", "in_progress", "needs_help_desk_fix", "qa_approved"])
async def test_status_outside_done_clears_resolution(status):
    repo = FakeRepo(issue=_resolved_issue())
    await _service(repo).update_issue(uuid4(), IssueUpdate(status=status))
    assert (repo.saved.status, repo.saved.resolved_at, repo.saved.resolved_by) == (status, None, None)


@pytest.mark.asyncio
async def test_unchanged_status_keeps_the_original_resolution():
    repo = FakeRepo(issue=_resolved_issue())
    await _service(repo).update_issue(uuid4(), IssueUpdate(status="resolved"))
    assert (repo.saved.resolved_at, repo.saved.resolved_by) == (STAMP, RESOLVER)


@pytest.mark.asyncio
async def test_changed_status_restamps_the_resolution():
    repo = FakeRepo(issue=_resolved_issue())
    user_id = uuid4()
    with request_cycle_context():
        context["user_id"] = user_id
        await _service(repo).update_issue(uuid4(), IssueUpdate(status="wont_fix"))

    assert repo.saved.status == "wont_fix"
    assert repo.saved.resolved_by == user_id
    assert repo.saved.resolved_at != STAMP


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["nope", "escalated"])
async def test_unknown_or_retired_status_is_rejected(status):
    repo = FakeRepo()
    with pytest.raises(AppException) as error:
        await _service(repo).update_issue(uuid4(), IssueUpdate(status=status))

    assert error.value.error_key == ErrorKey.ISSUE_STATUS_NOT_FOUND
    assert error.value.status_code == 422
    assert repo.saved is None


@pytest.mark.asyncio
async def test_unchanged_retired_status_still_saves_the_other_fields():
    repo = FakeRepo(issue=_issue(status="escalated"))
    await _service(repo).update_issue(uuid4(), IssueUpdate(status="escalated", fix_version="2.4.1"))
    assert (repo.saved.status, repo.saved.fix_version) == ("escalated", "2.4.1")


@pytest.mark.asyncio
async def test_explicit_null_is_passed_through():
    repo = FakeRepo(issue=_issue(fix_version="2.4.1"))
    await _service(repo).update_issue(uuid4(), IssueUpdate(fix_version=None))
    assert repo.saved.fix_version is None


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
