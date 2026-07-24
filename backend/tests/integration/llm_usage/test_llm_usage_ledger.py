"""Integration tests for the LLM usage ledger schema (migration 00099)"""

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
        "output_tokens": 5,
        "total_tokens": 15,
        "pricing_status": "fallback",
        "occurred_at": datetime.now(timezone.utc),
        "is_deleted": 0,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_control_singleton_is_inert(db):
    result = await db.execute(
        text(
            "SELECT capture_enabled, ledger_cutover_enabled FROM llm_usage_control "
            "WHERE singleton_key = :k"
        ),
        {"k": CONTROL_SINGLETON_KEY},
    )
    row = result.first()
    assert row is not None, "control singleton row must be seeded by the migration"
    assert row.capture_enabled is False
    assert row.ledger_cutover_enabled is False


@pytest.mark.asyncio
async def test_no_ledger_rows_before_activation(db):
    events = await db.execute(text("SELECT count(*) FROM llm_usage_events"))
    receipts = await db.execute(text("SELECT count(*) FROM llm_usage_capture_runs"))
    assert events.scalar() == 0
    assert receipts.scalar() == 0


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
async def test_total_ge_parts_check(db):
    db.add(
        LlmUsageEventModel(**_event_row(input_tokens=10, output_tokens=10, total_tokens=5))
    )
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
