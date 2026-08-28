"""Unit tests for the analytics authorization resolver, asserting the SQL it emits"""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from starlette_context import context, request_cycle_context

import app.db.models
import app.db.models.test_suite
from app.core.utils import analytics_agent_scope
from app.core.utils.analytics_agent_scope import (
    get_authorized_agents_for_group,
    resolve_authorized_agent_ids,
)
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG


class _Result:
    def scalars(self):
        return self

    def all(self):
        return []


class CapturingDb:

    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result()


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@contextmanager
def caller(*, user_id=None, group_id=None, supervised=(), admin=False):
    with request_cycle_context():
        context["user_id"] = user_id
        context["group_id"] = group_id
        context["supervised_group_ids"] = list(supervised)
        context["user_roles"] = [SimpleNamespace(name="admin" if admin else "operator")]
        yield


@pytest.mark.asyncio
async def test_no_request_context_fails_closed_to_empty_scope():
    db = CapturingDb()
    assert await resolve_authorized_agent_ids(db) == []
    assert await get_authorized_agents_for_group(db, uuid4()) == []
    assert db.statements == []


@pytest.mark.asyncio
async def test_context_without_user_id_fails_closed():
    db = CapturingDb()
    with caller(user_id=None, group_id=uuid4()):
        assert await resolve_authorized_agent_ids(db) == []
        assert db.statements == []


@pytest.mark.asyncio
async def test_admin_without_a_filter_is_unrestricted_and_queries_nothing():
    db = CapturingDb()
    with caller(user_id=uuid4(), admin=True):
        assert await resolve_authorized_agent_ids(db) is None
        assert db.statements == []


@pytest.mark.asyncio
async def test_admin_agent_filter_is_taken_verbatim_without_a_query():
    db = CapturingDb()
    agent_id = uuid4()
    with caller(user_id=uuid4(), admin=True):
        assert await resolve_authorized_agent_ids(db, agent_id=agent_id) == [agent_id]
        assert db.statements == []


@pytest.mark.asyncio
async def test_admin_group_filter_delegates_to_the_bypassing_helper():
    db = CapturingDb()
    group_id = uuid4()
    with caller(user_id=uuid4(), admin=True):
        assert await resolve_authorized_agent_ids(db, group_id=group_id) == []
        stmt = db.statements[0]
        assert stmt.get_execution_options().get(GROUP_SCOPE_BYPASS_FLAG) is True
        sql = _sql(stmt)
        # The legacy 3-way group definition: creator, operator user, or workflow owner.
        assert "agents.created_by IN" in sql
        assert "operators.user_id IN" in sql
        assert "workflows.user_id IN" in sql
        assert f"users.group_id = '{group_id}'" in sql


@pytest.mark.asyncio
async def test_group_user_without_a_filter_is_limited_to_their_groups_agents():
    db = CapturingDb()
    group_id = uuid4()
    with caller(user_id=uuid4(), group_id=group_id):
        assert await resolve_authorized_agent_ids(db) == []
        stmt = db.statements[0]
        assert stmt.get_execution_options().get(GROUP_SCOPE_BYPASS_FLAG) is None
        sql = _sql(stmt)
        assert "agents.is_deleted = 0" in sql
        assert "agents.created_by IN (SELECT users.id" in sql
        assert f"users.group_id = '{group_id}'" in sql


@pytest.mark.asyncio
async def test_group_user_agent_filter_intersects_with_visibility():
    db = CapturingDb()
    agent_id = uuid4()
    with caller(user_id=uuid4(), group_id=uuid4()):
        await resolve_authorized_agent_ids(db, agent_id=agent_id)
        sql = _sql(db.statements[0])
        assert f"agents.id = '{agent_id}'" in sql
        assert "agents.created_by IN (SELECT users.id" in sql


@pytest.mark.asyncio
async def test_group_user_group_filter_intersects_with_visibility():
    db = CapturingDb()
    own_group, requested_group = uuid4(), uuid4()
    with caller(user_id=uuid4(), group_id=own_group):
        await resolve_authorized_agent_ids(db, group_id=requested_group)
        sql = _sql(db.statements[0])
        assert f"users.group_id = '{own_group}'" in sql
        assert f"users.group_id = '{requested_group}'" in sql
        assert "operators.user_id IN" in sql and "workflows.user_id IN" in sql


@pytest.mark.asyncio
async def test_group_user_with_both_filters_is_a_three_way_intersection():
    db = CapturingDb()
    agent_id, own_group, requested_group = uuid4(), uuid4(), uuid4()
    with caller(user_id=uuid4(), group_id=own_group):
        await resolve_authorized_agent_ids(db, agent_id=agent_id, group_id=requested_group)
        sql = _sql(db.statements[0])
        assert f"agents.id = '{agent_id}'" in sql
        assert f"users.group_id = '{own_group}'" in sql
        assert f"users.group_id = '{requested_group}'" in sql


@pytest.mark.asyncio
async def test_groupless_user_sees_only_their_own_agents():
    db = CapturingDb()
    user_id = uuid4()
    with caller(user_id=user_id):
        await resolve_authorized_agent_ids(db)
        assert f"agents.created_by = '{user_id}'" in _sql(db.statements[0])


@pytest.mark.asyncio
async def test_supervisor_sees_every_supervised_group_and_their_own():
    db = CapturingDb()
    own_group = uuid4()
    supervised = [uuid4(), uuid4()]
    with caller(user_id=uuid4(), group_id=own_group, supervised=supervised):
        await resolve_authorized_agent_ids(db)
        sql = _sql(db.statements[0])
        assert "users.group_id IN" in sql
        for gid in [own_group, *supervised]:
            assert f"'{gid}'" in sql


@pytest.mark.asyncio
async def test_non_admin_with_no_visibility_clause_fails_closed(monkeypatch):
    monkeypatch.setattr(analytics_agent_scope, "get_group_scope_clause", lambda model: None)
    db = CapturingDb()
    with caller(user_id=uuid4(), group_id=uuid4()):
        assert await resolve_authorized_agent_ids(db) == []
        assert await get_authorized_agents_for_group(db, uuid4()) == []
        assert db.statements == []


@pytest.mark.asyncio
async def test_group_dropdown_delegates_for_admins():
    db = CapturingDb()
    group_id = uuid4()
    with caller(user_id=uuid4(), admin=True):
        await get_authorized_agents_for_group(db, group_id)
        stmt = db.statements[0]
        assert stmt.get_execution_options().get(GROUP_SCOPE_BYPASS_FLAG) is True
        assert f"users.group_id = '{group_id}'" in _sql(stmt)


@pytest.mark.asyncio
async def test_group_dropdown_for_a_group_user_is_the_readable_intersection():
    db = CapturingDb()
    own_group, requested_group = uuid4(), uuid4()
    with caller(user_id=uuid4(), group_id=own_group):
        await get_authorized_agents_for_group(db, requested_group)
        stmt = db.statements[0]
        assert stmt.get_execution_options().get(GROUP_SCOPE_BYPASS_FLAG) is None
        sql = _sql(stmt)
        assert "agents.is_deleted = 0" in sql
        assert f"users.group_id = '{own_group}'" in sql
        assert f"users.group_id = '{requested_group}'" in sql
        assert "ORDER BY agents.name" in sql
