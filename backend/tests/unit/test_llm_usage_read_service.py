"""Unit tests for LlmUsageReadService canonical cost/coverage math"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models.llm_usage import LlmUsageEventModel
from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_read import LlmUsageReadService


class FakeReadRepo:

    def __init__(self, summary_row=None, breakdown_rows=None, scope=None, options=None, timeseries_rows=None):
        self._summary = summary_row
        self._breakdown = breakdown_rows or []
        self._scope = scope
        self._options = options or {}
        self._timeseries = timeseries_rows or []
        self.scope_resolutions = 0
        self.distinct_calls = []

    async def resolve_scope(self, params):
        self.scope_resolutions += 1
        return self._scope

    async def summary(self, params, scope):
        return self._summary

    async def timeseries(self, params, scope):
        return self._timeseries

    async def breakdown(self, params, scope, column):
        return self._breakdown

    async def distinct_values(self, params, scope, column, *, use_provider=True, use_model=True):
        self.distinct_calls.append((column.key, use_provider, use_model))
        return self._options.get(column.key, [])

    async def distinct_agent_ids(self, params, scope):
        self.distinct_calls.append(("agent_id", True, True))
        return self._options.get("agent_id", [])


class FakeAgent:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class FakeAgentRepo:
    def __init__(self, agents=None):
        self._agents = agents or []

    async def get_by_ids(self, ids):
        return [a for a in self._agents if a.id in ids]


def _params(**overrides):
    return LlmUsageQueryParams(**overrides)


def _service(summary_row=None, breakdown_rows=None, agents=None, scope=None, options=None, timeseries_rows=None):
    repo = FakeReadRepo(summary_row, breakdown_rows, scope, options, timeseries_rows)
    return LlmUsageReadService(repo, FakeAgentRepo(agents)), repo


def _row(
    cost="1.00",
    input_tokens=100,
    output_tokens=100,
    total_tokens=200,
    calls=4,
    unpriced=0,
    configured=4,
    fallback=0,
    legacy=0,
    priced_tokens=200,
    conv_cost="0.80",
    studio_cost="0.20",
    conversations=4,
):
    return (
        Decimal(cost),
        input_tokens,
        output_tokens,
        total_tokens,
        calls,
        unpriced,
        configured,
        fallback,
        legacy,
        priced_tokens,
        Decimal(conv_cost),
        Decimal(studio_cost),
        conversations,
    )


@pytest.mark.asyncio
async def test_cost_per_conversation_divides_by_distinct():
    service, *_ = _service(summary_row=_row())
    summ = await service.get_summary(_params())
    assert summ.total_cost_usd == 1.0
    assert summ.cost_per_conversation_usd == 0.20
    assert summ.agent_studio_test_cost_usd == 0.20
    assert summ.cost_is_partial is False
    assert summ.priced_token_coverage_pct == 100.0


@pytest.mark.asyncio
async def test_partial_cost_and_token_coverage():
    row = _row(
        cost="0.50",
        total_tokens=100,
        calls=3,
        unpriced=1,
        configured=2,
        priced_tokens=60,
        conv_cost="0.50",
        studio_cost="0",
        conversations=2,
    )
    service, *_ = _service(summary_row=row)
    summ = await service.get_summary(_params())
    assert summ.cost_is_partial is True
    assert summ.unpriced_calls == 1
    assert summ.priced_token_coverage_pct == 60.0
    assert summ.cost_per_conversation_usd == 0.25


@pytest.mark.asyncio
async def test_summary_reports_rate_provenance_counts():
    row = _row(calls=6, configured=3, fallback=2, legacy=1, unpriced=0)
    service, *_ = _service(summary_row=row)
    summ = await service.get_summary(_params())
    assert (summ.configured_calls, summ.fallback_calls, summ.legacy_estimate_calls) == (3, 2, 1)
    assert summ.configured_calls + summ.fallback_calls + summ.legacy_estimate_calls + summ.unpriced_calls == 6


@pytest.mark.asyncio
async def test_no_conversations_leaves_cost_per_conversation_null():
    row = _row(cost="0.10", conv_cost="0", studio_cost="0.10", conversations=0)
    service, *_ = _service(summary_row=row)
    summ = await service.get_summary(_params())
    assert summ.cost_per_conversation_usd is None
    assert summ.agent_studio_test_cost_usd == 0.10


@pytest.mark.asyncio
async def test_zero_cost_conversation_still_reports_real_zero():
    row = _row(cost="0", conv_cost="0", studio_cost="0", conversations=2)
    service, *_ = _service(summary_row=row)
    summ = await service.get_summary(_params())
    assert summ.cost_per_conversation_usd == 0.0


@pytest.mark.asyncio
async def test_no_calls_reports_full_coverage():
    row = _row(cost="0", total_tokens=0, calls=0, configured=0, priced_tokens=0, conversations=0)
    service, *_ = _service(summary_row=row)
    summ = await service.get_summary(_params())
    assert summ.priced_token_coverage_pct == 100.0


@pytest.mark.asyncio
async def test_priced_zero_token_calls_report_full_coverage():
    row = _row(cost="0", input_tokens=0, output_tokens=0, total_tokens=0, calls=2, configured=2, priced_tokens=0)
    service, *_ = _service(summary_row=row)
    summ = await service.get_summary(_params())
    assert summ.priced_token_coverage_pct == 100.0


@pytest.mark.asyncio
async def test_zero_token_unpriced_calls_never_fabricate_full_coverage():
    row = _row(
        cost="0", input_tokens=0, output_tokens=0, total_tokens=0, calls=4, unpriced=1, configured=3, priced_tokens=0
    )
    service, *_ = _service(summary_row=row)
    summ = await service.get_summary(_params())
    assert summ.priced_token_coverage_pct == 75.0


@pytest.mark.asyncio
async def test_timeseries_maps_each_day_row_to_an_item():
    rows = [
        (date(2026, 1, 1), Decimal("0.30"), 500, 3, 0),
        (date(2026, 1, 2), Decimal("0.10"), 100, 1, 1),
    ]
    service, _ = _service(timeseries_rows=rows)
    resp = await service.get_timeseries(_params())
    assert resp.total == 2
    assert [i.stat_date for i in resp.items] == [date(2026, 1, 1), date(2026, 1, 2)]
    assert [i.cost_usd for i in resp.items] == [0.30, 0.10]
    assert [i.unpriced_calls for i in resp.items] == [0, 1]


@pytest.mark.asyncio
async def test_empty_scope_returns_zeroed_responses_without_querying():
    service, repo = _service(summary_row=_row(), breakdown_rows=[("openai", Decimal("1"), 0, 5, 1)], scope=[])
    summ = await service.get_summary(_params(group_id=uuid4()))
    assert summ.total_calls == 0 and summ.total_cost_usd == 0.0
    assert summ.priced_token_coverage_pct == 100.0
    assert summ.cost_per_conversation_usd is None
    assert (await service.get_timeseries(_params())).items == []
    assert (await service.get_breakdown(_params(), "provider")).items == []
    options = await service.get_filter_options(_params())
    assert (options.providers, options.models, options.agents) == ([], [], [])
    assert repo.distinct_calls == []


@pytest.mark.asyncio
async def test_export_report_resolves_scope_once():
    service, repo = _service(summary_row=_row(), breakdown_rows=[("openai", Decimal("1"), 0, 5, 1)])
    summary, breakdown = await service.get_export_report(_params(), "provider")
    assert repo.scope_resolutions == 1
    assert summary.total_cost_usd == 1.0
    assert breakdown.dimension == "provider"


@pytest.mark.asyncio
async def test_filter_options_ignore_their_own_selection():
    options = {"provider_key": ["openai"], "model_key": ["gpt-4o"], "agent_id": []}
    service, repo = _service(options=options)
    await service.get_filter_options(_params(provider="openai", model="gpt-4o"))
    by_column = {c[0]: c for c in repo.distinct_calls}
    # Providers ignore both selections, models honour the provider, agents honour both.
    assert by_column["provider_key"] == ("provider_key", False, False)
    assert by_column["model_key"] == ("model_key", True, False)
    assert by_column["agent_id"] == ("agent_id", True, True)


@pytest.mark.asyncio
async def test_filter_options_name_and_sort_agents():
    first, second = uuid4(), uuid4()
    service, *_ = _service(
        options={"agent_id": [first, second]},
        agents=[FakeAgent(first, "Zeta Bot"), FakeAgent(second, "Alpha Bot")],
    )
    options = await service.get_filter_options(_params())
    assert [a.name for a in options.agents] == ["Alpha Bot", "Zeta Bot"]


@pytest.mark.asyncio
async def test_breakdown_provider_partial_flag():
    rows = [("openai", Decimal("0.30"), 0, 500, 3), ("anthropic", Decimal("0"), 1, 100, 1)]
    service, *_ = _service(breakdown_rows=rows)
    resp = await service.get_breakdown(_params(), "provider")
    by = {i.key: i for i in resp.items}
    assert by["openai"].cost_is_partial is False and by["openai"].calls == 3
    assert by["anthropic"].cost_is_partial is True and by["anthropic"].label == "anthropic"
    assert resp.dimension == "provider"


@pytest.mark.asyncio
async def test_breakdown_agent_resolves_names_and_unattributed():
    aid = uuid4()
    rows = [(aid, Decimal("0.10"), 0, 100, 1), (None, Decimal("0.05"), 0, 50, 1)]
    service, *_ = _service(breakdown_rows=rows, agents=[FakeAgent(aid, "Sales Bot")])
    resp = await service.get_breakdown(_params(), "agent")
    by = {i.key: i for i in resp.items}
    assert by[str(aid)].label == "Sales Bot"
    assert by["unattributed"].label == "Unattributed"


@pytest.mark.asyncio
async def test_breakdown_source_relabels_workflow_and_analyst():
    rows = [("workflow", Decimal("0.80"), 0, 900, 5), ("llm_analyst", Decimal("0.20"), 0, 300, 4)]
    service, *_ = _service(breakdown_rows=rows)
    resp = await service.get_breakdown(_params(), "source")
    by = {i.key: i for i in resp.items}
    assert by["workflow"].label == "Workflow"
    assert by["llm_analyst"].label == "Conversation Analyst"
    assert resp.dimension == "source"


def test_scope_conditions_always_exclude_soft_deleted():
    from app.repositories.llm_usage_read import LlmUsageReadRepository

    conds = LlmUsageReadRepository._conditions(_params(from_date=date(2026, 1, 1)), None)
    assert any(LlmUsageEventModel.is_deleted.key in str(c) for c in conds)
