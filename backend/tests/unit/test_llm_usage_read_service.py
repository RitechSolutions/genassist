"""Unit tests for LlmUsageReadService canonical cost/coverage math"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models.llm_usage import LlmUsageEventModel
from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_read import LlmUsageReadService


class FakeReadRepo:

    def __init__(
        self,
        summary_row=None,
        breakdown_rows=None,
        scope=None,
        options=None,
        timeseries_rows=None,
        last_unpriced=None,
    ):
        self._summary = summary_row
        self._breakdown = breakdown_rows or []
        self._scope = scope
        self._options = options or {}
        self._timeseries = timeseries_rows or []
        self._last_unpriced = last_unpriced
        self.scope_resolutions = 0
        self.distinct_calls = []
        self.breakdown_calls = []
        self.pair_calls = []
        self.last_unpriced_calls = 0
        self.queries = []

    async def resolve_scope(self, params):
        self.scope_resolutions += 1
        return self._scope

    async def summary(self, params, scope):
        self.queries.append("summary")
        return self._summary

    async def last_unpriced_at(self):
        self.last_unpriced_calls += 1
        return self._last_unpriced

    async def timeseries(self, params, scope):
        self.queries.append("timeseries")
        return self._timeseries

    async def breakdown(self, params, scope, column, extra_conditions=None):
        self.queries.append("breakdown")
        self.breakdown_calls.append((column, extra_conditions))
        return self._breakdown

    async def distinct_values(self, params, scope, column, *, use_provider=True, use_model=True):
        self.distinct_calls.append((column.key, use_provider, use_model))
        return self._options.get(column.key, [])

    async def distinct_agent_ids(self, params, scope):
        self.distinct_calls.append(("agent_id", True, True))
        return self._options.get("agent_id", [])

    async def distinct_agent_workflow_pairs(self, params, scope, extra_conditions=None):
        self.pair_calls.append(extra_conditions)
        return self._options.get("pairs", [])


class FakeAgent:
    def __init__(self, id, name, workflow_id=None):
        self.id = id
        self.name = name
        self.workflow_id = workflow_id


class FakeAgentRepo:
    def __init__(self, agents=None):
        self._agents = agents or []

    async def get_by_ids(self, ids):
        return [a for a in self._agents if a.id in ids]


class FakeWorkflow:
    def __init__(self, id, nodes, created_at=None):
        self.id = id
        self.nodes = nodes
        self.created_at = created_at


class FakeWorkflowRepo:
    def __init__(self, workflows=None):
        self._workflows = workflows or []

    async def get_by_ids(self, ids):
        return [w for w in self._workflows if w.id in ids]


def _params(**overrides):
    return LlmUsageQueryParams(**overrides)


def _compiled(expression) -> str:
    return str(expression.compile(compile_kwargs={"literal_binds": True}))


def _node(node_id, name):
    return {"id": node_id, "type": "llmModelNode", "data": {"name": name}}


def _at(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def _service(
    summary_row=None,
    breakdown_rows=None,
    agents=None,
    scope=None,
    options=None,
    timeseries_rows=None,
    workflows=None,
    last_unpriced=None,
):
    repo = FakeReadRepo(summary_row, breakdown_rows, scope, options, timeseries_rows, last_unpriced)
    return LlmUsageReadService(repo, FakeAgentRepo(agents), FakeWorkflowRepo(workflows)), repo


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
    cache_read=0,
    cache_creation=0,
):
    return {
        "sum_cost": Decimal(cost),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "total_calls": calls,
        "unpriced_calls": unpriced,
        "configured_calls": configured,
        "fallback_calls": fallback,
        "legacy_estimate_calls": legacy,
        "priced_tokens": priced_tokens,
        "conversation_cost": Decimal(conv_cost),
        "agent_studio_test_cost": Decimal(studio_cost),
        "distinct_conversations": conversations,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
    }


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
async def test_cache_token_totals_are_carried_from_the_summary_row():
    service, *_ = _service(summary_row=_row(cache_read=3697, cache_creation=120))
    summ = await service.get_summary(_params())
    assert (summ.total_cache_read_tokens, summ.total_cache_creation_tokens) == (3697, 120)


@pytest.mark.asyncio
async def test_empty_scope_summary_reports_zero_cache_tokens():
    service, *_ = _service(summary_row=_row(cache_read=3697, cache_creation=120), scope=[])
    summ = await service.get_summary(_params(group_id=uuid4()))
    assert (summ.total_cache_read_tokens, summ.total_cache_creation_tokens) == (0, 0)


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
async def test_unpriced_calls_expose_the_tenant_wide_watermark():
    watermark = datetime(2026, 7, 30, 9, 15, tzinfo=timezone.utc)
    row = _row(calls=3, unpriced=1, configured=2)
    service, repo = _service(summary_row=row, last_unpriced=watermark)
    summ = await service.get_summary(_params())
    assert summ.last_unpriced_at == watermark
    assert repo.last_unpriced_calls == 1


@pytest.mark.asyncio
async def test_full_coverage_skips_the_watermark_query():
    row = _row(calls=4, unpriced=0, configured=4)
    service, repo = _service(summary_row=row, last_unpriced=datetime.now(timezone.utc))
    summ = await service.get_summary(_params())
    assert summ.last_unpriced_at is None
    assert repo.last_unpriced_calls == 0


@pytest.mark.asyncio
async def test_empty_scope_summary_has_no_watermark():
    service, repo = _service(scope=[])
    summ = await service.get_summary(_params())
    assert summ.last_unpriced_at is None
    assert repo.last_unpriced_calls == 0


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
    assert repo.queries == []


@pytest.mark.asyncio
async def test_export_report_on_an_empty_scope_returns_nothing_without_querying():
    service, repo = _service(summary_row=_row(), breakdown_rows=[("openai", Decimal("1"), 0, 5, 1)], scope=[])
    summary, breakdown = await service.get_export_report(_params(group_id=uuid4()), "provider")
    assert summary.total_cost_usd == 0.0 and summary.total_calls == 0
    assert breakdown.items == []
    assert repo.queries == []


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
async def test_breakdown_source_relabels_workflow_analyst_and_evaluations():
    rows = [
        ("workflow", Decimal("0.80"), 0, 900, 5),
        ("llm_analyst", Decimal("0.20"), 0, 300, 4),
        ("evaluation", Decimal("0.05"), 0, 200, 2),
    ]
    service, *_ = _service(breakdown_rows=rows)
    resp = await service.get_breakdown(_params(), "source")
    by = {i.key: i for i in resp.items}
    assert by["workflow"].label == "Workflow"
    assert by["llm_analyst"].label == "Conversation Analyst"
    assert by["evaluation"].label == "Evaluations"
    assert resp.dimension == "source"


@pytest.mark.asyncio
async def test_breakdown_evaluation_method_labels_the_two_judges():
    rows = [("llm_judge", Decimal("0.04"), 0, 150, 2), ("provenance_judge", Decimal("0.01"), 1, 50, 1)]
    service, *_ = _service(breakdown_rows=rows)
    resp = await service.get_breakdown(_params(), "evaluation_method")
    by = {i.key: i for i in resp.items}
    assert by["llm_judge"].label == "LLM Judge"
    assert by["provenance_judge"].label == "Provenance"
    assert by["provenance_judge"].cost_is_partial is True


@pytest.mark.asyncio
async def test_breakdown_evaluation_method_falls_back_to_the_raw_purpose():
    rows = [("some_future_judge", Decimal("0.01"), 0, 20, 1), (None, Decimal("0"), 0, 0, 1)]
    service, *_ = _service(breakdown_rows=rows)
    resp = await service.get_breakdown(_params(), "evaluation_method")
    by = {i.key: i for i in resp.items}
    assert by["some_future_judge"].label == "some_future_judge"
    assert by["unknown"].label == "Unknown"


@pytest.mark.asyncio
async def test_llm_dimension_groups_the_provider_model_pair():
    rows = [("openai · gpt-4o", Decimal("0.30"), 0, 500, 3)]
    service, repo = _service(breakdown_rows=rows)
    resp = await service.get_breakdown(_params(agent_id=uuid4()), "llm")
    assert resp.items[0].label == "openai · gpt-4o"
    column, _ = repo.breakdown_calls[0]
    assert "concat_ws" in str(column) and "coalesce" in str(column)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dimension,source_type",
    [("llm", "workflow"), ("evaluation_method", "evaluation"), ("node", "workflow")],
)
async def test_drill_down_dimensions_carry_their_source_type_filter(dimension, source_type):
    service, repo = _service(breakdown_rows=[])
    await service.get_breakdown(_params(), dimension)
    _, extra = repo.breakdown_calls[0]
    assert [_compiled(c) for c in extra] == [f"llm_usage_events.source_type = '{source_type}'"]


@pytest.mark.asyncio
@pytest.mark.parametrize("dimension", ["provider", "model", "agent", "source"])
async def test_page_wide_dimensions_add_no_extra_conditions(dimension):
    service, repo = _service(breakdown_rows=[])
    await service.get_breakdown(_params(), dimension)
    assert repo.breakdown_calls[0][1] is None


@pytest.mark.asyncio
async def test_breakdown_node_prefers_the_current_workflow_version_name():
    agent_id, old, current = uuid4(), uuid4(), uuid4()
    rows = [
        ("n1", Decimal("0.30"), 0, 500, 3),
        ("n2", Decimal("0.10"), 0, 100, 1),
        (None, Decimal("0.05"), 0, 50, 1),
        ("ghost", Decimal("0.01"), 0, 20, 1),
    ]
    service, _ = _service(
        breakdown_rows=rows,
        agents=[FakeAgent(agent_id, "Sales Bot", workflow_id=current)],
        options={"pairs": [(agent_id, old)]},
        workflows=[
            FakeWorkflow(old, [_node("n1", "Old step"), _node("n2", "Legacy step")], _at(1)),
            FakeWorkflow(current, [_node("n1", "New step")], _at(2)),
        ],
    )
    resp = await service.get_breakdown(_params(agent_id=agent_id), "node")
    by = {i.key: i for i in resp.items}
    assert (by["n1"].label, by["n1"].removed) == ("New step", False)
    assert (by["n2"].label, by["n2"].removed) == ("Legacy step", True)
    assert (by["unattributed"].label, by["unattributed"].removed) == ("Unattributed", None)
    assert (by["ghost"].label, by["ghost"].removed) == ("Unknown", None)


@pytest.mark.asyncio
async def test_breakdown_node_keeps_the_newest_surviving_name_for_a_deleted_node():
    agent_id, oldest, newer, current = uuid4(), uuid4(), uuid4(), uuid4()
    service, _ = _service(
        breakdown_rows=[("n1", Decimal("0.10"), 0, 100, 1)],
        agents=[FakeAgent(agent_id, "Sales Bot", workflow_id=current)],
        options={"pairs": [(agent_id, oldest), (agent_id, newer)]},
        workflows=[
            FakeWorkflow(oldest, [_node("n1", "First name")], _at(1)),
            FakeWorkflow(newer, [_node("n1", "Second name")], _at(2)),
            FakeWorkflow(current, [_node("n9", "Something else")], _at(3)),
        ],
    )
    resp = await service.get_breakdown(_params(agent_id=agent_id), "node")
    assert (resp.items[0].label, resp.items[0].removed) == ("Second name", True)


@pytest.mark.asyncio
async def test_breakdown_node_reports_unresolvable_nodes_as_unknown_without_a_removed_flag():
    agent_id, current = uuid4(), uuid4()
    service, _ = _service(
        breakdown_rows=[("gone", Decimal("0.10"), 0, 100, 1)],
        agents=[FakeAgent(agent_id, "Sales Bot", workflow_id=current)],
        options={"pairs": [(agent_id, current)]},
        workflows=[FakeWorkflow(current, [_node("n1", "Answer drafting")], _at(1))],
    )
    resp = await service.get_breakdown(_params(agent_id=agent_id), "node")
    # In-place deletes leave no stored name, so the row stays honest rather than claiming removal.
    assert (resp.items[0].label, resp.items[0].removed) == ("Unknown", None)


@pytest.mark.asyncio
async def test_breakdown_node_tolerates_malformed_node_entries():
    agent_id, current = uuid4(), uuid4()
    nodes = [
        "not-a-dict",
        {"type": "llmModelNode"},
        {"id": "n1", "data": None},
        {"id": "n2", "data": "text"},
        {"id": "n3", "data": {"name": 42}},
        _node("n4", "Answer drafting"),
    ]
    service, _ = _service(
        breakdown_rows=[("n1", Decimal("0.10"), 0, 100, 1), ("n4", Decimal("0.20"), 0, 200, 2)],
        agents=[FakeAgent(agent_id, "Sales Bot", workflow_id=current)],
        options={"pairs": [(agent_id, current)]},
        workflows=[FakeWorkflow(current, nodes, _at(1))],
    )
    resp = await service.get_breakdown(_params(agent_id=agent_id), "node")
    by = {i.key: i for i in resp.items}
    assert (by["n1"].label, by["n1"].removed) == ("Unknown", False)
    assert (by["n4"].label, by["n4"].removed) == ("Answer drafting", False)


@pytest.mark.asyncio
async def test_breakdown_node_disambiguates_duplicate_names():
    agent_id, current = uuid4(), uuid4()
    service, _ = _service(
        breakdown_rows=[("abcdef-one", Decimal("0.20"), 0, 200, 2), ("abcdef-two", Decimal("0.10"), 0, 100, 1)],
        agents=[FakeAgent(agent_id, "Sales Bot", workflow_id=current)],
        options={"pairs": [(agent_id, current)]},
        workflows=[
            FakeWorkflow(current, [_node("abcdef-one", "Summarizer"), _node("abcdef-two", "Summarizer")], _at(1))
        ],
    )
    resp = await service.get_breakdown(_params(agent_id=agent_id), "node")
    by = {i.key: i for i in resp.items}
    assert by["abcdef-one"].label == "Summarizer · abcdef-o"
    assert by["abcdef-two"].label == "Summarizer · abcdef-t"


@pytest.mark.asyncio
async def test_breakdown_node_matches_overlong_ids_via_the_ledger_clamp():
    agent_id, current = uuid4(), uuid4()
    long_id = "n" * 200
    service, _ = _service(
        breakdown_rows=[(long_id[:128], Decimal("0.10"), 0, 100, 1)],
        agents=[FakeAgent(agent_id, "Sales Bot", workflow_id=current)],
        options={"pairs": [(agent_id, current)]},
        workflows=[FakeWorkflow(current, [_node(long_id, "Long node")], _at(1))],
    )
    resp = await service.get_breakdown(_params(agent_id=agent_id), "node")
    assert (resp.items[0].label, resp.items[0].removed) == ("Long node", False)


@pytest.mark.asyncio
async def test_breakdown_node_handles_null_created_at_versions():
    agent_id, undated, current = uuid4(), uuid4(), uuid4()
    service, _ = _service(
        breakdown_rows=[("n1", Decimal("0.10"), 0, 100, 1)],
        agents=[FakeAgent(agent_id, "Sales Bot", workflow_id=current)],
        options={"pairs": [(agent_id, undated)]},
        workflows=[
            FakeWorkflow(undated, [_node("n1", "Undated step")], None),
            FakeWorkflow(current, [_node("n2", "Current step")], _at(2)),
        ],
    )
    resp = await service.get_breakdown(_params(agent_id=agent_id), "node")
    assert (resp.items[0].label, resp.items[0].removed) == ("Undated step", True)


@pytest.mark.asyncio
async def test_breakdown_node_skips_name_resolution_when_no_rows():
    service, repo = _service(breakdown_rows=[])
    resp = await service.get_breakdown(_params(agent_id=uuid4()), "node")
    assert resp.items == []
    assert repo.pair_calls == []


@pytest.mark.asyncio
async def test_breakdown_node_passes_the_drill_down_filter_to_the_pairs_query():
    service, repo = _service(breakdown_rows=[("n1", Decimal("0.10"), 0, 100, 1)])
    await service.get_breakdown(_params(agent_id=uuid4()), "node")
    assert [_compiled(c) for c in repo.pair_calls[0]] == ["llm_usage_events.source_type = 'workflow'"]


@pytest.mark.asyncio
@pytest.mark.parametrize("dimension", ["provider", "model", "agent", "source", "llm", "evaluation_method"])
async def test_removed_stays_null_on_every_other_dimension(dimension):
    service, _ = _service(breakdown_rows=[("openai", Decimal("0.10"), 0, 100, 1)])
    resp = await service.get_breakdown(_params(), dimension)
    assert resp.items[0].removed is None


def test_scope_conditions_always_exclude_soft_deleted():
    from app.repositories.llm_usage_read import LlmUsageReadRepository

    conds = LlmUsageReadRepository._conditions(_params(from_date=date(2026, 1, 1)), None)
    assert any(LlmUsageEventModel.is_deleted.key in str(c) for c in conds)
