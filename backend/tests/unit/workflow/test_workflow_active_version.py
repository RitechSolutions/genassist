"""Resolving a workflow's active version — the pointer evaluation runs default to."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.services.workflow import WorkflowService


def _service(*, workflow, agent_workflow_id=None):
    """A service whose repository returns ``workflow`` and whose session returns
    ``agent_workflow_id`` for the agent lookup."""
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=workflow)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=agent_workflow_id)
    repository.db = MagicMock()
    repository.db.execute = AsyncMock(return_value=result)
    return WorkflowService(repository=repository)


@pytest.mark.asyncio
async def test_returns_the_agents_workflow_id():
    active = uuid4()
    service = _service(
        workflow=SimpleNamespace(id=uuid4(), agent_id=uuid4()),
        agent_workflow_id=active,
    )

    assert await service.get_active_version_id(uuid4()) == active


@pytest.mark.asyncio
async def test_returns_none_when_the_workflow_has_no_agent():
    service = _service(workflow=SimpleNamespace(id=uuid4(), agent_id=None))

    assert await service.get_active_version_id(uuid4()) is None
    service.repository.db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_returns_none_when_the_workflow_is_missing():
    service = _service(workflow=None)

    assert await service.get_active_version_id(uuid4()) is None
    service.repository.db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_bypasses_group_scope_so_every_caller_resolves_the_same_version():
    """Agents are group-scoped and workflows are not; without the bypass the
    lookup would silently return nothing for users outside the agent's group,
    and their runs would target a different version."""
    service = _service(
        workflow=SimpleNamespace(id=uuid4(), agent_id=uuid4()),
        agent_workflow_id=uuid4(),
    )

    await service.get_active_version_id(uuid4())

    statement = service.repository.db.execute.await_args.args[0]
    assert statement.get_execution_options().get(GROUP_SCOPE_BYPASS_FLAG) is True
