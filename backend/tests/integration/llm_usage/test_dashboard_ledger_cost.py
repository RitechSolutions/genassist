"""Integration tests for the dashboard reading LLM cost from the ledger"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette_context import context, request_cycle_context

from app.core.config.settings import settings
from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationModel
from app.db.models.llm_usage import LlmUsageEventModel
from app.db.models.operator import OperatorModel
from app.repositories.dashboard import DashboardRepository
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_read import LlmUsageReadService


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
        "prompt_tokens": 100,
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


@contextmanager
def _admin_context():
    with request_cycle_context():
        context["user_id"] = uuid4()
        context["group_id"] = None
        context["supervised_group_ids"] = []
        context["user_roles"] = [SimpleNamespace(name="admin")]
        yield


@pytest.mark.asyncio
async def test_ledger_total_sums_priced_cost(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd(start, end, agent_ids=None)

    db.add(_event(cost_usd=Decimal("0.25")))
    await db.flush()

    after = await repo.get_total_cost_usd(start, end, agent_ids=None)
    assert after - before == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_ledger_total_excludes_unpriced(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd(start, end, agent_ids=None)

    db.add(_event(cost_usd=None, input_per_1k=None, output_per_1k=None, pricing_status="unpriced"))
    await db.flush()

    after = await repo.get_total_cost_usd(start, end, agent_ids=None)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_excludes_events_outside_window(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd(start, end, agent_ids=None)

    db.add(_event(cost_usd=Decimal("0.99"), occurred_at=start - timedelta(hours=1)))
    await db.flush()

    after = await repo.get_total_cost_usd(start, end, agent_ids=None)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_upper_bound_is_exclusive_of_the_next_day(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd(start, end, agent_ids=None)

    db.add(_event(cost_usd=Decimal("0.99"), occurred_at=start + timedelta(days=1)))
    await db.flush()

    after = await repo.get_total_cost_usd(start, end, agent_ids=None)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_drops_the_day_of_a_mid_day_lower_bound(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    mid_day = start + timedelta(hours=13)
    before = await repo.get_total_cost_usd(mid_day, end, agent_ids=None)

    db.add(_event(cost_usd=Decimal("0.99"), occurred_at=start + timedelta(hours=20)))
    await db.flush()

    after = await repo.get_total_cost_usd(mid_day, end, agent_ids=None)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_excludes_soft_deleted_events(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd(start, end, agent_ids=None)

    db.add(_event(cost_usd=Decimal("0.77"), is_deleted=1))
    await db.flush()

    after = await repo.get_total_cost_usd(start, end, agent_ids=None)
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
    before = _agent_cost(await repo._agent_cost_today([agent_id], start, end), agent_id)

    db.add(_event(agent_id=agent_id, cost_usd=Decimal("0.40")))
    # An unpriced call for the same agent must not lift the priced subtotal.
    db.add(_event(agent_id=agent_id, cost_usd=None, pricing_status="unpriced"))
    await db.flush()

    after = _agent_cost(await repo._agent_cost_today([agent_id], start, end), agent_id)
    assert after - before == pytest.approx(0.40)


@pytest.mark.asyncio
async def test_agent_cost_today_ledger_excludes_next_day(db):
    agent_id = (await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).limit(1))).scalar()
    if agent_id is None:
        pytest.skip("no agent available to attribute ledger cost to")

    repo = DashboardRepository(db)
    start, end = _today_window()
    before = _agent_cost(await repo._agent_cost_today([agent_id], start, end), agent_id)

    db.add(_event(agent_id=agent_id, cost_usd=Decimal("0.99"), occurred_at=end))
    await db.flush()

    after = _agent_cost(await repo._agent_cost_today([agent_id], start, end), agent_id)
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
    before = (await repo._agent_cost_today([agent_id], start, end)).get(agent_id, {})
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

    after = (await repo._agent_cost_today([agent_id], start, end)).get(agent_id, {})
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
    before = (await repo._agent_cost_today([agent_id], start, end)).get(agent_id, {})
    if before.get("cost_per_conversation") is not None:
        pytest.skip("agent already has conversation-attributed ledger rows today")

    priced_conv, unpriced_conv = uuid4(), uuid4()
    db.add(ConversationModel(id=priced_conv, operator_id=operator_id, conversation_type="chat"))
    db.add(ConversationModel(id=unpriced_conv, operator_id=operator_id, conversation_type="chat"))
    await db.flush()

    db.add(_event(agent_id=agent_id, conversation_id=priced_conv, cost_usd=Decimal("0.30")))
    db.add(_event(agent_id=agent_id, conversation_id=unpriced_conv, cost_usd=None, pricing_status="unpriced"))
    await db.flush()

    after = (await repo._agent_cost_today([agent_id], start, end)).get(agent_id, {})
    assert after["cost_per_conversation"] == pytest.approx(0.15)


@pytest.mark.asyncio
async def test_agent_cost_today_ledger_excludes_soft_deleted_events(db):
    agent_id = (await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).limit(1))).scalar()
    if agent_id is None:
        pytest.skip("no agent available to attribute ledger cost to")

    repo = DashboardRepository(db)
    start, end = _today_window()
    before = _agent_cost(await repo._agent_cost_today([agent_id], start, end), agent_id)

    db.add(_event(agent_id=agent_id, cost_usd=Decimal("0.77"), is_deleted=1))
    await db.flush()

    after = _agent_cost(await repo._agent_cost_today([agent_id], start, end), agent_id)
    assert after == pytest.approx(before)


@pytest.mark.asyncio
async def test_ledger_total_includes_analyst_source(db):
    repo = DashboardRepository(db)
    start, end = _today_range()
    before = await repo.get_total_cost_usd(start, end, agent_ids=None)

    db.add(_event(source_type="llm_analyst", source="conversation_analysis", cost_usd=Decimal("0.30")))
    await db.flush()

    after = await repo.get_total_cost_usd(start, end, agent_ids=None)
    assert after - before == pytest.approx(0.30)


@pytest.mark.asyncio
async def test_get_agents_with_stats_reports_ledger_cost_and_per_conversation(db):
    agent_id = (
        await db.execute(select(AgentModel.id).where(AgentModel.is_deleted == 0).order_by(AgentModel.name).limit(1))
    ).scalar()
    operator_id = (await db.execute(select(OperatorModel.id).limit(1))).scalar()
    if agent_id is None or operator_id is None:
        pytest.skip("need an agent and an operator to attribute ledger cost to")

    repo = DashboardRepository(db)

    def _row_for(rows):
        return next((row for row in rows if row["id"] == agent_id), None)

    before = _row_for(await repo.get_agents_with_stats(limit=5))
    assert before is not None, "seed agent must be within the returned set"

    conversation_id = uuid4()
    db.add(ConversationModel(id=conversation_id, operator_id=operator_id, conversation_type="chat"))
    await db.flush()
    db.add(_event(agent_id=agent_id, conversation_id=conversation_id, cost_usd=Decimal("0.40")))
    await db.flush()

    after = _row_for(await repo.get_agents_with_stats(limit=5))
    assert after["cost"] - (before["cost"] or 0.0) == pytest.approx(0.40)
    assert after["cost_per_conversation"] is not None


@pytest.mark.asyncio
async def test_cost_explorer_summary_total_matches_dashboard_total(db):
    dashboard_repo = DashboardRepository(db)
    read_service = LlmUsageReadService(LlmUsageReadRepository(db), None, None)
    start, end = _today_range()
    params = LlmUsageQueryParams(from_date=start.date(), to_date=end.date())

    dashboard_before = await dashboard_repo.get_total_cost_usd(start, end, agent_ids=None)
    with _admin_context():
        summary_before = (await read_service.get_summary(params)).total_cost_usd
    assert summary_before == pytest.approx(dashboard_before)

    db.add(_event(cost_usd=Decimal("0.65")))
    await db.flush()

    dashboard_after = await dashboard_repo.get_total_cost_usd(start, end, agent_ids=None)
    with _admin_context():
        summary_after = (await read_service.get_summary(params)).total_cost_usd
    assert summary_after == pytest.approx(dashboard_after)
    assert dashboard_after - dashboard_before == pytest.approx(0.65)
