"""Unit tests asserting the SQL shape of the reported-issue reads without needing a database"""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from starlette_context import context, request_cycle_context

import app.db.models  # noqa: F401 — registers mappers for ORM compilation
import app.db.models.test_suite  # noqa: F401
from app.core.exceptions.exception_classes import AppException
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.message_issue import MessageIssueModel
from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.repositories.transcript_message import TranscriptMessageRepository


class _Result:
    def __init__(self, row=None):
        self.row = row

    def all(self):
        return []

    def scalar_one(self):
        return 0

    def scalars(self):
        return self

    def first(self):
        return self.row


class CapturingDb:
    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result()


@contextmanager
def caller(*, roles):
    with request_cycle_context():
        context["user_id"] = uuid4()
        context["group_id"] = uuid4()
        context["supervised_group_ids"] = []
        context["user_roles"] = [SimpleNamespace(name=role) for role in roles]
        yield


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


async def _list_statements(**kwargs):
    db = CapturingDb()
    await TranscriptMessageRepository(db).get_message_issues(**kwargs)
    return db.statements


async def _summary_statement(**kwargs):
    db = CapturingDb()
    await TranscriptMessageRepository(db).count_message_issues_by_status(**kwargs)
    return db.statements[0]


async def _feedback_check_statement():
    db = CapturingDb()
    with pytest.raises(AppException):
        await TranscriptMessageRepository(db).list_issue_notes(uuid4())
    return db.statements[0]


@pytest.mark.asyncio
async def test_summary_groups_by_status_defaulting_to_open():
    sql = _sql(await _summary_statement())
    assert "coalesce(message_issues.status, 'open')" in sql
    assert "GROUP BY coalesce(message_issues.status, 'open')" in sql


@pytest.mark.asyncio
async def test_list_status_filter_matches_the_defaulted_status():
    rows, count = await _list_statements(status="needs_help_desk_fix")
    for stmt in (rows, count):
        assert "coalesce(message_issues.status, 'open') = 'needs_help_desk_fix'" in _sql(stmt)


@pytest.mark.asyncio
@pytest.mark.parametrize("roles, scoped", [(("operator",), True), (("admin",), False)])
async def test_group_scope_is_applied_explicitly_to_every_query(roles, scoped):
    with caller(roles=roles):
        statements = [*await _list_statements(), await _summary_statement(), await _feedback_check_statement()]

    for stmt in statements:
        where = _sql(stmt).split("WHERE", 1)[1]
        assert ("conversations.group_id" in where) is scoped
        assert stmt.get_execution_options()[GROUP_SCOPE_BYPASS_FLAG] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("roles, scoped", [(("operator",), True), (("admin",), False)])
async def test_stored_topic_options_only_come_from_conversations_the_caller_can_see(roles, scoped):
    db = CapturingDb()
    with caller(roles=roles):
        await ConversationAnalysisRepository(db).list_distinct_topics()

    sql = _sql(db.statements[0])
    assert ("JOIN conversations" in sql and "conversations.group_id" in sql) is scoped


@pytest.mark.asyncio
async def test_topic_filters_follow_the_conversations_page():
    statements = [
        *await _list_statements(topic="Refund", subtopic="Wrong plate"),
        await _summary_statement(topic="Refund", subtopic="Wrong plate"),
    ]

    finalized = "CASE WHEN (conversations.status = 'finalized') THEN conversation_analysis"
    for stmt in statements:
        sql = _sql(stmt)
        assert "LEFT OUTER JOIN conversation_analysis" in sql
        assert f"lower(trim({finalized}.topic ELSE conversations.topic END)) = 'refund'" in sql
        assert f"lower(trim({finalized}.subtopic END)) = 'wrong plate'" in sql


@pytest.mark.asyncio
async def test_triage_writes_need_an_issue_the_list_shows():
    sql = _sql(await _feedback_check_statement())
    assert "trim(message_feedback.feedback_message) != ''" in sql
    assert "conversations.is_deleted = 0" in sql


@pytest.mark.asyncio
async def test_list_skips_the_heavy_message_and_conversation_columns():
    rows, _ = await _list_statements()
    sql = _sql(rows)
    for heavy in ("audio_data", "text_search", "transcription", "custom_attributes"):
        assert heavy not in sql


class UpsertDb(CapturingDb):
    def __init__(self, issue):
        super().__init__()
        self.rows = [uuid4(), issue]
        self.added = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result(self.rows.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("values, status", [({"fix_version": "2.4.1"}, "open"), ({"status": "resolved"}, "resolved")])
async def test_upsert_creates_the_issue_defaulting_to_open(values, status):
    db, feedback_id = UpsertDb(issue=None), uuid4()
    issue = await TranscriptMessageRepository(db).upsert_issue(feedback_id, values)
    assert db.added == [issue]
    assert (issue.message_feedback_id, issue.status) == (feedback_id, status)


@pytest.mark.asyncio
async def test_upsert_updates_the_existing_issue_in_place():
    existing = MessageIssueModel(status="open", fix_version="2.4.1")
    db = UpsertDb(issue=existing)
    issue = await TranscriptMessageRepository(db).upsert_issue(uuid4(), {"status": "resolved", "fix_version": None})
    assert issue is existing and db.added == []
    assert (existing.status, existing.fix_version) == ("resolved", None)


FIRST_RESOLUTION = {
    "resolved_by": UUID("11111111-1111-1111-1111-111111111111"),
    "resolved_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
}
LATER_RESOLUTION = {
    "resolved_by": UUID("22222222-2222-2222-2222-222222222222"),
    "resolved_at": datetime(2026, 10, 9, tzinfo=timezone.utc),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("status, resolution", [("resolved", FIRST_RESOLUTION), ("wont_fix", LATER_RESOLUTION)])
async def test_upsert_restamps_the_resolution_only_when_the_status_changes(status, resolution):
    existing = MessageIssueModel(status="resolved", **FIRST_RESOLUTION)
    issue = await TranscriptMessageRepository(UpsertDb(issue=existing)).upsert_issue(
        uuid4(), {"status": status, **LATER_RESOLUTION}
    )
    assert issue.status == status
    assert {"resolved_by": issue.resolved_by, "resolved_at": issue.resolved_at} == resolution
