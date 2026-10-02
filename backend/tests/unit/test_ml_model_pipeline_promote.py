"""
Tests that promoting a pipeline run surfaces a ratio-target model's baseline
column as `inference_params.ratioBaselineColumn` on the MLModel row, so the
inference UI knows to ask for it - see MLModelInferenceNode's reconstruction
of the real-unit prediction, which needs that same baseline value supplied.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.ml_model_pipeline import PipelineRunStatus as PipelineRunStatusEnum
from app.schemas.ml_model_pipeline import MLModelPipelineRunPromote
from app.services.ml_model_pipeline import MLModelPipelineRunService


def _make_service(execution_output: dict):
    model_id = uuid.uuid4()
    run_id = uuid.uuid4()
    config_id = uuid.uuid4()

    run = MagicMock()
    run.model_id = model_id
    run.status = PipelineRunStatusEnum.COMPLETED
    run.execution_output = {"output": execution_output}
    run.pipeline_config_id = config_id

    config = MagicMock()
    config.id = config_id
    config.model_id = model_id

    run_repository = MagicMock()
    run_repository.get_by_id = AsyncMock(return_value=run)

    config_repository = MagicMock()
    config_repository.get_by_id = AsyncMock(return_value=config)
    config_repository.unset_default_for_model = AsyncMock()
    config_repository.update = AsyncMock(return_value=config)

    model_repository = MagicMock()
    model_repository.get_by_id = AsyncMock(return_value=MagicMock())
    model_repository.update = AsyncMock()

    workflow_repository = MagicMock()

    service = MLModelPipelineRunService(
        run_repository=run_repository,
        config_repository=config_repository,
        model_repository=model_repository,
        workflow_repository=workflow_repository,
    )
    return service, model_repository, model_id, run_id


@pytest.mark.asyncio
async def test_promote_surfaces_ratio_baseline_column_as_inference_params():
    service, model_repository, model_id, run_id = _make_service({
        "model_file_path": "/tmp/model.pkl",
        "target_column": "y",
        "feature_columns": ["x"],
        "target_transform": {"type": "ratio", "baselineColumn": "base"},
    })

    await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    assert model_repository.update.await_count == 1
    _, update_dict = model_repository.update.await_args.args
    assert update_dict["inference_params"] == {"ratioBaselineColumn": "base"}


@pytest.mark.asyncio
async def test_promote_without_ratio_target_sets_inference_params_none():
    service, model_repository, model_id, run_id = _make_service({
        "model_file_path": "/tmp/model.pkl",
        "target_column": "y",
        "feature_columns": ["x"],
    })

    await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    assert model_repository.update.await_count == 1
    _, update_dict = model_repository.update.await_args.args
    assert update_dict["inference_params"] is None
