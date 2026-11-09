"""
A pipeline run trains a new file for a registered model; it must not change
what the user set on that model. Its description stays as written, and its
type stays as registered. A run whose Train Model node trains another type is
refused instead of switching the type (for example, Random Forest to XGBoost).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model import ModelType as DbModelType
from app.db.models.ml_model_pipeline import PipelineRunStatus as PipelineRunStatusEnum
from app.dependencies.injector import injector
from app.modules.workflow.engine.nodes.ml.train_model_node import (
    ModelTypeMismatchError,
    TrainModelNode,
)
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.schemas.ml_model_pipeline import MLModelPipelineRunPromote
from app.services.ml_model_pipeline import MLModelPipelineRunService
from app.services.ml_models import MODEL_TYPE_LABELS, model_type_mismatch_message


def _make_node(node_id=None, initial_values=None) -> TrainModelNode:
    state = WorkflowState(workflow={})
    if initial_values is not None:
        state.initial_values = initial_values
    return TrainModelNode(node_id=node_id or str(uuid.uuid4()), node_config={}, state=state)


def _existing_model(model_type, description="Churn model for the EU stores"):
    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing.name = "Churn"
    existing.description = description
    existing.model_type = model_type
    existing.inference_params = None
    return existing


def _patch_dependencies(monkeypatch, ml_service):
    file_manager = MagicMock()
    provider = MagicMock()
    provider.get_base_path.return_value = "/data"
    provider.name = "local"
    file_manager.initialize = AsyncMock(return_value=provider)
    uploaded_file = MagicMock()
    uploaded_file.id = uuid.uuid4()
    file_manager.create_file_from_local_path = AsyncMock(return_value=uploaded_file)

    app_settings_service = MagicMock()
    app_settings_service.get_by_type_and_name = AsyncMock(return_value=MagicMock())

    from app.services.app_settings import AppSettingsService
    from app.services.file_manager import FileManagerService
    from app.services.ml_models import MLModelsService

    services = {
        FileManagerService: file_manager,
        AppSettingsService: app_settings_service,
        MLModelsService: ml_service,
    }
    monkeypatch.setattr(injector, "get", lambda cls: services[cls])
    return file_manager


def _ml_service(existing=None, by_name=None):
    ml_service = MagicMock()
    ml_service.get_by_id = AsyncMock(return_value=existing)
    ml_service.get_by_name = AsyncMock(return_value=by_name)
    ml_service.update = AsyncMock(return_value=existing or by_name)
    created = MagicMock()
    created.id = uuid.uuid4()
    ml_service.create = AsyncMock(return_value=created)
    return ml_service


async def _register(node, model_type, target_model_id=None, name="Churn"):
    return await node._register_trained_model(
        name=name,
        model_type=model_type,
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
        target_model_id=target_model_id,
    )


# -- model_type_mismatch_message ----------------------------------------------


def test_mismatch_message_names_both_types_with_ui_labels():
    message = model_type_mismatch_message("Churn", "random_forest", "xgboost")
    assert message is not None
    assert "'Churn' is registered as Random Forest" in message
    assert "set to XGBoost" in message
    assert "was not changed" in message


@pytest.mark.parametrize(
    "registered,trained",
    [
        ("random_forest", "random_forest"),
        (DbModelType.RANDOM_FOREST, "random_forest"),
        ("XGBoost", "xgboost"),
        (None, "xgboost"),
        ("xgboost", None),
    ],
)
def test_no_mismatch_for_same_type_or_missing_type(registered, trained):
    assert model_type_mismatch_message("Churn", registered, trained) is None


def test_every_model_type_has_a_label():
    assert set(MODEL_TYPE_LABELS) == {member.value for member in DbModelType}


def test_db_enum_is_compared_by_value():
    assert model_type_mismatch_message("Churn", DbModelType.RANDOM_FOREST, "xgboost")


# -- _register_trained_model --------------------------------------------------


@pytest.mark.asyncio
async def test_update_leaves_description_and_type_alone(monkeypatch):
    existing = _existing_model(DbModelType.RANDOM_FOREST)
    ml_service = _ml_service(existing=existing)
    _patch_dependencies(monkeypatch, ml_service)

    ml_model_id, pkl_file_id, error, warnings = await _register(
        _make_node(), "random_forest", target_model_id=str(existing.id)
    )

    assert error is None
    assert warnings == []
    assert ml_model_id == str(existing.id)
    assert pkl_file_id is not None
    update = ml_service.update.await_args.args[1]
    assert "description" not in update.model_fields_set
    assert "model_type" not in update.model_fields_set
    assert update.pkl_file_id == pkl_file_id


@pytest.mark.asyncio
async def test_create_sets_description_marker_and_type(monkeypatch):
    ml_service = _ml_service()
    _patch_dependencies(monkeypatch, ml_service)
    node = _make_node()

    _, _, error, _ = await _register(node, "xgboost", name="Brand new")

    assert error is None
    create = ml_service.create.await_args.args[0]
    assert create.model_type.value == "xgboost"
    assert f"[train-model-node:{node.node_id}]" in create.description


@pytest.mark.asyncio
async def test_pipeline_target_of_another_type_fails_without_uploading(monkeypatch):
    existing = _existing_model(DbModelType.RANDOM_FOREST)
    ml_service = _ml_service(existing=existing)
    file_manager = _patch_dependencies(monkeypatch, ml_service)

    # Raised (not returned) so the node, and the pipeline run, fail.
    with pytest.raises(ModelTypeMismatchError) as excinfo:
        await _register(_make_node(), "xgboost", target_model_id=str(existing.id))

    assert "registered as Random Forest" in excinfo.value.error_detail
    # Checked before the upload, so no orphaned file is left behind.
    file_manager.create_file_from_local_path.assert_not_awaited()
    ml_service.update.assert_not_awaited()
    ml_service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_target_lookup_failure_falls_back_and_keeps_the_file(monkeypatch):
    ml_service = _ml_service()
    ml_service.get_by_id = AsyncMock(side_effect=RuntimeError("db hiccup"))
    file_manager = _patch_dependencies(monkeypatch, ml_service)

    ml_model_id, pkl_file_id, error, _ = await _register(
        _make_node(), "xgboost", target_model_id=str(uuid.uuid4()), name="Brand new"
    )

    assert error is None
    assert ml_model_id is not None
    assert pkl_file_id == str(file_manager.create_file_from_local_path.return_value.id)


@pytest.mark.asyncio
async def test_registry_lookup_failure_keeps_the_uploaded_file(monkeypatch):
    ml_service = _ml_service()
    ml_service.get_by_name = AsyncMock(side_effect=RuntimeError("db unavailable"))
    file_manager = _patch_dependencies(monkeypatch, ml_service)

    _, pkl_file_id, error, _ = await _register(_make_node(), "xgboost")

    assert error == "db unavailable"
    assert pkl_file_id == str(file_manager.create_file_from_local_path.return_value.id)


@pytest.mark.asyncio
async def test_node_own_ad_hoc_model_follows_the_node_type_but_keeps_description(monkeypatch):
    node = _make_node()
    description = f"My notes [train-model-node:{node.node_id}]"
    own = _existing_model("linear_regression", description=description)
    ml_service = _ml_service(by_name=own)
    _patch_dependencies(monkeypatch, ml_service)

    ml_model_id, _, error, _ = await _register(node, "ridge_regression", name="Train Model")

    assert error is None
    assert ml_model_id == str(own.id)
    update = ml_service.update.await_args.args[1]
    assert update.model_type.value == "ridge_regression"
    assert "description" not in update.model_fields_set


# -- process(): fail before training ------------------------------------------


@pytest.mark.asyncio
async def test_target_type_check_without_pipeline_target_is_skipped():
    assert await _make_node()._target_model_type_mismatch(None, "xgboost") is None


@pytest.mark.asyncio
async def test_target_type_check_ignores_lookup_failures(monkeypatch):
    ml_service = MagicMock()
    ml_service.get_by_id = AsyncMock(side_effect=AppException(error_key=ErrorKey.NOT_FOUND))
    _patch_dependencies(monkeypatch, ml_service)
    assert await _make_node()._target_model_type_mismatch(str(uuid.uuid4()), "xgboost") is None

    ml_service.get_by_id = AsyncMock(return_value=None)
    assert await _make_node()._target_model_type_mismatch(str(uuid.uuid4()), "xgboost") is None


@pytest.mark.asyncio
async def test_pipeline_run_fails_before_training_on_type_mismatch(monkeypatch, tmp_path):
    existing = _existing_model(DbModelType.RANDOM_FOREST)
    ml_service = _ml_service(existing=existing)
    _patch_dependencies(monkeypatch, ml_service)
    node = _make_node(initial_values={"model_id": str(existing.id)})
    node._register_trained_model = AsyncMock()

    with pytest.raises(AppException) as excinfo:
        await node.process(
            {
                "name": "Train Model",
                "modelType": "xgboost",
                # Never read: the run stops before loading data.
                "fileUrl": str(tmp_path / "missing.csv"),
                "targetColumn": "y",
                "featureColumns": ["x"],
            }
        )

    assert "registered as Random Forest" in excinfo.value.error_detail
    assert "set to XGBoost" in excinfo.value.error_detail
    node._register_trained_model.assert_not_awaited()


# -- promote_run --------------------------------------------------------------


def _promote_service(model_type, run_model_type):
    model_id = uuid.uuid4()
    run = MagicMock()
    run.model_id = model_id
    run.status = PipelineRunStatusEnum.COMPLETED
    run.execution_output = {
        "output": {
            "model_type": run_model_type,
            "model_file_path": "/data/model.pkl",
            "pkl_file_id": str(uuid.uuid4()),
            "feature_columns": ["x"],
            "target_column": "y",
        }
    }
    run_repository = MagicMock()
    run_repository.get_by_id = AsyncMock(return_value=run)

    config = MagicMock()
    config_repository = MagicMock()
    config_repository.get_by_id = AsyncMock(return_value=config)
    config_repository.unset_default_for_model = AsyncMock()
    config_repository.update = AsyncMock(return_value=config)

    model = MagicMock()
    model.name = "Churn"
    model.model_type = model_type
    model.inference_params = None
    model_repository = MagicMock()
    model_repository.get_by_id = AsyncMock(return_value=model)

    model_service = MagicMock()
    model_service.update = AsyncMock(return_value=model)

    service = MLModelPipelineRunService(
        run_repository=run_repository,
        config_repository=config_repository,
        model_repository=model_repository,
        model_service=model_service,
        model_manager=MagicMock(),
        workflow_repository=MagicMock(),
    )
    return service, model_service, config_repository, model_id


@pytest.mark.asyncio
async def test_promote_refuses_a_file_of_another_type():
    service, model_service, config_repository, model_id = _promote_service(
        DbModelType.RANDOM_FOREST, "xgboost"
    )

    with pytest.raises(AppException) as excinfo:
        await service.promote_run(
            model_id, uuid.uuid4(), MLModelPipelineRunPromote(update_model_file=True)
        )

    assert excinfo.value.error_key == ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE
    assert "registered as Random Forest" in excinfo.value.error_detail
    model_service.update.assert_not_awaited()
    config_repository.unset_default_for_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_accepts_a_file_of_the_same_type():
    service, model_service, _, model_id = _promote_service(
        DbModelType.RANDOM_FOREST, "random_forest"
    )

    await service.promote_run(
        model_id, uuid.uuid4(), MLModelPipelineRunPromote(update_model_file=True)
    )

    update = model_service.update.await_args.args[1]
    assert "model_type" not in update.model_fields_set
    assert "description" not in update.model_fields_set
