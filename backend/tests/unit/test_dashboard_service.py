"""Unit tests for DashboardService reading cost straight from the ledger repository"""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.services.dashboard import DashboardService

TOTAL_COST = 99.99
AGENT_COST = 2.22
PER_CONVERSATION = 0.55
CONVERSATIONS = 7

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
        self.response_time_bounds = _UNSET
        self.total_cost_bounds = _UNSET
        self.total_cost_exact = _UNSET
        self.agents_kwargs = None

    async def get_active_agents_count(self):
        return 3

    async def resolve_visible_agent_ids(self):
        self.scope_calls += 1
        return self._visible_agent_ids

    async def get_avg_response_time(self, from_date, to_date, *, agent_ids):
        self.response_time_scope = agent_ids
        self.response_time_bounds = (from_date, to_date)
        return 0 if agent_ids == [] else 250

    async def get_total_cost_usd(self, from_date, to_date, *, agent_ids, exact=False):
        self.total_cost_calls += 1
        self.total_cost_scope = agent_ids
        self.total_cost_bounds = (from_date, to_date)
        self.total_cost_exact = exact
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


class FakeAnalyticsRepo:
    def __init__(self):
        self.conversation_kwargs = None

    async def get_conversation_status_counts(self, **kwargs):
        self.conversation_kwargs = kwargs
        return [{"total_unique_conversations": CONVERSATIONS}]


def _service(visible_agent_ids=None):
    repo = FakeDashboardRepo(uuid4(), visible_agent_ids)
    analytics_repo = FakeAnalyticsRepo()
    return DashboardService(repo, analytics_repo), repo, analytics_repo


def test_service_takes_the_dashboard_and_analytics_repositories():
    service, repo, analytics_repo = _service()
    assert service.dashboard_repo is repo
    assert service.analytics_repo is analytics_repo


@pytest.mark.asyncio
async def test_summary_reads_the_ledger_total():
    service, repo, _ = _service()
    summary = await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert summary.total_cost_usd == TOTAL_COST
    assert repo.total_cost_calls == 1
    assert (summary.active_agents, summary.conversations, summary.avg_response_time_ms) == (3, 7, 250)


@pytest.mark.asyncio
async def test_summary_counts_conversations_with_the_canonical_query():
    service, _, analytics_repo = _service()
    summary = await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert summary.conversations == CONVERSATIONS
    assert analytics_repo.conversation_kwargs["group_by_agent"] is False
    assert "agent_id" not in analytics_repo.conversation_kwargs
    assert "group_id" not in analytics_repo.conversation_kwargs


@pytest.mark.asyncio
async def test_summary_resolves_visible_scope_once_and_passes_it_to_both_reads():
    scope = [uuid4()]
    service, repo, _ = _service(visible_agent_ids=scope)
    await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert repo.scope_calls == 1
    assert repo.response_time_scope == scope
    assert repo.total_cost_scope == scope


@pytest.mark.asyncio
async def test_summary_serialises_workflow_runs_as_a_mirror_of_conversations():
    service, _, _ = _service()
    summary = await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert summary.conversations == summary.workflow_runs == CONVERSATIONS
    assert summary.model_dump()["workflow_runs"] == CONVERSATIONS


@pytest.mark.asyncio
async def test_legacy_mode_sends_utc_dates_to_conversations_and_rolling_buckets_to_stats():
    service, repo, analytics_repo = _service()
    await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert analytics_repo.conversation_kwargs["from_date"] == date(2026, 1, 1)
    assert analytics_repo.conversation_kwargs["to_date"] == date(2026, 1, 31)
    assert "activity_from_datetime" not in analytics_repo.conversation_kwargs
    assert repo.response_time_bounds == (date(2026, 1, 1), date(2026, 1, 31))
    assert repo.total_cost_bounds == (FROM_DATE, TO_DATE)
    assert repo.total_cost_exact is False


@pytest.mark.asyncio
async def test_exact_mode_sends_activity_instants_and_intersecting_buckets():
    service, repo, analytics_repo = _service()
    start = datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 8, tzinfo=timezone.utc)
    await service.get_summary_stats(start, end, exact=True)
    assert analytics_repo.conversation_kwargs["activity_from_datetime"] == start
    assert analytics_repo.conversation_kwargs["activity_to_datetime"] == end
    assert "from_date" not in analytics_repo.conversation_kwargs
    assert repo.response_time_bounds == (date(2026, 8, 1), date(2026, 8, 7))
    assert repo.total_cost_bounds == (start, end)
    assert repo.total_cost_exact is True


@pytest.mark.asyncio
async def test_summary_without_bounds_reads_all_time():
    service, repo, analytics_repo = _service()
    await service.get_summary_stats()
    assert analytics_repo.conversation_kwargs == {"group_by_agent": False}
    assert repo.response_time_bounds == (None, None)
    assert repo.total_cost_bounds == (None, None)


@pytest.mark.asyncio
async def test_summary_passes_empty_scope_to_both_reads():
    service, repo, _ = _service(visible_agent_ids=[])
    summary = await service.get_summary_stats(FROM_DATE, TO_DATE)
    assert repo.response_time_scope == [] and repo.total_cost_scope == []
    assert (summary.avg_response_time_ms, summary.total_cost_usd) == (0, 0.0)


@pytest.mark.asyncio
async def test_agents_stats_surface_ledger_cost_and_per_conversation():
    service, repo, _ = _service()
    response = await service.get_agents_stats(FROM_DATE, TO_DATE)
    agent = response.agents[0]
    assert float(agent.cost) == AGENT_COST
    assert float(agent.cost_per_conversation) == PER_CONVERSATION
    assert repo.agents_kwargs == {"from_date": FROM_DATE, "to_date": TO_DATE, "limit": 5}
