"""Statement shapes of the workflow lineage lookups a Train Model node relies on"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import app.db.events.group_scope as group_scope
from app.db.events.soft_delete import SOFT_DELETE_FLAG, _soft_delete_filter
from app.repositories.workflow import WorkflowRepository


def _compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def _repository(rows=()):
    result = MagicMock()
    result.all = MagicMock(return_value=list(rows))
    result.first = MagicMock(return_value=None)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return WorkflowRepository(db=db)


@pytest.mark.asyncio
async def test_agent_ids_include_deleted_versions():
    deleted_version, agent_id = uuid4(), uuid4()
    repository = _repository([SimpleNamespace(id=deleted_version, agent_id=agent_id)])

    assert await repository.get_agent_ids([deleted_version]) == {deleted_version: agent_id}

    statement = repository.db.execute.await_args.args[0]
    state = SimpleNamespace(
        is_select=True,
        execution_options=dict(statement.get_execution_options()),
        statement=statement,
    )
    _soft_delete_filter(state)
    assert SOFT_DELETE_FLAG in state.execution_options
    assert "is_deleted" not in _compiled(state.statement)


async def _node_lookup_sql(agent_id) -> str:
    repository = _repository()
    with patch.object(
        group_scope, "context", {"group_id": "g-1", "user_id": "u-1", "supervised_group_ids": []}
    ), patch.object(group_scope, "current_user_is_admin", lambda: False):
        found = await repository.node_exists_outside(uuid4(), agent_id, "node-1", "Churn")
    assert found is False
    return _compiled(repository.db.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_node_lookup_reads_live_workflows_outside_the_run_without_agents():
    sql = await _node_lookup_sql(uuid4())

    assert "workflows.nodes @>" in sql
    assert "workflows.is_deleted =" in sql
    assert "workflows.id !=" in sql
    assert "workflows.agent_id IS DISTINCT FROM" in sql
    assert "agents" not in sql.replace("workflows", "")


@pytest.mark.asyncio
async def test_node_lookup_without_an_agent_skips_only_the_run_itself():
    sql = await _node_lookup_sql(None)

    assert "workflows.id !=" in sql
    assert "IS DISTINCT FROM" not in sql
