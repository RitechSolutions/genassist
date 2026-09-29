"""Integration tests for the LLM usage ledger schema (migration 00102)"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.llm_usage import (
    CONTROL_SINGLETON_KEY,
    LlmUsageCaptureRunModel,
    LlmUsageEventModel,
)


@pytest_asyncio.fixture
async def db(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


def _event_row(**overrides) -> dict:
    row = {
        "id": uuid4(),
        "execution_id": f"exec-{uuid4()}",
        "call_index": 0,
        "source_type": "workflow",
        "source": "chat",
        "input_tokens": 10,
        "prompt_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "pricing_status": "fallback",
        "occurred_at": datetime.now(timezone.utc),
        "is_deleted": 0,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_control_singleton_captures_by_default(db):
    result = await db.execute(
        text("SELECT capture_enabled, capture_started_at FROM llm_usage_control WHERE singleton_key = :k"),
        {"k": CONTROL_SINGLETON_KEY},
    )
    row = result.first()
    assert row is not None, "control singleton row must be seeded by the migration"
    assert row.capture_enabled is True
    assert row.capture_started_at is not None, "capture without a boundary leaves the backfill inert"


@pytest.mark.asyncio
async def test_ledger_tables_are_exactly_the_permanent_set(db):
    result = await db.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'llm\\_usage%'")
    )
    assert {row[0] for row in result.all()} == {
        "llm_usage_events",
        "llm_usage_capture_runs",
        "llm_usage_control",
    }


@pytest.mark.asyncio
async def test_control_columns_are_exactly_the_permanent_set(db):
    result = await db.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name='llm_usage_control'")
    )
    assert {row[0] for row in result.all()} == {
        "id",
        "singleton_key",
        "capture_enabled",
        "capture_started_at",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "is_deleted",
    }


@pytest.mark.asyncio
async def test_every_ledger_fk_sets_null_on_delete(db):
    result = await db.execute(
        text(
            "SELECT tc.table_name, kcu.column_name, rc.delete_rule "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.referential_constraints rc "
            "  ON rc.constraint_name = tc.constraint_name AND rc.constraint_schema = tc.constraint_schema "
            "JOIN information_schema.key_column_usage kcu "
            "  ON kcu.constraint_name = tc.constraint_name AND kcu.constraint_schema = tc.constraint_schema "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "  AND tc.table_name IN ('llm_usage_events', 'llm_usage_capture_runs')"
        )
    )
    assert {(row[0], row[1]): row[2] for row in result.all()} == {
        ("llm_usage_events", "agent_id"): "SET NULL",
        ("llm_usage_events", "workflow_id"): "SET NULL",
        ("llm_usage_events", "llm_provider_id"): "SET NULL",
        ("llm_usage_events", "llm_analyst_id"): "SET NULL",
        ("llm_usage_events", "conversation_id"): "SET NULL",
        ("llm_usage_events", "legacy_response_log_id"): "SET NULL",
        ("llm_usage_capture_runs", "agent_id"): "SET NULL",
        ("llm_usage_capture_runs", "workflow_id"): "SET NULL",
        ("llm_usage_capture_runs", "conversation_id"): "SET NULL",
    }


@pytest.mark.asyncio
async def test_no_live_events_predate_the_capture_boundary(db):
    result = await db.execute(
        text(
            "SELECT count(*) FROM llm_usage_events e, llm_usage_control c "
            "WHERE e.legacy_response_log_id IS NULL AND e.occurred_at < c.capture_started_at"
        )
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_workflow_execution_id_column_and_partial_unique(db):
    cols = await db.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='agent_response_logs' AND column_name='workflow_execution_id'"
        )
    )
    assert cols.scalar() == "character varying"

    idx = await db.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname='uq_agent_response_logs_workflow_execution_id'"
        )
    )
    definition = idx.scalar()
    assert definition is not None
    assert "UNIQUE" in definition and "workflow_execution_id IS NOT NULL" in definition


@pytest.mark.asyncio
async def test_pricing_status_check_rejects_bad_value(db):
    db.add(LlmUsageEventModel(**_event_row(pricing_status="made_up")))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_source_type_check_rejects_bad_value(db):
    db.add(LlmUsageEventModel(**_event_row(source_type="platform")))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_event_source_type_check_accepts_evaluation(db):
    db.add(LlmUsageEventModel(**_event_row(source_type="evaluation", source="test_suite", purpose="llm_judge")))
    try:
        await db.flush()
    finally:
        await db.rollback()


@pytest.mark.asyncio
async def test_capture_run_source_type_check_accepts_evaluation(db):
    db.add(
        LlmUsageCaptureRunModel(
            id=uuid4(),
            execution_id=f"eval:{uuid4()}",
            source_type="evaluation",
            source="test_suite",
            execution_outcome="returned",
            run_status="completed",
            expected_entries=2,
            persisted_events=2,
            occurred_at=datetime.now(timezone.utc),
            is_deleted=0,
        )
    )
    try:
        await db.flush()
    finally:
        await db.rollback()


@pytest.mark.asyncio
async def test_total_ge_parts_check(db):
    db.add(
        LlmUsageEventModel(**_event_row(input_tokens=10, output_tokens=10, total_tokens=5))
    )
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_prompt_tokens_below_input_rejected(db):
    db.add(LlmUsageEventModel(**_event_row(input_tokens=10, prompt_tokens=9)))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_negative_tokens_rejected(db):
    db.add(LlmUsageEventModel(**_event_row(input_tokens=-1)))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_execution_call_index_idempotent(db):
    exec_id = f"exec-{uuid4()}"
    row1 = _event_row(execution_id=exec_id, call_index=0)
    row2 = _event_row(execution_id=exec_id, call_index=0)
    try:
        stmt = insert(LlmUsageEventModel).values([row1]).on_conflict_do_nothing(
            constraint="uq_llm_usage_events_execution_call"
        )
        r1 = await db.execute(stmt)
        assert r1.rowcount == 1
        stmt2 = insert(LlmUsageEventModel).values([row2]).on_conflict_do_nothing(
            constraint="uq_llm_usage_events_execution_call"
        )
        r2 = await db.execute(stmt2)
        assert r2.rowcount == 0
    finally:
        await db.rollback()


@pytest.mark.asyncio
async def test_capture_run_outcome_check(db):
    db.add(
        LlmUsageCaptureRunModel(
            id=uuid4(),
            execution_id=f"run-{uuid4()}",
            source_type="workflow",
            source="chat",
            execution_outcome="exploded",
            run_status="completed",
            expected_entries=0,
            persisted_events=0,
            occurred_at=datetime.now(timezone.utc),
            is_deleted=0,
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()
