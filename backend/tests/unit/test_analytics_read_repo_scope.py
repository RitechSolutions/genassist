"""Unit tests proving the analytics reads are wired to the authorization resolver"""

import re
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

# Register every mapper before a statement is compiled.
import app.db.models  # noqa: F401
import app.db.models.test_suite  # noqa: F401
from app.repositories import analytics_read
from app.repositories.analytics_read import AnalyticsReadRepository


class _Result:
    def scalars(self):
        return self

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


def _repo_with_scope(monkeypatch, scope):
    db = CapturingDb()

    async def _resolver(_db, agent_id=None, group_id=None):
        return scope

    monkeypatch.setattr(analytics_read, "resolve_authorized_agent_ids", _resolver)
    return AnalyticsReadRepository(db), db


def _repo_with_conversation_scope(monkeypatch, scope):
    db = CapturingDb()

    async def _resolver(_db, agent_id=None, group_id=None):
        return scope

    monkeypatch.setattr(analytics_read, "resolve_scoped_agent_ids", _resolver)
    return AnalyticsReadRepository(db), db


def _repo_with_both_scopes(monkeypatch, scope):
    db = CapturingDb()

    async def _resolver(_db, agent_id=None, group_id=None):
        return scope

    monkeypatch.setattr(analytics_read, "resolve_authorized_agent_ids", _resolver)
    monkeypatch.setattr(analytics_read, "resolve_scoped_agent_ids", _resolver)
    return AnalyticsReadRepository(db), db


def _logged_at_predicates(sql: str) -> list[str]:
    return sorted(re.findall(r"agent_response_logs\.logged_at [<>=]+ '[^']+'", sql))


@pytest.mark.asyncio
async def test_agent_daily_stats_denied_scope_returns_nothing_without_querying(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [])
    assert await repo.get_agent_daily_stats(group_id=uuid4()) == []
    assert db.statements == []


@pytest.mark.asyncio
async def test_agent_daily_stats_restricts_to_the_authorized_agents(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [uuid4(), uuid4()])
    await repo.get_agent_daily_stats()
    assert "agent_id IN" in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_node_daily_stats_denied_scope_returns_nothing_without_querying(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [])
    assert await repo.get_node_daily_stats(group_id=uuid4()) == []
    assert db.statements == []


@pytest.mark.asyncio
async def test_node_daily_stats_restricts_to_the_authorized_agents(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [uuid4(), uuid4()])
    await repo.get_node_daily_stats()
    assert "agent_id IN" in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_node_breakdown_authorizes_before_it_queries(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [])
    assert await repo.get_node_type_breakdown(uuid4()) == []
    assert db.statements == []


@pytest.mark.asyncio
async def test_node_breakdown_keeps_its_equality_predicate_for_an_authorized_agent(monkeypatch):
    agent_id = uuid4()
    repo, db = _repo_with_scope(monkeypatch, [agent_id])
    await repo.get_node_type_breakdown(agent_id)
    assert f"agent_id = '{agent_id}'" in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_custom_attribute_keys_denied_scope_returns_nothing_without_querying(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [])
    assert await repo.get_custom_attribute_keys(agent_id=uuid4()) == []
    assert db.statements == []


@pytest.mark.asyncio
async def test_custom_attribute_keys_admin_agentless_group_now_returns_empty(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [])
    assert await repo.get_custom_attribute_keys(group_id=uuid4()) == []
    assert db.statements == []


@pytest.mark.asyncio
async def test_custom_attribute_keys_unrestricted_scope_reads_every_workflow(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, None)
    await repo.get_custom_attribute_keys()
    sql = _sql(db.statements[0])
    assert "FROM workflows" in sql
    assert "JOIN agents" not in sql


@pytest.mark.asyncio
async def test_custom_attribute_keys_joins_agents_for_a_restricted_scope(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [uuid4()])
    await repo.get_custom_attribute_keys()
    sql = _sql(db.statements[0])
    assert "JOIN agents" in sql
    assert "agents.id IN" in sql


@pytest.mark.asyncio
async def test_agent_stats_summary_keeps_the_conversation_tier_on_a_group_request(monkeypatch):
    agent_id, group_id = uuid4(), uuid4()
    repo, db = _repo_with_scope(monkeypatch, [])
    seen = {}

    async def _conversation_counts(agent_id=None, group_id=None, from_date=None, to_date=None, **kwargs):
        seen.update(agent_id=agent_id, group_id=group_id)
        return [
            {
                "total_unique_conversations": 4,
                "total_finalized_conversations": 3,
                "total_in_progress_conversations": 1,
            }
        ]

    monkeypatch.setattr(repo, "get_conversation_status_counts", _conversation_counts)

    summary = await repo.get_agent_stats_summary(agent_id=agent_id, group_id=group_id)

    assert summary["total_executions"] == 0
    assert summary["total_unique_conversations"] == 4
    assert seen == {"agent_id": agent_id, "group_id": group_id}
    assert db.statements == []


@pytest.mark.asyncio
async def test_agent_stats_summary_zeroes_everything_when_no_group_was_requested(monkeypatch):
    repo, db = _repo_with_scope(monkeypatch, [])
    summary = await repo.get_agent_stats_summary(agent_id=uuid4())
    assert summary["total_executions"] == 0
    assert summary["total_unique_conversations"] == 0
    assert db.statements == []


ACTIVITY_FROM = datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc)
ACTIVITY_TO = datetime(2026, 8, 8, tzinfo=timezone.utc)
LEGACY_FROM = date(2026, 8, 1)
LEGACY_TO = date(2026, 8, 7)


