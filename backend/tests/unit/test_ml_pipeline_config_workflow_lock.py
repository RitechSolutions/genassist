from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.ml_model_pipeline import MLModelPipelineConfigCreate, MLModelPipelineConfigUpdate
from app.services.ml_model_pipeline import MLModelPipelineConfigService


def _service(workflow):
    config_repository = MagicMock()
    config_repository.create = AsyncMock()
    config_repository.update = AsyncMock()
    config_repository.unset_default_for_model = AsyncMock()
    model_repository = MagicMock()
    model_repository.get_by_id = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    workflow_repository = MagicMock()
    workflow_repository.lock_live_shared = AsyncMock(return_value=workflow)
    return MLModelPipelineConfigService(
        config_repository=config_repository,
        model_repository=model_repository,
        workflow_repository=workflow_repository,
    )


@pytest.mark.asyncio
async def test_create_on_a_deleted_or_missing_workflow_is_refused():
    """Today the lookup result is ignored and the config is written anyway."""
    service = _service(workflow=False)
    workflow_id = uuid4()

    with pytest.raises(AppException) as exc:
        await service.create(MLModelPipelineConfigCreate(model_id=uuid4(), workflow_id=workflow_id))

    assert exc.value.status_code == 404
    assert exc.value.error_key == ErrorKey.WORKFLOW_NOT_FOUND
    service.workflow_repository.lock_live_shared.assert_awaited_once_with(
        workflow_id, visible_to_caller=True
    )
    service.config_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_onto_a_deleted_or_missing_workflow_is_refused():
    service = _service(workflow=False)
    model_id, config_id, workflow_id = uuid4(), uuid4(), uuid4()
    service.config_repository.get_by_id = AsyncMock(return_value=SimpleNamespace(id=config_id, model_id=model_id, workflow_id=uuid4()))

    with pytest.raises(AppException) as exc:
        await service.update(model_id, config_id, MLModelPipelineConfigUpdate(workflow_id=workflow_id))

    assert exc.value.status_code == 404
    assert exc.value.error_key == ErrorKey.WORKFLOW_NOT_FOUND
    service.workflow_repository.lock_live_shared.assert_awaited_once_with(
        workflow_id, visible_to_caller=True
    )
    service.config_repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_on_a_live_workflow_locks_it_and_writes_the_config():
    service = _service(workflow=True)
    workflow_id = uuid4()
    data = MLModelPipelineConfigCreate(model_id=uuid4(), workflow_id=workflow_id)
    service.config_repository.create = AsyncMock(return_value=SimpleNamespace())

    with patch("app.services.ml_model_pipeline.MLModelPipelineConfigRead.model_validate"):
        await service.create(data)

    service.workflow_repository.lock_live_shared.assert_awaited_once_with(
        workflow_id, visible_to_caller=True
    )
    service.config_repository.create.assert_awaited_once_with(data)


@pytest.mark.asyncio
async def test_update_without_a_workflow_change_takes_no_lock():
    service = _service(workflow=True)
    model_id, config_id = uuid4(), uuid4()
    service.config_repository.get_by_id = AsyncMock(return_value=SimpleNamespace(id=config_id, model_id=model_id))

    with patch("app.services.ml_model_pipeline.MLModelPipelineConfigRead.model_validate"):
        await service.update(model_id, config_id, MLModelPipelineConfigUpdate(cron_schedule="0 2 * * *"))

    service.workflow_repository.lock_live_shared.assert_not_awaited()
    service.config_repository.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_resending_the_current_workflow_takes_no_lock():
    """A config on a deleted workflow can still have its cron cleared."""
    service = _service(workflow=False)
    model_id, config_id, workflow_id = uuid4(), uuid4(), uuid4()
    service.config_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=config_id, model_id=model_id, workflow_id=workflow_id)
    )

    with patch("app.services.ml_model_pipeline.MLModelPipelineConfigRead.model_validate"):
        await service.update(
            model_id, config_id, MLModelPipelineConfigUpdate(workflow_id=workflow_id, cron_schedule="")
        )

    service.workflow_repository.lock_live_shared.assert_not_awaited()
    service.config_repository.update.assert_awaited_once()
