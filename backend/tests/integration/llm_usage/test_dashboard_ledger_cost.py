"""Integration tests for the dashboard reading LLM cost from the ledger after cutover"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.agent import AgentModel
from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.conversation import ConversationModel
from app.db.models.llm_usage import LlmUsageEventModel
from app.db.models.operator import OperatorModel
from app.repositories.dashboard import DashboardRepository


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


def _event(**overrides) -> LlmUsageEventModel:
    row = {
        "id": uuid4(),
        "execution_id": f"exec-{uuid4()}",
        "call_index": 0,
        "source_type": "workflow",
        "source": "chat",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "cost_usd": Decimal("0.25"),
        "pricing_status": "configured",
        "occurred_at": datetime.now(timezone.utc),
        "is_deleted": 0,
    }
    row.update(overrides)
    return LlmUsageEventModel(**row)


def _today_window() -> tuple[datetime, datetime]:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _today_range() -> tuple[datetime, datetime]:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start


@pytest.mark.asyncio
async def test_ledger_total_sums_priced_cost(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd_from_ledger(start, end)

    db.add(_event(cost_usd=Decimal("0.25")))
    await db.flush()

    after = await repo.get_total_cost_usd_from_ledger(start, end)
    assert after - before == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_ledger_total_excludes_unpriced(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd_from_ledger(start, end)

    db.add(_event(cost_usd=None, input_per_1k=None, output_per_1k=None, pricing_status="unpriced"))
    await db.flush()

    after = await repo.get_total_cost_usd_from_ledger(start, end)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_excludes_events_outside_window(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd_from_ledger(start, end)

    db.add(_event(cost_usd=Decimal("0.99"), occurred_at=start - timedelta(hours=1)))
    await db.flush()

    after = await repo.get_total_cost_usd_from_ledger(start, end)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_upper_bound_is_exclusive_of_the_next_day(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd_from_ledger(start, end)

    db.add(_event(cost_usd=Decimal("0.99"), occurred_at=start + timedelta(days=1)))
    await db.flush()

    after = await repo.get_total_cost_usd_from_ledger(start, end)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_drops_the_day_of_a_mid_day_lower_bound(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    mid_day = start + timedelta(hours=13)
    before = await repo.get_total_cost_usd_from_ledger(mid_day, end)

    db.add(_event(cost_usd=Decimal("0.99"), occurred_at=start + timedelta(hours=20)))
    await db.flush()

    after = await repo.get_total_cost_usd_from_ledger(mid_day, end)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_excludes_soft_deleted_events(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd_from_ledger(start, end)

    db.add(_event(cost_usd=Decimal("0.77"), is_deleted=1))
    await db.flush()

    after = await repo.get_total_cost_usd_from_ledger(start, end)
    assert after == pytest.approx(before)


def _agent_cost(rows, agent_id) -> float:
    return rows.get(agent_id, {}).get("cost", 0.0)


@pytest.mark.asyncio
async def test_agent_cost_today_ledger_sums_for_agent(db):
    agent_id = (await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).limit(1))).scalar()
    if agent_id is None:
        pytest.skip("no agent available to attribute ledger cost to")

    repo = DashboardRepository(db)
    start, end = _today_window()
    before = _agent_cost(await repo._agent_cost_today_ledger([agent_id], start, end), agent_id)

    db.add(_event(agent_id=agent_id, cost_usd=Decimal("0.40")))
    # An unpriced call for the same agent must not lift the priced subtotal.
    db.add(_event(agent_id=agent_id, cost_usd=None, pricing_status="unpriced"))
    await db.flush()

    after = _agent_cost(await repo._agent_cost_today_ledger([agent_id], start, end), agent_id)
    assert after - before == pytest.approx(0.40)


@pytest.mark.asyncio
async def test_agent_cost_today_ledger_excludes_next_day(db):
    agent_id = (await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).limit(1))).scalar()
    if agent_id is None:
        pytest.skip("no agent available to attribute ledger cost to")

    repo = DashboardRepository(db)
    start, end = _today_window()
    before = _agent_cost(await repo._agent_cost_today_ledger([agent_id], start, end), agent_id)

    db.add(_event(agent_id=agent_id, cost_usd=Decimal("0.99"), occurred_at=end))
    await db.flush()

    after = _agent_cost(await repo._agent_cost_today_ledger([agent_id], start, end), agent_id)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_agent_cost_per_conversation_today_ledger_is_canonical(db):
    agent_id = (
        await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).order_by(AgentModel.name).limit(1))
    ).scalar()
    operator_id = (await db.execute(select(OperatorModel.id).limit(1))).scalar()
    if agent_id is None or operator_id is None:
        pytest.skip("need an agent and an operator to attribute ledger cost to")

    repo = DashboardRepository(db)
    start, end = _today_window()
    before = (await repo._agent_cost_today_ledger([agent_id], start, end)).get(agent_id, {})
    if before.get("cost_per_conversation") is not None:
        pytest.skip("agent already has conversation-attributed ledger rows today")

    conv_a, conv_b = uuid4(), uuid4()
    db.add(ConversationModel(id=conv_a, operator_id=operator_id, conversation_type="chat"))
    db.add(ConversationModel(id=conv_b, operator_id=operator_id, conversation_type="chat"))
    await db.flush()

    db.add(_event(agent_id=agent_id, conversation_id=conv_a, cost_usd=Decimal("0.30")))
    db.add(_event(agent_id=agent_id, conversation_id=conv_b, cost_usd=Decimal("0.10")))
    db.add(_event(agent_id=agent_id, conversation_id=conv_b, cost_usd=Decimal("0.20")))
    db.add(_event(agent_id=agent_id, conversation_id=None, cost_usd=Decimal("0.50")))
    await db.flush()

    after = (await repo._agent_cost_today_ledger([agent_id], start, end)).get(agent_id, {})
    assert after["cost_per_conversation"] == pytest.approx(0.30)
    assert after["cost"] - before.get("cost", 0.0) == pytest.approx(1.10)


@pytest.mark.asyncio
async def test_agent_cost_per_conversation_counts_unpriced_only_conversations(db):
    agent_id = (
        await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).order_by(AgentModel.name).limit(1))
    ).scalar()
    operator_id = (await db.execute(select(OperatorModel.id).limit(1))).scalar()
    if agent_id is None or operator_id is None:
        pytest.skip("need an agent and an operator to attribute ledger cost to")

    repo = DashboardRepository(db)
    start, end = _today_window()
    before = (await repo._agent_cost_today_ledger([agent_id], start, end)).get(agent_id, {})
    if before.get("cost_per_conversation") is not None:
        pytest.skip("agent already has conversation-attributed ledger rows today")

    priced_conv, unpriced_conv = uuid4(), uuid4()
    db.add(ConversationModel(id=priced_conv, operator_id=operator_id, conversation_type="chat"))
    db.add(ConversationModel(id=unpriced_conv, operator_id=operator_id, conversation_type="chat"))
    await db.flush()

    db.add(_event(agent_id=agent_id, conversation_id=priced_conv, cost_usd=Decimal("0.30")))
    db.add(_event(agent_id=agent_id, conversation_id=unpriced_conv, cost_usd=None, pricing_status="unpriced"))
    await db.flush()

    after = (await repo._agent_cost_today_ledger([agent_id], start, end)).get(agent_id, {})
    assert after["cost_per_conversation"] == pytest.approx(0.15)


@pytest.mark.asyncio
async def test_agent_cost_today_daily_stats_never_attributes_per_conversation(db):
    agent_id = (await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).limit(1))).scalar()
    if agent_id is None:
        pytest.skip("no agent available to attribute daily-stats cost to")

    today = datetime.now(timezone.utc).date()
    existing = (
        await db.execute(
            select(AgentExecutionDailyStatsModel.id).where(
                AgentExecutionDailyStatsModel.agent_id == agent_id,
                AgentExecutionDailyStatsModel.stat_date == today,
            )
        )
    ).scalar()
    if existing is not None:
        pytest.skip("agent already has a daily-stats row today")

    db.add(
        AgentExecutionDailyStatsModel(
            agent_id=agent_id,
            stat_date=today,
            total_cost_usd=Decimal("3.33"),
            last_aggregated_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()

    repo = DashboardRepository(db)
    record = (await repo._agent_cost_today_daily_stats([agent_id], today)).get(agent_id)
    assert record is not None
    assert record["cost"] == pytest.approx(3.33)
    assert record["cost_per_conversation"] is None


@pytest.mark.asyncio
async def test_agent_cost_today_ledger_excludes_soft_deleted_events(db):
    agent_id = (await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).limit(1))).scalar()
    if agent_id is None:
        pytest.skip("no agent available to attribute ledger cost to")

    repo = DashboardRepository(db)
    start, end = _today_window()
    before = _agent_cost(await repo._agent_cost_today_ledger([agent_id], start, end), agent_id)

    db.add(_event(agent_id=agent_id, cost_usd=Decimal("0.77"), is_deleted=1))
    await db.flush()

    after = _agent_cost(await repo._agent_cost_today_ledger([agent_id], start, end), agent_id)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_includes_analyst_source(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd_from_ledger(start, end)

    db.add(_event(source_type="llm_analyst", source="conversation_analysis", cost_usd=Decimal("0.30")))
    await db.flush()

    after = await repo.get_total_cost_usd_from_ledger(start, end)
    assert after - before == pytest.approx(0.30)


@pytest.mark.asyncio
async def test_get_agents_with_stats_picks_source_by_use_ledger(db):
    agent_id = (
        await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).order_by(AgentModel.name).limit(1))
    ).scalar()
    if agent_id is None:
        pytest.skip("no agent available to attribute ledger cost to")

    repo = DashboardRepository(db)

    def _cost_for(rows):
        return next((row["cost"] or 0.0 for row in rows if row["id"] == agent_id), None)

    on_before = _cost_for(await repo.get_agents_with_stats(limit=5, use_ledger=True))
    off_before = _cost_for(await repo.get_agents_with_stats(limit=5, use_ledger=False))
    assert on_before is not None, "seed agent must be within the returned set"

    db.add(_event(agent_id=agent_id, cost_usd=Decimal("0.40")))
    await db.flush()

    on_after = _cost_for(await repo.get_agents_with_stats(limit=5, use_ledger=True))
    off_after = _cost_for(await repo.get_agents_with_stats(limit=5, use_ledger=False))

    assert on_after - on_before == pytest.approx(0.40)
    assert off_after == pytest.approx(off_before)
