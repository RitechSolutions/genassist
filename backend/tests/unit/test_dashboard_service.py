"""Unit tests for DashboardService reading cost straight from the ledger repository"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.dashboard import DashboardService

TOTAL_COST = 99.99
AGENT_COST = 2.22
PER_CONVERSATION = 0.55

FROM_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)
TO_DATE = datetime(2026, 1, 31, tzinfo=timezone.utc)

_UNSET = object()


class FakeDashboardRepo:
    def __init__(self, agent_id, visible_agent_ids=None):
        self._agent_id = agent_id
        self._visible_agent_ids = visible_agent_ids
        self.total_cost_calls = 0
        self.scope_calls = 0
        self.response_time_scope = _UNSET
        self.total_cost_scope = _UNSET
        self.agents_kwargs = None

    async def get_active_agents_count(self):
        return 3

    async def get_workflow_runs_count(self, from_date, to_date):
        return 7

    async def resolve_visible_agent_ids(self):
        self.scope_calls += 1
        return self._visible_agent_ids

    async def get_avg_response_time(self, from_date, to_date, *, agent_ids):
        self.response_time_scope = agent_ids
        return 0 if agent_ids == [] else 250

    async def get_total_cost_usd(self, from_date, to_date, *, agent_ids):
        self.total_cost_calls += 1
        self.total_cost_scope = agent_ids
        return 0.0 if agent_ids == [] else TOTAL_COST

    async def get_agents_with_stats(self, from_date, to_date, limit):
        self.agents_kwargs = {"from_date": from_date, "to_date": to_date, "limit": limit}
        return [
            {
                "id": self._agent_id,
                "name": "Agent A",
                "is_active": True,
                "conversations_today": 4,
                "resolution_rate": 0.5,
                "avg_response_time_ms": 250,
                "cost": AGENT_COST,
                "cost_per_conversation": PER_CONVERSATION,
            }
        ]


def _service(visible_agent_ids=None):
    repo = FakeDashboardRepo(uuid4(), visible_agent_ids)
    return DashboardService(repo), repo


def test_service_takes_only_the_dashboard_repository():
    service, repo = _service()
    assert service.dashboard_repo is repo


@pytest.mark.asyncio
async def test_summary_reads_the_ledger_total():
    service, repo = _service()
    summary = await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert summary.total_cost_usd == TOTAL_COST
    assert repo.total_cost_calls == 1
    assert (summary.active_agents, summary.workflow_runs, summary.avg_response_time_ms) == (3, 7, 250)


@pytest.mark.asyncio
async def test_summary_resolves_visible_scope_once_and_passes_it_to_both_reads():
    scope = [uuid4()]
    service, repo = _service(visible_agent_ids=scope)
    await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert repo.scope_calls == 1
    assert repo.response_time_scope == scope
    assert repo.total_cost_scope == scope


@pytest.mark.asyncio
async def test_summary_passes_empty_scope_to_both_reads():
    service, repo = _service(visible_agent_ids=[])
    summary = await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert repo.response_time_scope == [] and repo.total_cost_scope == []
    assert (summary.avg_response_time_ms, summary.total_cost_usd) == (0, 0.0)


@pytest.mark.asyncio
async def test_agents_stats_surface_ledger_cost_and_per_conversation():
    service, repo = _service()
    response = await service.get_agents_stats(FROM_DATE, TO_DATE)
    agent = response.agents[0]
    assert float(agent.cost) == AGENT_COST
    assert float(agent.cost_per_conversation) == PER_CONVERSATION
    assert repo.agents_kwargs == {"from_date": FROM_DATE, "to_date": TO_DATE, "limit": 5}
