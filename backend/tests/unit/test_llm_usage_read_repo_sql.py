"""Unit tests asserting the SQL shape of the ledger reads without needing a database"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import app.db.models
import app.db.models.test_suite
from app.repositories.dashboard import DashboardRepository, _ledger_window
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_read import _DIMENSION_COLUMNS, _EXTRA_BREAKDOWN_CONDITIONS, LlmUsageReadService

WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 1, 31, tzinfo=timezone.utc)
BUCKET_FROM = date(2026, 1, 1)
BUCKET_TO = date(2026, 1, 31)


class _Result:
    def scalar(self):
        return 0

    def all(self):
        return []

    def mappings(self):
        return self

    def one(self):
        return {}


class CapturingDb:

    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result()


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _conditions_sql(params, scope=None, **flags) -> str:
    conds = LlmUsageReadRepository._conditions(params, scope, **flags)
    return " AND ".join(_sql(c) for c in conds)


def test_conditions_always_exclude_soft_deleted_rows():
    assert "is_deleted = 0" in _conditions_sql(LlmUsageQueryParams())


def test_date_bounds_are_half_open_on_utc_days():
    sql = _conditions_sql(LlmUsageQueryParams(from_date=date(2026, 1, 1), to_date=date(2026, 1, 31)))
    assert "occurred_at >= '2026-01-01 00:00:00+00:00'" in sql
    # Upper bound is exclusive of the day after to_date, so the last day is fully covered.
    assert "occurred_at < '2026-02-01 00:00:00+00:00'" in sql


def test_provider_and_model_filters_are_normalised():
    sql = _conditions_sql(LlmUsageQueryParams(provider=" OpenAI ", model=" GPT-4o "))
    assert "provider_key = 'openai'" in sql
    assert "model_key = 'gpt-4o'" in sql


def test_filter_flags_drop_the_selection_they_ignore():
    params = LlmUsageQueryParams(provider="openai", model="gpt-4o")
    providers_sql = _conditions_sql(params, use_provider=False, use_model=False)
    assert "provider_key" not in providers_sql and "model_key" not in providers_sql

    models_sql = _conditions_sql(params, use_model=False)
    assert "provider_key = 'openai'" in models_sql and "model_key" not in models_sql


def test_single_agent_scope_compares_directly():
    agent_id = uuid4()
    assert f"agent_id = '{agent_id}'" in _conditions_sql(LlmUsageQueryParams(), scope=[agent_id])


def test_multi_agent_scope_uses_in_clause():
    scope = [uuid4(), uuid4()]
    assert "agent_id IN" in _conditions_sql(LlmUsageQueryParams(), scope=scope)


@pytest.mark.asyncio
async def test_summary_counts_each_pricing_status():
    db = CapturingDb()
    await LlmUsageReadRepository(db).summary(LlmUsageQueryParams(), None)
    sql = _sql(db.statements[0])
    for status in ("configured", "fallback", "legacy_estimate"):
        assert f"pricing_status = '{status}'" in sql


@pytest.mark.asyncio
async def test_summary_sums_the_cache_token_buckets():
    db = CapturingDb()
    await LlmUsageReadRepository(db).summary(LlmUsageQueryParams(), None)
    sql = _sql(db.statements[0])
    assert "sum(llm_usage_events.cache_read_tokens)" in sql
    assert "sum(llm_usage_events.cache_creation_tokens)" in sql


@pytest.mark.asyncio
async def test_summary_reads_the_stored_prompt_total_instead_of_deriving_it():
    db = CapturingDb()
    await LlmUsageReadRepository(db).summary(LlmUsageQueryParams(), None)
    sql = _sql(db.statements[0])
    assert "sum(llm_usage_events.prompt_tokens)" in sql
    assert "provider_key IN" not in sql, "reads must not reapply provider reporting rules"
@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["timeseries", "breakdown"])
async def test_every_token_aggregate_shares_the_derived_total(query):
    db = CapturingDb()
    repo = LlmUsageReadRepository(db)
    if query == "timeseries":
        await repo.timeseries(LlmUsageQueryParams(), None)
    else:
        await repo.breakdown(LlmUsageQueryParams(), None, _DIMENSION_COLUMNS["provider"])
    sql = _sql(db.statements[0])
    assert "greatest(llm_usage_events.total_tokens, llm_usage_events.prompt_tokens" in sql
@pytest.mark.asyncio
async def test_summary_scopes_agent_studio_cost_to_the_two_studio_test_sources():
    db = CapturingDb()
    await LlmUsageReadRepository(db).summary(LlmUsageQueryParams(), None)
    sql = _sql(db.statements[0])
    assert "source IN ('workflow_test', 'node_test')" in sql
    # Suites, schedules and API/MCP runs are non-conversation too, but they are not studio tests.
    for other in ("test_suite", "schedule", "workflow_api", "mcp", "chat"):
        assert f"'{other}'" not in sql


@pytest.mark.asyncio
async def test_breakdown_without_extra_conditions_stays_all_source():
    db = CapturingDb()
    await LlmUsageReadRepository(db).breakdown(
        LlmUsageQueryParams(), None, _DIMENSION_COLUMNS["provider"]
    )
    assert "source_type" not in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_llm_dimension_groups_the_provider_model_pair_over_workflow_rows_only():
    db = CapturingDb()
    await LlmUsageReadRepository(db).breakdown(
        LlmUsageQueryParams(), None, _DIMENSION_COLUMNS["llm"], _EXTRA_BREAKDOWN_CONDITIONS["llm"]
    )
    sql = _sql(db.statements[0])
    assert "concat_ws" in sql and "coalesce(llm_usage_events.provider_key, 'unknown')" in sql
    assert "source_type = 'workflow'" in sql


@pytest.mark.asyncio
async def test_evaluation_method_dimension_groups_purpose_over_evaluation_rows_only():
    db = CapturingDb()
    await LlmUsageReadRepository(db).breakdown(
        LlmUsageQueryParams(),
        None,
        _DIMENSION_COLUMNS["evaluation_method"],
        _EXTRA_BREAKDOWN_CONDITIONS["evaluation_method"],
    )
    sql = _sql(db.statements[0])
    assert "llm_usage_events.purpose" in sql
    assert "source_type = 'evaluation'" in sql


@pytest.mark.asyncio
async def test_node_dimension_groups_node_id_over_workflow_rows_only():
    db = CapturingDb()
    await LlmUsageReadRepository(db).breakdown(
        LlmUsageQueryParams(), None, _DIMENSION_COLUMNS["node"], _EXTRA_BREAKDOWN_CONDITIONS["node"]
    )
    sql = _sql(db.statements[0])
    assert "GROUP BY llm_usage_events.node_id" in sql
    assert "source_type = 'workflow'" in sql


@pytest.mark.asyncio
async def test_distinct_agent_workflow_pairs_is_distinct_and_filtered():
    db = CapturingDb()
    agent_id = uuid4()
    params = LlmUsageQueryParams(from_date=date(2026, 1, 1), provider="OpenAI")
    await LlmUsageReadRepository(db).distinct_agent_workflow_pairs(
        params, [agent_id], _EXTRA_BREAKDOWN_CONDITIONS["node"]
    )
    sql = _sql(db.statements[0])
    assert "SELECT DISTINCT llm_usage_events.agent_id, llm_usage_events.workflow_id" in sql
    for clause in (
        "is_deleted = 0",
        f"agent_id = '{agent_id}'",
        "occurred_at >= '2026-01-01 00:00:00+00:00'",
        "provider_key = 'openai'",
        "source_type = 'workflow'",
    ):
        assert clause in sql


@pytest.mark.asyncio
async def test_extra_conditions_compose_with_scope_date_and_provider_filters():
    db = CapturingDb()
    agent_id = uuid4()
    params = LlmUsageQueryParams(from_date=date(2026, 1, 1), to_date=date(2026, 1, 31), provider="OpenAI")
    await LlmUsageReadRepository(db).breakdown(
        params, [agent_id], _DIMENSION_COLUMNS["llm"], _EXTRA_BREAKDOWN_CONDITIONS["llm"]
    )
    sql = _sql(db.statements[0])
    for clause in (
        "is_deleted = 0",
        f"agent_id = '{agent_id}'",
        "occurred_at >= '2026-01-01 00:00:00+00:00'",
        "occurred_at < '2026-02-01 00:00:00+00:00'",
        "provider_key = 'openai'",
        "source_type = 'workflow'",
    ):
        assert clause in sql


@pytest.mark.asyncio
async def test_dashboard_ledger_total_is_half_open_and_skips_deleted():
    db = CapturingDb()
    await DashboardRepository(db).get_total_cost_usd(
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 31, tzinfo=timezone.utc), agent_ids=None
    )
    sql = _sql(db.statements[0])
    assert "occurred_at >= '2026-01-01 00:00:00+00:00'" in sql
    assert "occurred_at < '2026-02-01 00:00:00+00:00'" in sql
    assert "is_deleted = 0" in sql


@pytest.mark.asyncio
async def test_dashboard_ledger_total_without_a_scope_has_no_agent_predicate():
    db = CapturingDb()
    await DashboardRepository(db).get_total_cost_usd(WINDOW_START, WINDOW_END, agent_ids=None)
    assert "agent_id" not in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_dashboard_ledger_total_restricts_to_the_visible_agents():
    db = CapturingDb()
    scope = [uuid4(), uuid4()]
    await DashboardRepository(db).get_total_cost_usd(WINDOW_START, WINDOW_END, agent_ids=scope)
    assert "agent_id IN" in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_dashboard_ledger_total_in_exact_mode_keeps_the_caller_instants():
    db = CapturingDb()
    await DashboardRepository(db).get_total_cost_usd(
        datetime(2026, 1, 1, 15, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 31, 9, 0, tzinfo=timezone.utc),
        agent_ids=None,
        exact=True,
    )
    sql = _sql(db.statements[0])
    assert "occurred_at >= '2026-01-01 15:30:00+00:00'" in sql
    assert "occurred_at < '2026-01-31 09:00:00+00:00'" in sql


@pytest.mark.asyncio
async def test_dashboard_ledger_total_without_bounds_has_no_date_predicate():
    db = CapturingDb()
    await DashboardRepository(db).get_total_cost_usd(agent_ids=None)
    sql = _sql(db.statements[0])
    assert "occurred_at" not in sql
    assert "is_deleted = 0" in sql


@pytest.mark.asyncio
async def test_dashboard_ledger_total_rejects_a_half_supplied_range():
    db = CapturingDb()
    with pytest.raises(ValueError):
        await DashboardRepository(db).get_total_cost_usd(WINDOW_START, None, agent_ids=None)
    assert db.statements == []


@pytest.mark.asyncio
async def test_dashboard_ledger_total_short_circuits_on_an_empty_scope():
    db = CapturingDb()
    total = await DashboardRepository(db).get_total_cost_usd(WINDOW_START, WINDOW_END, agent_ids=[])
    assert total == 0.0
    assert db.statements == []


@pytest.mark.asyncio
async def test_dashboard_response_time_without_a_scope_has_no_agent_predicate():
    db = CapturingDb()
    await DashboardRepository(db).get_avg_response_time(BUCKET_FROM, BUCKET_TO, agent_ids=None)
    assert "agent_id" not in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_dashboard_response_time_filters_on_inclusive_bucket_dates():
    db = CapturingDb()
    await DashboardRepository(db).get_avg_response_time(BUCKET_FROM, BUCKET_TO, agent_ids=None)
    sql = _sql(db.statements[0])
    assert "stat_date >= '2026-01-01'" in sql
    assert "stat_date <= '2026-01-31'" in sql
    assert "is_deleted = 0" in sql


@pytest.mark.asyncio
async def test_dashboard_response_time_without_bounds_has_no_date_predicate():
    db = CapturingDb()
    await DashboardRepository(db).get_avg_response_time(agent_ids=None)
    assert "stat_date" not in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_dashboard_response_time_restricts_to_the_visible_agents():
    db = CapturingDb()
    scope = [uuid4(), uuid4()]
    await DashboardRepository(db).get_avg_response_time(BUCKET_FROM, BUCKET_TO, agent_ids=scope)
    assert "agent_id IN" in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_dashboard_response_time_short_circuits_on_an_empty_scope():
    db = CapturingDb()
    avg = await DashboardRepository(db).get_avg_response_time(BUCKET_FROM, BUCKET_TO, agent_ids=[])
    assert avg == 0
    assert db.statements == []


@pytest.mark.asyncio
async def test_dashboard_agent_cost_today_is_half_open_and_skips_deleted():
    db = CapturingDb()
    day_start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    await DashboardRepository(db)._agent_cost_today([uuid4()], day_start, day_start + timedelta(days=1))
    sql = _sql(db.statements[0])
    assert "occurred_at >= '2026-01-15 00:00:00+00:00'" in sql
    assert "occurred_at < '2026-01-16 00:00:00+00:00'" in sql
    assert "is_deleted = 0" in sql


def test_ledger_window_is_half_open_on_whole_utc_days():
    start, end = _ledger_window(
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 31, tzinfo=timezone.utc)
    )
    assert start == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 2, 1, tzinfo=timezone.utc)


def test_ledger_window_rounds_a_mid_day_lower_bound_up():
    start, _ = _ledger_window(
        datetime(2026, 1, 1, 13, 30, tzinfo=timezone.utc), datetime(2026, 1, 31, 13, 30, tzinfo=timezone.utc)
    )
    assert start == datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_ledger_window_includes_the_whole_upper_bound_day():
    _, end = _ledger_window(
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 31, 13, 30, tzinfo=timezone.utc)
    )
    assert end == datetime(2026, 2, 1, tzinfo=timezone.utc)


def test_ledger_window_of_a_single_day_covers_that_day():
    day = datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert _ledger_window(day, day) == (day, day + timedelta(days=1))


@pytest.mark.asyncio
async def test_the_service_reads_exactly_the_labels_the_summary_selects():
    db = CapturingDb()
    await LlmUsageReadRepository(db).summary(LlmUsageQueryParams(), None)
    labels = {column.name: 0 for column in db.statements[0].selected_columns}

    class _Repo:
        async def summary(self, params, scope):
            return labels

        async def last_unpriced_at(self):
            return None

    summary = await LlmUsageReadService(_Repo(), None, None)._summary(LlmUsageQueryParams(), None)
    assert summary.total_calls == 0
