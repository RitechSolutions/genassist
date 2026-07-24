"""Unit tests for the dashboard cost-source cutover: values follow the active source"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.repositories.dashboard import DashboardRepository
from app.schemas.llm_usage_control import COST_SOURCE_DAILY_STATS, COST_SOURCE_LEDGER
from app.services.dashboard import DashboardService

DAILY_TOTAL = 12.34
LEDGER_TOTAL = 99.99
DAILY_AGENT_COST = 1.11
LEDGER_AGENT_COST = 2.22
DAILY_PER_CONV = None
LEDGER_PER_CONV = 0.55


class FakeControl:
    def __init__(self, cutover_on):
        self.ledger_cutover_enabled = cutover_on


class FakeControlRepo:
    def __init__(self, control):
        self._control = control

    async def get_singleton(self):
        return self._control


class FakeDashboardRepo:

    def __init__(self, agent_id):
        self._agent_id = agent_id
        self.total_cost_calls = []
        self.agents_use_ledger = None

    async def get_active_agents_count(self):
        return 3

    async def get_workflow_runs_count(self, from_date, to_date):
        return 7

    async def get_avg_response_time(self, from_date, to_date):
        return 250

    async def get_total_cost_usd(self, from_date, to_date):
        self.total_cost_calls.append("daily_stats")
        return DAILY_TOTAL

    async def get_total_cost_usd_from_ledger(self, from_date, to_date):
        self.total_cost_calls.append("ledger")
        return LEDGER_TOTAL

    async def get_agents_with_stats(self, from_date, to_date, limit, use_ledger=False):
        self.agents_use_ledger = use_ledger
        cost = LEDGER_AGENT_COST if use_ledger else DAILY_AGENT_COST
        return [
            {
                "id": self._agent_id,
                "name": "Agent A",
                "is_active": True,
                "conversations_today": 4,
                "resolution_rate": 0.5,
                "avg_response_time_ms": 250,
                "cost": cost,
                "cost_per_conversation": LEDGER_PER_CONV if use_ledger else DAILY_PER_CONV,
            }
        ]


def _service(cutover_on, agent_id=None):
    repo = FakeDashboardRepo(agent_id or uuid4())
    return DashboardService(repo, FakeControlRepo(FakeControl(cutover_on))), repo


@pytest.mark.asyncio
async def test_summary_reads_daily_stats_when_cutover_off():
    service, repo = _service(cutover_on=False)
    summary = await service.get_summary_stats()
    assert summary.cost_source == COST_SOURCE_DAILY_STATS
    assert summary.total_cost_usd == DAILY_TOTAL
    assert repo.total_cost_calls == ["daily_stats"]


@pytest.mark.asyncio
async def test_summary_reads_ledger_when_cutover_on():
    service, repo = _service(cutover_on=True)
    summary = await service.get_summary_stats()
    assert summary.cost_source == COST_SOURCE_LEDGER
    assert summary.total_cost_usd == LEDGER_TOTAL
    assert repo.total_cost_calls == ["ledger"]


@pytest.mark.asyncio
async def test_summary_defaults_daily_stats_when_control_missing():
    repo = FakeDashboardRepo(uuid4())
    service = DashboardService(repo, FakeControlRepo(None))
    summary = await service.get_summary_stats()
    assert summary.cost_source == COST_SOURCE_DAILY_STATS
    assert repo.total_cost_calls == ["daily_stats"]


@pytest.mark.asyncio
async def test_agents_use_daily_stats_when_cutover_off():
    service, repo = _service(cutover_on=False)
    response = await service.get_agents_stats()
    assert repo.agents_use_ledger is False
    assert response.agents[0].cost_source == COST_SOURCE_DAILY_STATS
    assert float(response.agents[0].cost) == DAILY_AGENT_COST
    assert response.agents[0].cost_per_conversation is None


@pytest.mark.asyncio
async def test_agents_use_ledger_when_cutover_on():
    service, repo = _service(cutover_on=True)
    response = await service.get_agents_stats()
    assert repo.agents_use_ledger is True
    assert response.agents[0].cost_source == COST_SOURCE_LEDGER
    assert float(response.agents[0].cost) == LEDGER_AGENT_COST
    assert float(response.agents[0].cost_per_conversation) == LEDGER_PER_CONV


@pytest.mark.asyncio
async def test_agent_cost_today_routes_by_use_ledger():
    repo = DashboardRepository(None)
    calls = []

    async def fake_ledger(agent_ids, day_start, day_end):
        calls.append("ledger")
        return {}

    async def fake_daily(agent_ids, today):
        calls.append("daily_stats")
        return {}

    repo._agent_cost_today_ledger = fake_ledger
    repo._agent_cost_today_daily_stats = fake_daily
    day_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    await repo._agent_cost_today([], day_start, day_end, use_ledger=True)
    assert calls == ["ledger"]

    calls.clear()
    await repo._agent_cost_today([], day_start, day_end, use_ledger=False)
    assert calls == ["daily_stats"]
