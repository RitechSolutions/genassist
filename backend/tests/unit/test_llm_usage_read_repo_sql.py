"""Unit tests asserting the SQL shape of the ledger reads without needing a database"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import app.db.models
import app.db.models.test_suite
from app.db.models.llm_usage import LlmUsageEventModel
from app.repositories.dashboard import DashboardRepository
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.schemas.llm_usage import LlmUsageQueryParams


class _Result:
    def scalar(self):
        return 0

    def all(self):
        return []

    def one(self):
        return ()


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
async def test_dashboard_ledger_total_is_half_open_and_skips_deleted():
    db = CapturingDb()
    await DashboardRepository(db).get_total_cost_usd_from_ledger(
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 31, tzinfo=timezone.utc)
    )
    sql = _sql(db.statements[0])
    assert "occurred_at >= '2026-01-01 00:00:00+00:00'" in sql
    assert "occurred_at < '2026-02-01 00:00:00+00:00'" in sql
    assert "is_deleted = 0" in sql


@pytest.mark.asyncio
async def test_dashboard_agent_cost_today_is_half_open_and_skips_deleted():
    db = CapturingDb()
    day_start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    await DashboardRepository(db)._agent_cost_today_ledger([uuid4()], day_start, day_start + timedelta(days=1))
    sql = _sql(db.statements[0])
    assert "occurred_at >= '2026-01-15 00:00:00+00:00'" in sql
    assert "occurred_at < '2026-01-16 00:00:00+00:00'" in sql
    assert "is_deleted = 0" in sql


@pytest.mark.asyncio
async def test_legacy_daily_stats_total_keeps_its_inclusive_raw_bounds():
    db = CapturingDb()
    from_date = datetime(2026, 1, 1, 13, 30, tzinfo=timezone.utc)
    to_date = datetime(2026, 1, 31, 13, 30, tzinfo=timezone.utc)
    await DashboardRepository(db).get_total_cost_usd(from_date, to_date)
    sql = _sql(db.statements[0])
    assert LlmUsageEventModel.__tablename__ not in sql
    assert "stat_date >= '2026-01-01 13:30:00+00:00'" in sql
    assert "stat_date <= '2026-01-31 13:30:00+00:00'" in sql
