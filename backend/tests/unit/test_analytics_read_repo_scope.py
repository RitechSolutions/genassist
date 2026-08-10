"""Unit tests proving the analytics reads are wired to the authorization resolver"""

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

    async def _conversation_counts(agent_id=None, group_id=None, from_date=None, to_date=None, *, group_by_agent=False):
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
