"""
Tests that promoting a pipeline run surfaces a ratio-target model's baseline
column as `inference_params.ratioBaselineColumn` on the MLModel row, so the
inference UI knows to ask for it - see MLModelInferenceNode's reconstruction
of the real-unit prediction, which needs that same baseline value supplied.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model_pipeline import PipelineRunStatus as PipelineRunStatusEnum
from app.schemas.ml_model_pipeline import (
    MLModelPipelineRunPromote,
    PipelineRunPromoteResponse,
)
from app.services.ml_model_pipeline import MLModelPipelineRunService


def _make_service(execution_output: dict, inference_params=None, features=None):
    model_id = uuid.uuid4()
    run_id = uuid.uuid4()
    config_id = uuid.uuid4()
    execution_output = execution_output.copy()
    if (
        "model_file_path" in execution_output
        and "pkl_file_id" not in execution_output
    ):
        execution_output["pkl_file_id"] = str(uuid.uuid4())

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

    model = MagicMock()
    model.inference_params = inference_params
    model.features = features or ["x"]
    model.target_variable = "existing_target"
    model_repository = MagicMock()
    model_repository.get_by_id = AsyncMock(return_value=model)

    model_service = MagicMock()
    model_service.update = AsyncMock(return_value=model)
    model_manager = MagicMock()

    workflow_repository = MagicMock()

    service = MLModelPipelineRunService(
        run_repository=run_repository,
        config_repository=config_repository,
        model_repository=model_repository,
        model_service=model_service,
        model_manager=model_manager,
        workflow_repository=workflow_repository,
    )
    return service, model_service, model_manager, model_id, run_id


def _model_update(model_service: MagicMock) -> dict:
    update = model_service.update.await_args.args[1]
    return update.model_dump(exclude_unset=True)


@pytest.mark.asyncio
async def test_promote_surfaces_ratio_baseline_column_as_inference_params():
    service, model_service, _, model_id, run_id = _make_service(
        {
            "model_file_path": "/tmp/model.pkl",
            "target_column": "y",
            "feature_columns": ["x"],
            "target_transform": {"type": "ratio", "baselineColumn": "base"},
        },
        inference_params={
            "featureDefaults": {"x": 1, "removed": 2},
            "ratioBaselineColumn": "old_base",
        },
    )

    await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    assert model_service.update.await_count == 1
    update_dict = _model_update(model_service)
    assert update_dict["inference_params"] == {
        "featureDefaults": {"x": 1},
        "ratioBaselineColumn": "base",
    }


@pytest.mark.asyncio
async def test_promote_without_ratio_target_preserves_feature_defaults():
    service, model_service, _, model_id, run_id = _make_service(
        {
            "model_file_path": "/tmp/model.pkl",
            "target_column": "y",
            "feature_columns": ["x"],
        },
        inference_params={
            "featureDefaults": {"x": 1},
            "ratioBaselineColumn": "old_base",
        },
    )

    await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    assert model_service.update.await_count == 1
    update_dict = _model_update(model_service)
    assert update_dict["inference_params"] == {"featureDefaults": {"x": 1}}


@pytest.mark.asyncio
async def test_promote_without_existing_inference_params_keeps_none():
    service, model_service, _, model_id, run_id = _make_service({
        "model_file_path": "/tmp/model.pkl",
        "target_column": "y",
        "feature_columns": ["x"],
    })

    await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    update_dict = _model_update(model_service)
    assert update_dict["inference_params"] is None


@pytest.mark.asyncio
async def test_promote_keeps_training_fills_in_the_artifact():
    service, model_service, _, model_id, run_id = _make_service({
        "model_file_path": "/tmp/model.pkl",
        "target_column": "y",
        "feature_columns": ["x"],
        "missing_value_fills": {"x": 0},
    })

    await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    update_dict = _model_update(model_service)
    assert update_dict["inference_params"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("feature_columns", [None, []])
async def test_promote_without_usable_feature_columns_preserves_model_contract(
    feature_columns,
):
    service, model_service, _, model_id, run_id = _make_service(
        {
            "model_file_path": "/tmp/model.pkl",
            "feature_columns": feature_columns,
        },
        inference_params={
            "featureDefaults": {"x": 1},
            "ratioBaselineColumn": "existing_base",
        },
        features=["x"],
    )

    await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    update_dict = _model_update(model_service)
    assert set(update_dict) == {"pkl_file_id"}
    assert uuid.UUID(update_dict["pkl_file_id"])


@pytest.mark.asyncio
async def test_promote_rejects_legacy_run_without_file_id_before_any_updates():
    service, model_service, model_manager, model_id, run_id = _make_service(
        {
            "model_file_path": "/worker/models/legacy-run.pkl",
            "pkl_file_id": None,
            "target_column": "y",
            "feature_columns": ["x"],
        }
    )

    with pytest.raises(AppException) as exc_info:
        await service.promote_run(
            model_id=model_id,
            run_id=run_id,
            promote_data=MLModelPipelineRunPromote(
                update_model_file=True, update_metrics=False
            ),
        )

    assert "Run the pipeline again" in exc_info.value.error_detail
    service.config_repository.get_by_id.assert_not_awaited()
    service.config_repository.unset_default_for_model.assert_not_awaited()
    service.config_repository.update.assert_not_awaited()
    model_service.update.assert_not_awaited()
    model_manager.invalidate_model.assert_not_called()


@pytest.mark.asyncio
async def test_promote_warns_when_retained_default_is_not_a_fitted_category():
    service, model_service, _, model_id, run_id = _make_service(
        {
            "model_file_path": "/tmp/model.pkl",
            "target_column": "y",
            "feature_columns": ["kind"],
            "warnings": [
                "Feature default(s) no longer match categories fitted by this run: "
                "kind. Update or remove these defaults before relying on them during "
                "inference."
            ],
        },
        inference_params={"featureDefaults": {"kind": "removed"}},
        features=["kind"],
    )

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    update_dict = _model_update(model_service)
    assert update_dict["inference_params"] == {
        "featureDefaults": {"kind": "removed"}
    }
    assert "kind" in result["warnings"][0]
    assert "no longer match categories" in result["warnings"][0]

    response = PipelineRunPromoteResponse(**result)
    assert response.warnings == result["warnings"]
    assert response.model_dump()["warnings"] == result["warnings"]


@pytest.mark.asyncio
async def test_promote_switches_uploaded_file_id_and_invalidates_cache():
    pkl_file_id = str(uuid.uuid4())
    service, model_service, model_manager, model_id, run_id = _make_service(
        {
            "model_file_path": "/worker/models/run-a.pkl",
            "pkl_file_id": pkl_file_id,
            "target_column": "y",
            "feature_columns": ["age", "visits"],
        },
        features=["age", "tenure_months", "monthly_spend", "visits"],
    )

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    update_dict = _model_update(model_service)
    assert update_dict["pkl_file_id"] == pkl_file_id
    assert "pkl_file" not in update_dict
    assert update_dict["features"] == ["age", "visits"]
    model_service.update.assert_awaited_once()
    model_manager.invalidate_model.assert_called_once_with(model_id)
    assert result["model_updated"] is True
