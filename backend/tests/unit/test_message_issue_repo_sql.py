"""Unit tests asserting the SQL shape of the reported-issue reads without needing a database"""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from starlette_context import context, request_cycle_context

import app.db.models  # noqa: F401 — registers mappers for ORM compilation
import app.db.models.test_suite  # noqa: F401
from app.core.exceptions.exception_classes import AppException
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.message_issue import MessageIssueModel
from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.filter import MessageIssueFilter, MessageIssueSummaryFilter
from app.schemas.message_issue import ReportedIssueRead


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
    await TranscriptMessageRepository(db).get_message_issues(MessageIssueFilter(**kwargs))
    return db.statements


async def _summary_statement(**kwargs):
    db = CapturingDb()
    await TranscriptMessageRepository(db).count_message_issues_by_status(MessageIssueSummaryFilter(**kwargs))
    return db.statements[0]


async def _feedback_check_statement(read=TranscriptMessageRepository.list_issue_notes):
    db = CapturingDb()
    with pytest.raises(AppException):
        await read(TranscriptMessageRepository(db), uuid4())
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
        statements = [
            *await _list_statements(),
            await _summary_statement(),
            await _feedback_check_statement(),
            await _feedback_check_statement(TranscriptMessageRepository.list_issue_history),
        ]

    for stmt in statements:
        where = _sql(stmt).split("WHERE", 1)[1]
        assert ("conversations.group_id" in where) is scoped
        assert stmt.get_execution_options()[GROUP_SCOPE_BYPASS_FLAG] is True


@pytest.mark.asyncio
async def test_feedback_id_narrows_the_list_to_one_report():
    feedback_id = uuid4()
    rows, count = await _list_statements(feedback_id=feedback_id)
    for stmt in (rows, count):
        assert f"message_feedback.id = '{feedback_id}'" in _sql(stmt)


@pytest.mark.asyncio
async def test_agent_filter_narrows_the_rows_count_and_summary():
    agent_id = uuid4()
    statements = [*await _list_statements(agent_id=agent_id), await _summary_statement(agent_id=agent_id)]

    for stmt in statements:
        sql = _sql(stmt)
        assert "LEFT OUTER JOIN agents ON agents.operator_id = operators.id" in sql
        assert f"agents.id = '{agent_id}'" in sql


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
async def test_search_matches_the_comment_or_any_note():
    statements = [*await _list_statements(search="timeout"), await _summary_statement(search="timeout")]

    for stmt in statements:
        sql = _sql(stmt)
        assert "message_feedback.feedback_message ILIKE" in sql
        assert "EXISTS (SELECT message_issue_notes.body" in sql
        assert "message_issue_notes.message_feedback_id = message_feedback.id" in sql
        assert "ESCAPE '/'" in sql


@pytest.mark.asyncio
async def test_blank_search_adds_no_filter():
    rows, count = await _list_statements(search="   ")
    summary = await _summary_statement(search="   ")

    for stmt in (rows, count, summary):
        assert "ILIKE" not in _sql(stmt)
    assert "NULL AS matched_note" in _sql(rows)


@pytest.mark.asyncio
async def test_list_returns_the_newest_matching_note():
    rows, _ = await _list_statements(search="timeout")
    sql = _sql(rows)
    assert "ORDER BY message_issue_notes.created_at DESC, message_issue_notes.id DESC" in sql
    assert "AS matched_note" in sql

    rows, _ = await _list_statements()
    assert "NULL AS matched_note" in _sql(rows)


@pytest.mark.asyncio
async def test_list_rows_carry_every_reported_issue_field():
    rows, _ = await _list_statements()
    assert {column["name"] for column in rows.column_descriptions} == set(ReportedIssueRead.model_fields)


@pytest.mark.asyncio
async def test_search_escapes_like_wildcards():
    statements = [*await _list_statements(search="50%_off"), await _summary_statement(search="50%_off")]

    for stmt in statements:
        values = stmt.compile(dialect=postgresql.dialect()).params.values()
        assert "50/%/_off" in values
        assert "50%_off" not in values


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


class IssueDb(CapturingDb):
    def __init__(self, issue):
        super().__init__()
        self.rows = [uuid4(), issue]
        self.added = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result(self.rows.pop(0))

    def add(self, obj):
        self.added.append(obj)


@pytest.mark.asyncio
async def test_get_or_add_adds_a_missing_issue_defaulting_to_open():
    db, feedback_id = IssueDb(issue=None), uuid4()
    issue = await TranscriptMessageRepository(db).get_or_add_issue(feedback_id)
    assert db.added == [issue]
    assert (issue.message_feedback_id, issue.status) == (feedback_id, "open")


@pytest.mark.asyncio
async def test_get_or_add_returns_the_existing_issue():
    existing = MessageIssueModel(status="resolved", fix_version="2.4.1")
    db = IssueDb(issue=existing)
    issue = await TranscriptMessageRepository(db).get_or_add_issue(uuid4())
    assert issue is existing and db.added == []


@pytest.mark.asyncio
async def test_history_reads_the_issue_and_comment_rows():
    db = IssueDb(issue=None)
    await TranscriptMessageRepository(db).list_issue_history(uuid4())

    sql = _sql(db.statements[1])
    assert "audit_log.table_name = 'message_issues' AND audit_log.record_id = (SELECT message_issues.id" in sql
    assert "audit_log.table_name = 'message_feedback'" in sql
    assert "LEFT OUTER JOIN users ON users.id = audit_log.modified_by" in sql
    assert "ORDER BY audit_log.modified_at ASC, audit_log.id ASC" in sql
