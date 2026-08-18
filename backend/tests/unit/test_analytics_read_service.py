"""Unit tests for AnalyticsReadService deriving the summary totals from the per-agent rows"""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.services.analytics_read import AnalyticsReadService

AGENT_A = uuid4()
AGENT_B = uuid4()

FROM_DATE = date(2026, 8, 1)
TO_DATE = date(2026, 8, 7)
ACTIVITY_FROM = datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc)
ACTIVITY_TO = datetime(2026, 8, 8, tzinfo=timezone.utc)

DAILY = {
    "total_executions": 12,
    "total_success": 10,
    "total_errors": 2,
    "avg_response_ms": 250.0,
    "avg_success_rate": 0.83,
    "total_rag_used": 4,
    "total_thumbs_up": 3,
    "total_thumbs_down": 1,
}

TOTALS = {
    "total_unique_conversations": 9,
    "total_finalized_conversations": 6,
    "total_in_progress_conversations": 3,
}

ZERO_TOTALS = {key: 0 for key in TOTALS}

GROUPED = [
    {
        "agent_id": AGENT_A,
        "unique_conversations": 5,
        "finalized_conversations": 4,
        "in_progress_conversations": 1,
    },
    {
        "agent_id": AGENT_B,
        "unique_conversations": 4,
        "finalized_conversations": 2,
        "in_progress_conversations": 2,
    },
]


class FakeAnalyticsReadRepo:
    def __init__(self, summary=None, grouped=None, comparison=None):
        self._summary = summary if summary is not None else {**DAILY, **TOTALS}
        self._grouped = grouped if grouped is not None else GROUPED
        self._comparison = comparison
        self.summary_kwargs = None
        self.comparison_kwargs = None
        self.grouped_calls = []

    async def get_agent_stats_summary(self, **kwargs):
        self.summary_kwargs = kwargs
        return dict(self._summary)

    async def get_conversation_status_counts(self, **kwargs):
        self.grouped_calls.append(kwargs)
        return [dict(row) for row in self._grouped]

    async def get_agent_stats_summary_with_comparison(self, **kwargs):
        self.comparison_kwargs = kwargs
        return self._comparison


def _service(**kwargs):
    repo = FakeAnalyticsReadRepo(**kwargs)
    return AnalyticsReadService(repo), repo


BOUNDS = {
    "from_date": FROM_DATE,
    "to_date": TO_DATE,
    "activity_from_datetime": ACTIVITY_FROM,
    "activity_to_datetime": ACTIVITY_TO,
}


@pytest.mark.asyncio
async def test_all_agents_summary_stops_the_repository_counting_conversations():
    service, repo = _service()
    await service.get_agent_stats_summary(**BOUNDS)
    assert repo.summary_kwargs["include_conversation_counts"] is False


@pytest.mark.asyncio
async def test_all_agents_summary_runs_one_grouped_query_over_the_same_window():
    service, repo = _service()
    await service.get_agent_stats_summary(**BOUNDS)
    assert len(repo.grouped_calls) == 1
    assert repo.grouped_calls[0] == {
        "agent_id": None,
        "group_id": None,
        "group_by_agent": True,
        **BOUNDS,
    }
    for key, value in BOUNDS.items():
        assert repo.summary_kwargs[key] == value


@pytest.mark.asyncio
async def test_all_agents_totals_are_the_sum_of_the_per_agent_rows():
    service, _ = _service(summary={**DAILY})
    summary = await service.get_agent_stats_summary(**BOUNDS)
    assert summary.total_unique_conversations == 9
    assert summary.total_finalized_conversations == 6
    assert summary.total_in_progress_conversations == 3
    assert [row.agent_id for row in summary.conversation_status_by_agent] == [AGENT_A, AGENT_B]
    assert (summary.total_executions, summary.total_errors) == (12, 2)
    assert summary.avg_response_ms == 250.0


@pytest.mark.asyncio
async def test_no_agent_activity_leaves_every_total_at_zero():
    service, _ = _service(summary={**DAILY}, grouped=[])
    summary = await service.get_agent_stats_summary(**BOUNDS)
    assert summary.total_unique_conversations == 0
    assert summary.total_finalized_conversations == 0
    assert summary.total_in_progress_conversations == 0
    assert summary.conversation_status_by_agent == []


@pytest.mark.asyncio
async def test_a_single_agent_summary_still_takes_its_totals_from_the_repository():
    service, repo = _service()
    summary = await service.get_agent_stats_summary(agent_id=AGENT_A, **BOUNDS)
    assert repo.summary_kwargs["include_conversation_counts"] is True
    assert repo.grouped_calls == []
    assert summary.total_unique_conversations == 9
    assert summary.conversation_status_by_agent == []


@pytest.mark.asyncio
async def test_a_group_scoped_summary_without_totals_is_built_from_the_grouped_rows():
    service, _ = _service(summary={**DAILY})
    summary = await service.get_agent_stats_summary(group_id=uuid4(), **BOUNDS)
    assert summary.total_unique_conversations == 9
    assert summary.total_finalized_conversations == 6
    assert summary.total_in_progress_conversations == 3


@pytest.mark.asyncio
async def test_a_denied_caller_keeps_the_hard_zero_totals_it_was_given():
    service, _ = _service(summary={**DAILY, **ZERO_TOTALS})
    summary = await service.get_agent_stats_summary(**BOUNDS)
    assert summary.total_unique_conversations == 0
    assert summary.total_finalized_conversations == 0
    assert summary.total_in_progress_conversations == 0


@pytest.mark.asyncio
async def test_the_comparison_path_still_lets_the_repository_count_conversations():
    comparison = {"current": {**DAILY, **TOTALS}, "previous": {**DAILY, **TOTALS}}
    service, repo = _service(comparison=comparison)
    result = await service.get_agent_stats_summary_with_comparison(from_date=FROM_DATE, to_date=TO_DATE)
    assert "include_conversation_counts" not in repo.comparison_kwargs
    assert repo.summary_kwargs is None
    assert len(repo.grouped_calls) == 1
    assert result["current"].total_unique_conversations == 9
    assert result["previous"].total_unique_conversations == 9
