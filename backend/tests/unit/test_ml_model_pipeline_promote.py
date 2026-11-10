"""
Tests that promoting a pipeline run surfaces a ratio-target model's baseline
column as `inference_params.ratioBaselineColumn` on the MLModel row, so the
inference UI knows to ask for it - see MLModelInferenceNode's reconstruction
of the real-unit prediction, which needs that same baseline value supplied.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model_pipeline import PipelineRunStatus as PipelineRunStatusEnum
from app.schemas.ml_model_pipeline import (
    MLModelPipelineRunPromote,
    PipelineRunPromoteResponse,
)
from app.services.ml_model_pipeline import MLModelPipelineRunService


def _make_service(
    execution_output: dict,
    inference_params=None,
    features=None,
    add_default_file_id=True,
):
    model_id = uuid.uuid4()
    run_id = uuid.uuid4()
    config_id = uuid.uuid4()
    execution_output = execution_output.copy()
    if (
        add_default_file_id
        and "model_file_path" in execution_output
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
async def test_promote_missing_model_uses_not_found_status():
    service, _, _, model_id, run_id = _make_service({})
    service.model_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(AppException) as exc_info:
        await service.promote_run(
            model_id=model_id,
            run_id=run_id,
            promote_data=MLModelPipelineRunPromote(),
        )

    assert exc_info.value.error_key is ErrorKey.NOT_FOUND
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_promote_run_for_another_model_uses_not_found_status():
    service, _, _, model_id, run_id = _make_service({})
    service.run_repository.get_by_id.return_value.model_id = uuid.uuid4()

    with pytest.raises(AppException) as exc_info:
        await service.promote_run(
            model_id=model_id,
            run_id=run_id,
            promote_data=MLModelPipelineRunPromote(),
        )

    assert exc_info.value.error_key is ErrorKey.NOT_FOUND
    assert exc_info.value.status_code == 404


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
            "target_column": "y",
            "feature_columns": ["x"],
        },
        add_default_file_id=False,
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
    assert "predates stored model file IDs" in exc_info.value.error_detail
    assert exc_info.value.error_key is ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE
    service.config_repository.get_by_id.assert_not_awaited()
    service.config_repository.unset_default_for_model.assert_not_awaited()
    service.config_repository.update.assert_not_awaited()
    model_service.update.assert_not_awaited()
    model_manager.invalidate_model.assert_not_called()


@pytest.mark.asyncio
async def test_promote_distinguishes_failed_upload_from_historical_run():
    service, model_service, model_manager, model_id, run_id = _make_service(
        {
            "model_file_path": "/worker/models/new-run.pkl",
            "pkl_file_id": None,
            "registration_error": "upload failed",
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

    assert "was not uploaded to File Manager" in exc_info.value.error_detail
    assert "predates" not in exc_info.value.error_detail
    assert exc_info.value.error_key is ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE
    service.config_repository.get_by_id.assert_not_awaited()
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


@pytest.mark.asyncio
async def test_promote_rejects_incomplete_run_with_client_safe_reason(monkeypatch):
    from fastapi import Request

    from app.core.exceptions.exception_handler import _app_exception_body

    monkeypatch.setenv("ENV", "prod")
    service, model_service, _, model_id, run_id = _make_service({})
    service.run_repository.get_by_id.return_value.status = PipelineRunStatusEnum.RUNNING

    with pytest.raises(AppException) as exc_info:
        await service.promote_run(
            model_id=model_id,
            run_id=run_id,
            promote_data=MLModelPipelineRunPromote(),
        )

    assert exc_info.value.error_key is ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE
    request = Request({"type": "http", "headers": [], "query_string": b""})
    body = _app_exception_body(request, exc_info.value)
    assert body["error_detail"] == "Only completed pipeline runs can be promoted."
    service.config_repository.update.assert_not_awaited()
    model_service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_applies_run_metrics_with_its_file():
    pkl_file_id = str(uuid.uuid4())
    metrics = {"mse": 0.25, "rmse": 0.5, "mae": 0.4, "r2_score": 0.8}
    service, model_service, model_manager, model_id, run_id = _make_service(
        {
            "model_file_path": "/worker/models/run-a.pkl",
            "pkl_file_id": pkl_file_id,
            "target_column": "y",
            "feature_columns": ["x"],
            "metrics": metrics,
        }
    )

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=True),
    )

    model_service.update.assert_awaited_once()
    assert _model_update(model_service)["pkl_file_id"] == pkl_file_id
    assert model_service.update.await_args.kwargs["training_metrics"] == metrics
    model_manager.invalidate_model.assert_called_once_with(model_id)
    assert result["model_updated"] is True


@pytest.mark.asyncio
async def test_promote_without_metrics_lets_the_new_file_clear_them():
    service, model_service, _, model_id, run_id = _make_service(
        {"model_file_path": "/worker/models/run-a.pkl", "metrics": {"r2_score": 0.8}}
    )

    await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    # None tells MLModelsService.update the file changed without metrics.
    assert model_service.update.await_args.kwargs["training_metrics"] is None


@pytest.mark.asyncio
async def test_promote_skips_metrics_of_a_file_the_model_does_not_serve():
    service, model_service, model_manager, model_id, run_id = _make_service(
        {"pkl_file_id": str(uuid.uuid4()), "metrics": {"accuracy": 0.91}}
    )

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=False, update_metrics=True),
    )

    model_service.update.assert_not_awaited()
    model_manager.invalidate_model.assert_not_called()
    assert result["model_updated"] is False


@pytest.mark.asyncio
async def test_promote_updates_metrics_only_when_run_file_is_already_served():
    pkl_file_id = str(uuid.uuid4())
    metrics = {"accuracy": 0.91, "f1_score": 0.9}
    service, model_service, model_manager, model_id, run_id = _make_service(
        {"pkl_file_id": pkl_file_id, "metrics": metrics}
    )
    service.model_repository.get_by_id.return_value.pkl_file_id = pkl_file_id

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=False, update_metrics=True),
    )

    assert _model_update(model_service) == {}
    assert model_service.update.await_args.kwargs["training_metrics"] == metrics
    model_manager.invalidate_model.assert_not_called()
    assert result["model_updated"] is True


# Runs completed before training success was checked (e.g. a pipeline pointed
# at a chat workflow) can store any output, often not a dict. Promoting such a
# run must still make its pipeline the default instead of failing.
NON_MODEL_EXECUTION_OUTPUTS = [
    pytest.param({"output": "some text"}, id="output-string"),
    pytest.param({"output": None}, id="output-none"),
    pytest.param({"output": ["a"]}, id="output-list"),
    pytest.param({}, id="no-output-key"),
    pytest.param("text", id="execution-output-string"),
    pytest.param(["a"], id="execution-output-list"),
    pytest.param(None, id="execution-output-none"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_execution_output", NON_MODEL_EXECUTION_OUTPUTS)
@pytest.mark.parametrize("update_model_file", [True, False])
async def test_promote_run_without_model_output_only_sets_default_config(
    raw_execution_output, update_model_file
):
    service, model_service, model_manager, model_id, run_id = _make_service({})
    service.run_repository.get_by_id.return_value.execution_output = raw_execution_output

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=update_model_file),
    )

    response = PipelineRunPromoteResponse(**result)
    assert response.model_updated is False
    assert "no model file" in response.message
    assert response.warnings == []
    config_repository = service.config_repository
    config_repository.unset_default_for_model.assert_awaited_once_with(model_id)
    assert config_repository.update.await_args.args[1].is_default is True
    model_service.update.assert_not_awaited()
    model_manager.invalidate_model.assert_not_called()


@pytest.mark.asyncio
async def test_promote_trained_run_message_does_not_mention_missing_file():
    service, _, _, model_id, run_id = _make_service(
        {"model_file_path": "/tmp/model.pkl", "feature_columns": ["x"]}
    )

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True),
    )

    assert result["model_updated"] is True
    assert "no model file" not in result["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "malformed_fields, field_name",
    [
        pytest.param({"pkl_file_id": 123}, "pkl_file_id", id="pkl-file-id-int"),
        pytest.param({"target_column": ["y"]}, "target_column", id="target-column-list"),
        pytest.param({"feature_columns": "x"}, "feature_columns", id="feature-columns-string"),
        pytest.param({"feature_columns": [1, 2]}, "feature_columns", id="feature-columns-not-strings"),
        pytest.param({"target_transform": "ratio"}, "target_transform", id="target-transform-string"),
        pytest.param(
            {"target_transform": {"type": "ratio", "baselineColumn": ["base"]}},
            "target_transform",
            id="baseline-column-list",
        ),
        pytest.param(
            {"target_transform": {"type": "ratio", "baselineColumn": "  "}},
            "target_transform",
            id="baseline-column-blank",
        ),
        pytest.param({"target_column": "y" * 256}, "target_column", id="target-column-too-long"),
        pytest.param({"pkl_file_id": "f" * 501}, "pkl_file_id", id="pkl-file-id-too-long"),
    ],
)
async def test_promote_rejects_malformed_trained_run_before_any_updates(
    malformed_fields, field_name
):
    service, model_service, model_manager, model_id, run_id = _make_service(
        {
            "model_file_path": "/tmp/model.pkl",
            "pkl_file_id": str(uuid.uuid4()),
            "target_column": "y",
            "feature_columns": ["x"],
            **malformed_fields,
        },
        inference_params={"ratioBaselineColumn": "base"},
    )

    with pytest.raises(AppException) as exc_info:
        await service.promote_run(
            model_id=model_id,
            run_id=run_id,
            promote_data=MLModelPipelineRunPromote(update_model_file=True),
        )

    assert exc_info.value.error_key is ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE
    assert field_name in exc_info.value.error_detail
    service.config_repository.unset_default_for_model.assert_not_awaited()
    service.config_repository.update.assert_not_awaited()
    model_service.update.assert_not_awaited()
    model_manager.invalidate_model.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("warnings", [None, "text"])
async def test_promote_ignores_malformed_warnings_of_a_trained_run(warnings):
    service, model_service, _, model_id, run_id = _make_service(
        {"model_file_path": "/tmp/model.pkl", "feature_columns": ["x"], "warnings": warnings}
    )

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    assert PipelineRunPromoteResponse(**result).warnings == []
    assert result["model_updated"] is True
    assert _model_update(model_service)["features"] == ["x"]


@pytest.mark.asyncio
async def test_promote_without_model_file_skips_stale_default_warnings():
    service, model_service, _, model_id, run_id = _make_service(
        {
            "success": True,
            "warnings": [
                "Feature default(s) no longer match categories fitted by this run: kind."
            ],
        }
    )

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True),
    )

    assert result["model_updated"] is False
    assert "warnings" not in result
    assert "no model file" in result["message"]
    model_service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_ignores_target_transform_when_run_keeps_the_feature_contract():
    service, model_service, _, model_id, run_id = _make_service(
        {"model_file_path": "/tmp/model.pkl", "feature_columns": [], "target_transform": "ratio"}
    )

    result = await service.promote_run(
        model_id=model_id,
        run_id=run_id,
        promote_data=MLModelPipelineRunPromote(update_model_file=True, update_metrics=False),
    )

    assert result["model_updated"] is True
    assert set(_model_update(model_service)) == {"pkl_file_id"}


@pytest.mark.asyncio
async def test_promote_blames_invalid_saved_inference_settings_on_the_model():
    service, model_service, _, model_id, run_id = _make_service(
        {"model_file_path": "/tmp/model.pkl", "feature_columns": ["x"]},
        inference_params={"useTrainingFills": "true"},
    )

    with pytest.raises(AppException) as exc_info:
        await service.promote_run(
            model_id=model_id,
            run_id=run_id,
            promote_data=MLModelPipelineRunPromote(update_model_file=True),
        )

    assert exc_info.value.error_key is ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE
    assert "saved inference settings" in exc_info.value.error_detail
    assert "target_transform" not in exc_info.value.error_detail
    service.config_repository.unset_default_for_model.assert_not_awaited()
    model_service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_blames_saved_settings_even_when_run_fields_are_also_malformed():
    service, model_service, _, model_id, run_id = _make_service(
        {
            "model_file_path": "/tmp/model.pkl",
            "feature_columns": ["x"],
            "target_column": "y" * 256,
        },
        inference_params={"useTrainingFills": "true"},
    )

    with pytest.raises(AppException) as exc_info:
        await service.promote_run(
            model_id=model_id,
            run_id=run_id,
            promote_data=MLModelPipelineRunPromote(update_model_file=True),
        )

    detail = exc_info.value.error_detail
    assert exc_info.value.error_key is ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE
    assert "saved inference settings" in detail
    assert "target_column" in detail
    assert "inference_params" not in detail
    service.config_repository.unset_default_for_model.assert_not_awaited()
    model_service.update.assert_not_awaited()
