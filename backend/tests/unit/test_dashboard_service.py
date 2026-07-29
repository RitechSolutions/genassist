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


class FakeDashboardRepo:
    def __init__(self, agent_id):
        self._agent_id = agent_id
        self.total_cost_calls = 0
        self.agents_kwargs = None

    async def get_active_agents_count(self):
        return 3

    async def get_workflow_runs_count(self, from_date, to_date):
        return 7

    async def get_avg_response_time(self, from_date, to_date):
        return 250

    async def get_total_cost_usd(self, from_date, to_date):
        self.total_cost_calls += 1
        return TOTAL_COST

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


def _service():
    repo = FakeDashboardRepo(uuid4())
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
async def test_agents_stats_surface_ledger_cost_and_per_conversation():
    service, repo = _service()
    response = await service.get_agents_stats(FROM_DATE, TO_DATE)
    agent = response.agents[0]
    assert float(agent.cost) == AGENT_COST
    assert float(agent.cost_per_conversation) == PER_CONVERSATION
    assert repo.agents_kwargs == {"from_date": FROM_DATE, "to_date": TO_DATE, "limit": 5}