@pytest.mark.asyncio
async def test_conversation_counts_apply_the_exact_activity_window_half_open(monkeypatch):
    repo, db = _repo_with_conversation_scope(monkeypatch, None)
    await repo.get_conversation_status_counts(
        activity_from_datetime=ACTIVITY_FROM, activity_to_datetime=ACTIVITY_TO
    )
    sql = _sql(db.statements[0])
    assert "logged_at >= '2026-08-01 15:00:00+00:00'" in sql
    assert "logged_at < '2026-08-08 00:00:00+00:00'" in sql


@pytest.mark.asyncio
async def test_conversation_counts_keep_the_legacy_inclusive_utc_day_window(monkeypatch):
    repo, db = _repo_with_conversation_scope(monkeypatch, None)
    await repo.get_conversation_status_counts(from_date=LEGACY_FROM, to_date=LEGACY_TO)
    sql = _sql(db.statements[0])
    assert "logged_at >= '2026-08-01 00:00:00+00:00'" in sql
    assert "logged_at <= '2026-08-07 23:59:59.999999+00:00'" in sql


@pytest.mark.asyncio
async def test_exact_activity_bounds_replace_the_legacy_dates(monkeypatch):
    repo, db = _repo_with_conversation_scope(monkeypatch, None)
    await repo.get_conversation_status_counts(
        from_date=LEGACY_FROM,
        to_date=LEGACY_TO,
        activity_from_datetime=ACTIVITY_FROM,
        activity_to_datetime=ACTIVITY_TO,
    )
    sql = _sql(db.statements[0])
    assert "logged_at >= '2026-08-01 15:00:00+00:00'" in sql
    assert "logged_at < '2026-08-08 00:00:00+00:00'" in sql
    assert "23:59:59.999999" not in sql


@pytest.mark.asyncio
async def test_grouped_and_ungrouped_counts_share_the_same_activity_bounds(monkeypatch):
    repo, db = _repo_with_conversation_scope(monkeypatch, None)
    bounds = {"activity_from_datetime": ACTIVITY_FROM, "activity_to_datetime": ACTIVITY_TO}
    await repo.get_conversation_status_counts(group_by_agent=False, **bounds)
    await repo.get_conversation_status_counts(group_by_agent=True, **bounds)
    ungrouped, grouped = (_sql(stmt) for stmt in db.statements)
    assert _logged_at_predicates(ungrouped) == _logged_at_predicates(grouped)
    assert "GROUP BY" in grouped


@pytest.mark.asyncio
async def test_conversation_counts_only_exclude_deleted_response_logs(monkeypatch):
    repo, db = _repo_with_conversation_scope(monkeypatch, None)
    await repo.get_conversation_status_counts(
        activity_from_datetime=ACTIVITY_FROM, activity_to_datetime=ACTIVITY_TO
    )
    sql = _sql(db.statements[0])
    assert "agent_response_logs.is_deleted = 0" in sql
    for table in ("conversations", "agents", "operators"):
        assert f"{table}.is_deleted" not in sql


@pytest.mark.asyncio
async def test_conversation_counts_reject_a_half_supplied_activity_range(monkeypatch):
    repo, db = _repo_with_conversation_scope(monkeypatch, None)
    with pytest.raises(ValueError):
        await repo.get_conversation_status_counts(activity_from_datetime=ACTIVITY_FROM)
    assert db.statements == []


@pytest.mark.asyncio
async def test_agent_stats_summary_forwards_activity_bounds_to_the_conversation_query(monkeypatch):
    repo, _ = _repo_with_scope(monkeypatch, None)
    seen = {}

    async def _conversation_counts(**kwargs):
        seen.update(kwargs)
        return [{"total_unique_conversations": 2}]

    monkeypatch.setattr(repo, "get_conversation_status_counts", _conversation_counts)
    await repo.get_agent_stats_summary(
        from_date=LEGACY_FROM,
        to_date=LEGACY_TO,
        activity_from_datetime=ACTIVITY_FROM,
        activity_to_datetime=ACTIVITY_TO,
    )
    assert seen["activity_from_datetime"] == ACTIVITY_FROM
    assert seen["activity_to_datetime"] == ACTIVITY_TO
    assert (seen["from_date"], seen["to_date"]) == (LEGACY_FROM, LEGACY_TO)


@pytest.mark.asyncio
async def test_agent_stats_summary_reads_the_response_logs_by_default(monkeypatch):
    repo, db = _repo_with_both_scopes(monkeypatch, None)
    await repo.get_agent_stats_summary()
    statements = [_sql(stmt) for stmt in db.statements]
    assert any("agent_execution_daily_stats" in sql for sql in statements)
    assert any("agent_response_logs" in sql for sql in statements)


@pytest.mark.asyncio
async def test_agent_stats_summary_skips_the_response_logs_when_counts_are_excluded(monkeypatch):
    repo, db = _repo_with_both_scopes(monkeypatch, None)
    summary = await repo.get_agent_stats_summary(include_conversation_counts=False)
    statements = [_sql(stmt) for stmt in db.statements]
    assert len(statements) == 1
    assert "agent_execution_daily_stats" in statements[0]
    assert "agent_response_logs" not in statements[0]
    assert "total_unique_conversations" not in summary


@pytest.mark.asyncio
async def test_denied_caller_keeps_hard_zero_totals_without_conversation_counts(monkeypatch):
    repo, db = _repo_with_both_scopes(monkeypatch, [])
    summary = await repo.get_agent_stats_summary(agent_id=uuid4(), include_conversation_counts=False)
    assert summary["total_unique_conversations"] == 0
    assert summary["total_finalized_conversations"] == 0
    assert summary["total_in_progress_conversations"] == 0
    assert db.statements == []
