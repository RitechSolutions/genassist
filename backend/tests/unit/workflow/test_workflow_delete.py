from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions.error_messages import ErrorKey, get_error_message
from app.core.exceptions.exception_classes import AppException
from app.services.workflow import WorkflowService


def _service(*, workflow, agent_workflow_id=None, mcp_servers=(), ml_models=()):
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=workflow)
    repository.get_locked = AsyncMock(return_value=workflow)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=agent_workflow_id)
    repository.db = MagicMock()
    repository.db.execute = AsyncMock(return_value=result)
    repository.live_mcp_server_names = AsyncMock(return_value=list(mcp_servers))
    repository.live_ml_model_names = AsyncMock(return_value=list(ml_models))
    repository.repoint_test_data = AsyncMock()
    repository.soft_delete = AsyncMock()
    repository.delete = AsyncMock()
    return WorkflowService(repository=repository)


def _assert_nothing_written(service):
    service.repository.repoint_test_data.assert_not_awaited()
    service.repository.soft_delete.assert_not_awaited()
    service.repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_version_is_refused_before_any_write():
    """Today the delete goes through and the agent is left with no workflow."""
    version = uuid4()
    service = _service(
        workflow=SimpleNamespace(id=version, agent_id=uuid4()),
        agent_workflow_id=version,
    )

    with pytest.raises(AppException) as exc:
        await service.delete(version)

    assert exc.value.status_code == 409
    assert exc.value.error_key == ErrorKey.WORKFLOW_VERSION_ACTIVE
    _assert_nothing_written(service)


@pytest.mark.asyncio
async def test_version_exposed_by_a_live_mcp_server_is_refused_and_names_it():
    version = uuid4()
    service = _service(
        workflow=SimpleNamespace(id=version, agent_id=uuid4()),
        agent_workflow_id=uuid4(),
        mcp_servers=["Support tools", "Billing"],
    )

    with pytest.raises(AppException) as exc:
        await service.delete(version)

    assert exc.value.status_code == 409
    assert exc.value.error_key == ErrorKey.WORKFLOW_VERSION_IN_USE_BY_MCP_SERVER
    assert exc.value.error_variables == ["Support tools, Billing"]
    _assert_nothing_written(service)


@pytest.mark.asyncio
async def test_version_used_by_an_ml_pipeline_is_refused_and_names_the_model():
    version = uuid4()
    service = _service(
        workflow=SimpleNamespace(id=version, agent_id=uuid4()),
        agent_workflow_id=uuid4(),
        ml_models=["Churn v2"],
    )

    with pytest.raises(AppException) as exc:
        await service.delete(version)

    assert exc.value.status_code == 409
    assert exc.value.error_key == ErrorKey.WORKFLOW_VERSION_IN_USE_BY_ML_MODEL
    assert exc.value.error_variables == ["Churn v2"]
    _assert_nothing_written(service)


@pytest.mark.asyncio
async def test_delete_hides_the_version_and_moves_its_test_data_to_the_active_version():
    version, active = uuid4(), uuid4()
    workflow = SimpleNamespace(id=version, agent_id=uuid4())
    service = _service(workflow=workflow, agent_workflow_id=active)

    await service.delete(version)

    service.repository.repoint_test_data.assert_awaited_once_with(version, active)
    service.repository.soft_delete.assert_awaited_once_with(workflow)
    service.repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_without_an_active_version_test_data_is_unpinned():
    version = uuid4()
    workflow = SimpleNamespace(id=version, agent_id=None)
    service = _service(workflow=workflow)

    await service.delete(version)

    service.repository.repoint_test_data.assert_awaited_once_with(version, None)
    service.repository.soft_delete.assert_awaited_once_with(workflow)


@pytest.mark.parametrize(
    ("error_key", "expected"),
    [
        (
            ErrorKey.WORKFLOW_VERSION_IN_USE_BY_MCP_SERVER,
            "This version cannot be deleted while an MCP server exposes it as a tool (Support tools). "
            "Remove those tools first.",
        ),
        (
            ErrorKey.WORKFLOW_VERSION_IN_USE_BY_ML_MODEL,
            "This version cannot be deleted while an ML model's pipeline configuration uses it (Support tools). "
            "Remove those configurations first.",
        ),
    ],
)
def test_in_use_messages_name_what_blocks(error_key, expected):
    assert get_error_message(error_key, error_variables=["Support tools"]) == expected
