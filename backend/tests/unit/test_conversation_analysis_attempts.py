"""Unit tests for the analysis-attempt bookkeeping on conversations, without a database"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import app.services.conversations as conversations_module
from app.repositories.conversations import ConversationRepository
from app.services.conversations import ConversationService


class CapturingDb:
    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return MagicMock()

    async def flush(self):
        pass


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_backfill_query_caps_and_spaces_attempts_bounds_age_and_takes_the_oldest_first():
    db = CapturingDb()
    repo = ConversationRepository(db)
    before = datetime.now(timezone.utc)

    await repo.get_finalized_without_analysis(max_attempts=3, max_age_days=30, retry_delay_minutes=60)
    await repo.get_finalized_without_analysis(max_attempts=3, max_age_days=0, retry_delay_minutes=60)

    windowed, unbounded = (_sql(s) for s in db.statements)
    assert "conversations.analysis_attempts < 3" in windowed
    assert "(conversations.analysis_last_attempt_at IS NULL OR conversations.analysis_last_attempt_at < " in windowed
    assert "conversations.created_at >= " in windowed
    assert "NOT (EXISTS (SELECT" in windowed and "conversation_analysis.conversation_id = conversations.id" in windowed
    assert "LEFT OUTER JOIN" not in windowed
    assert "ORDER BY conversations.created_at ASC, conversations.id ASC" in windowed
    assert windowed.endswith("LIMIT 100")
    assert "created_at >= " not in unbounded
    params, after = db.statements[0].compile().params, datetime.now(timezone.utc)
    assert before - timedelta(days=30) <= params["created_at_1"] <= after - timedelta(days=30)
    assert before - timedelta(minutes=60) <= params["analysis_last_attempt_at_1"] <= after - timedelta(minutes=60)


@pytest.mark.asyncio
async def test_bookkeeping_updates_leave_updated_at_untouched_and_truncate_errors():
    db = CapturingDb()
    repo = ConversationRepository(db)
    conversation_id = uuid4()

    await repo.mark_analysis_attempt(conversation_id)
    await repo.mark_analysis_attempt(conversation_id, error="x" * 5000)
    await repo.set_analysis_last_error(conversation_id, None)

    plain, with_error, cleared = db.statements
    for stmt in db.statements:
        assert "updated_at=conversations.updated_at" in _sql(stmt)
    assert "analysis_attempts=(conversations.analysis_attempts + 1)" in _sql(plain)
    assert "analysis_last_attempt_at=" in _sql(plain)
    assert "analysis_last_error" not in _sql(plain)
    assert with_error.compile().params["analysis_last_error"] == "x" * 2000
    assert "analysis_last_error=NULL" in _sql(cleared)
    assert "analysis_attempts" not in _sql(cleared) and "analysis_last_attempt_at" not in _sql(cleared)


@pytest.mark.asyncio
async def test_topic_fill_only_writes_a_missing_topic_and_leaves_updated_at_untouched():
    db = CapturingDb()
    conversation_id = uuid4()

    await ConversationRepository(db).fill_topic_if_missing(conversation_id, "Billing Questions")

    [stmt] = db.statements
    sql = _sql(stmt)
    assert "conversations.topic IS NULL" in sql
    assert "updated_at=conversations.updated_at" in sql
    assert stmt.compile().params["topic"] == "Billing Questions"
    assert "analysis_attempts" not in sql


def _cleanup_service(repo):
    return ConversationService(
        operator_statistics_service=MagicMock(),
        conversation_repo=repo,
        conversation_read_repo=AsyncMock(),
        transcript_message_repo=AsyncMock(),
        audit_log_repo=AsyncMock(),
        recordings_repo=AsyncMock(),
        conversation_read_receipt_repo=AsyncMock(),
        thread_rag=AsyncMock(),
        gpt_kpi_analyzer_service=MagicMock(),
        conversation_analysis_service=MagicMock(),
        llm_analyst_service=MagicMock(),
    )


def _stale(count):
    return [MagicMock(id=uuid4(), messages=[MagicMock()] * 3) for _ in range(count)]


@pytest.fixture(autouse=True)
def _no_cache(monkeypatch):
    monkeypatch.setattr(conversations_module, "invalidate_conversation_cache", AsyncMock())


@pytest.mark.asyncio
async def test_cleanup_records_one_attempt_when_finalizing_fails():
    repo = AsyncMock()
    [stale] = _stale(1)
    repo.get_stale_conversations.return_value = [stale]
    service = _cleanup_service(repo)
    service.finalize_in_progress_conversation = AsyncMock(side_effect=RuntimeError("provider down"))

    result = await service.cleanup_stale_conversations(datetime.now(timezone.utc))

    repo.mark_analysis_attempt.assert_awaited_once_with(stale.id, error="RuntimeError: provider down")
    assert result["failed_count"] == 1


@pytest.mark.asyncio
async def test_cleanup_keeps_going_when_recording_the_attempt_fails():
    repo = AsyncMock()
    repo.get_stale_conversations.return_value = _stale(2)
    repo.mark_analysis_attempt.side_effect = RuntimeError("session is dead")
    service = _cleanup_service(repo)
    service.finalize_in_progress_conversation = AsyncMock(side_effect=RuntimeError("provider down"))

    result = await service.cleanup_stale_conversations(datetime.now(timezone.utc))

    assert service.finalize_in_progress_conversation.await_count == 2
    assert result == {"deleted_count": 0, "finalized_count": 0, "failed_count": 2}
