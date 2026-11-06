from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services.agent_config import AgentConfigService


def _service(workflow_delete):
    repository = MagicMock()
    repository.get_by_id_full = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    repository.soft_delete = AsyncMock()
    workflow_service = MagicMock()
    workflow_service.soft_delete_by_agent = workflow_delete
    db = MagicMock()
    db.commit = AsyncMock()
    return AgentConfigService(
        repository=repository,
        operator_service=MagicMock(),
        workflow_service=workflow_service,
        user_types_repository=MagicMock(),
        db=db,
    )


@pytest.mark.asyncio
async def test_agent_is_kept_when_its_workflow_trains_a_live_model():
    """The 409 comes before the agent row is touched, so nothing is half-deleted."""
    refusal = AppException(
        status_code=409, error_key=ErrorKey.AGENT_IN_USE_BY_ML_MODEL, error_variables=["Churn v2"]
    )
    service = _service(AsyncMock(side_effect=refusal))

    with pytest.raises(AppException) as exc:
        await service.delete(uuid4())

    assert exc.value.status_code == 409
    assert exc.value.error_key == ErrorKey.AGENT_IN_USE_BY_ML_MODEL
    service.repository.soft_delete.assert_not_awaited()
    service.db.commit.assert_not_awaited()
