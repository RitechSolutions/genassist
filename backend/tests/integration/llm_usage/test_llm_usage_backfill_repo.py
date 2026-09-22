"""Integration tests for the legacy backfill insert paths"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.llm_usage import LlmUsageEventModel
from app.repositories.llm_usage_backfill import LlmUsageBackfillRepository


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


def _backfill_row(execution_id: str, **overrides) -> dict:
    row = {
        "execution_id": execution_id,
        "call_index": 0,
        "source_type": "workflow",
        "source": "chat",
        "input_tokens": 10,
        "prompt_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "cost_usd": Decimal("0.001"),
        "pricing_status": "legacy_estimate",
        "occurred_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_insert_is_idempotent(db):
    repo = LlmUsageBackfillRepository(db)
    exec_id = f"legacy:{uuid4()}"
    try:
        first = await repo.insert_events([_backfill_row(exec_id)], force=False)
        second = await repo.insert_events([_backfill_row(exec_id)], force=False)
        assert first == 1
        assert second == 0
    finally:
        await db.execute(delete(LlmUsageEventModel).where(LlmUsageEventModel.execution_id == exec_id))
        await db.commit()


@pytest.mark.asyncio
async def test_force_recopies_existing_row(db):
    repo = LlmUsageBackfillRepository(db)
    exec_id = f"legacy:{uuid4()}"
    try:
        await repo.insert_events([_backfill_row(exec_id, cost_usd=Decimal("0.001"))], force=False)
        updated = await repo.insert_events(
            [_backfill_row(exec_id, cost_usd=Decimal("0.5"), pricing_status="unpriced")],
            force=True,
        )
        assert updated == 1

        row = (
            await db.execute(select(LlmUsageEventModel).where(LlmUsageEventModel.execution_id == exec_id))
        ).scalar_one()
        assert row.cost_usd == Decimal("0.5")
        assert row.pricing_status == "unpriced"
    finally:
        await db.execute(delete(LlmUsageEventModel).where(LlmUsageEventModel.execution_id == exec_id))
        await db.commit()


@pytest.mark.asyncio
async def test_empty_rows_write_nothing(db):
    repo = LlmUsageBackfillRepository(db)
    assert await repo.insert_events([], force=False) == 0


@pytest.mark.asyncio
async def test_legacy_event_aggregates_shape(db):
    repo = LlmUsageBackfillRepository(db)
    count, ti, to, tt, cost = await repo.legacy_event_aggregates()
    assert isinstance(count, int)
    assert isinstance(ti, int) and isinstance(to, int) and isinstance(tt, int)
    assert isinstance(cost, Decimal)


@pytest.mark.asyncio
async def test_resolve_agent_workflow_empty(db):
    repo = LlmUsageBackfillRepository(db)
    assert await repo.resolve_agent_workflow(set()) == {}
