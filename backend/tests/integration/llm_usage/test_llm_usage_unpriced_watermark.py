"""Integration tests for the newest-unpriced watermark behind the coverage notice"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.llm_usage import LlmUsageEventModel
from app.repositories.llm_usage_read import LlmUsageReadRepository

_MONTH_AGO = timedelta(days=30)


@pytest_asyncio.fixture
async def db(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    execution_ids: list[str] = []
    async with maker() as session:
        try:
            yield session, execution_ids
        finally:
            await session.rollback()
            if execution_ids:
                await session.execute(
                    delete(LlmUsageEventModel).where(LlmUsageEventModel.execution_id.in_(execution_ids))
                )
                await session.commit()
    await engine.dispose()


async def _record(db, *, cost, occurred_at) -> None:
    session, execution_ids = db
    execution_id = f"watermark-{uuid4()}"
    execution_ids.append(execution_id)
    session.add(
        LlmUsageEventModel(
            id=uuid4(),
            execution_id=execution_id,
            call_index=0,
            source_type="workflow",
            source="chat",
            input_tokens=10,
            prompt_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_usd=cost,
            pricing_status="unpriced" if cost is None else "configured",
            occurred_at=occurred_at,
            is_deleted=0,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_watermark_tracks_when_the_call_was_recorded_not_when_it_ran(db):
    session, _ = db
    ran_at = datetime.now(timezone.utc) - _MONTH_AGO
    recorded_after = datetime.now(timezone.utc)
    await _record(db, cost=None, occurred_at=ran_at)

    watermark = await LlmUsageReadRepository(session).last_unpriced_at()
    assert watermark >= recorded_after, "an out-of-order arrival must still count as newly recorded"
    assert watermark > ran_at


@pytest.mark.asyncio
async def test_priced_calls_leave_the_watermark_alone(db):
    session, _ = db
    await _record(db, cost=None, occurred_at=datetime.now(timezone.utc) - _MONTH_AGO)
    before = await LlmUsageReadRepository(session).last_unpriced_at()

    await _record(db, cost=Decimal("0.25"), occurred_at=datetime.now(timezone.utc))

    assert await LlmUsageReadRepository(session).last_unpriced_at() == before


@pytest.mark.asyncio
async def test_soft_deleted_unpriced_calls_are_excluded(db):
    session, execution_ids = db
    await _record(db, cost=None, occurred_at=datetime.now(timezone.utc))
    repo = LlmUsageReadRepository(session)
    before = await repo.last_unpriced_at()

    await session.execute(
        LlmUsageEventModel.__table__.update()
        .where(LlmUsageEventModel.execution_id.in_(execution_ids))
        .values(is_deleted=1)
    )
    await session.commit()

    assert await repo.last_unpriced_at() != before
