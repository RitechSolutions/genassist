"""
_register_trained_model is the automatic registration path that runs after
every Train Model node run (ad-hoc or pipeline), independent of the ML Model
Pipeline's separate "promote" flow. It needs the same ratio-target baseline
column surfaced as MLModelUpdate/MLModelCreate's inference_params, since this
is the path that actually sets the ml_models row's fields in the common case.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.dependencies.injector import injector
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState


def _make_node() -> TrainModelNode:
    return TrainModelNode(
        node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
    )


def _patch_dependencies(monkeypatch, ml_service: MagicMock):
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

    def _get(cls):
        return {
            FileManagerService: file_manager,
            AppSettingsService: app_settings_service,
            MLModelsService: ml_service,
        }[cls]

    monkeypatch.setattr(injector, "get", _get)
    return str(uploaded_file.id)


@pytest.mark.asyncio
async def test_ratio_target_surfaces_baseline_column_as_inference_params(monkeypatch):
    ml_service = MagicMock()
    ml_service.get_by_name = AsyncMock(return_value=None)
    created = MagicMock()
    created.id = uuid.uuid4()
    ml_service.create = AsyncMock(return_value=created)
    uploaded_file_id = _patch_dependencies(monkeypatch, ml_service)

    node = _make_node()
    ml_model_id, pkl_file_id, error, warnings = await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
        target_transform={"type": "ratio", "baselineColumn": "base"},
    )

    assert error is None
    assert warnings == []
    assert ml_model_id == str(created.id)
    assert pkl_file_id == uploaded_file_id
    ml_service.create.assert_awaited_once()
    create_arg = ml_service.create.await_args.args[0]
    assert create_arg.inference_params == {"ratioBaselineColumn": "base"}


@pytest.mark.asyncio
async def test_without_ratio_target_inference_params_is_none(monkeypatch):
    ml_service = MagicMock()
    ml_service.get_by_name = AsyncMock(return_value=None)
    created = MagicMock()
    created.id = uuid.uuid4()
    ml_service.create = AsyncMock(return_value=created)
    _patch_dependencies(monkeypatch, ml_service)

    node = _make_node()
    await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
    )

    create_arg = ml_service.create.await_args.args[0]
    assert create_arg.inference_params is None


@pytest.mark.asyncio
async def test_registration_persists_training_metrics(monkeypatch):
    ml_service = MagicMock()
    ml_service.get_by_name = AsyncMock(return_value=None)
    created = MagicMock()
    created.id = uuid.uuid4()
    ml_service.create = AsyncMock(return_value=created)
    _patch_dependencies(monkeypatch, ml_service)

    node = _make_node()
    await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
        training_metrics={"mse": 0.25, "rmse": 0.5, "r2_score": 0.9},
    )

    assert ml_service.create.await_args.kwargs["training_metrics"] == {
        "mse": 0.25,
        "rmse": 0.5,
        "r2_score": 0.9,
    }


@pytest.mark.asyncio
async def test_retrain_preserves_valid_feature_defaults(monkeypatch):
    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing.model_type = "linear_regression"
    existing.inference_params = {
        "featureDefaults": {"x": 1, "removed": 2},
        "ratioBaselineColumn": "old_base",
    }

    ml_service = MagicMock()
    ml_service.get_by_id = AsyncMock(return_value=existing)
    updated = MagicMock()
    updated.id = existing.id
    ml_service.update = AsyncMock(return_value=updated)
    _patch_dependencies(monkeypatch, ml_service)

    node = _make_node()
    ml_model_id, _, error, warnings = await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
        target_model_id=str(existing.id),
        target_transform={"type": "ratio", "baselineColumn": "base"},
        training_metrics={"mse": 0.25, "r2_score": 0.9},
    )

    assert error is None
    assert warnings == []
    assert ml_model_id == str(existing.id)
    update_arg = ml_service.update.await_args.args[1]
    assert update_arg.inference_params == {
        "featureDefaults": {"x": 1},
        "ratioBaselineColumn": "base",
    }
    assert ml_service.update.await_args.kwargs["training_metrics"] == {
        "mse": 0.25,
        "r2_score": 0.9,
    }


@pytest.mark.asyncio
async def test_retrain_removes_obsolete_ratio_baseline(monkeypatch):
    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing.model_type = "linear_regression"
    existing.inference_params = {
        "featureDefaults": {"x": 1},
        "ratioBaselineColumn": "old_base",
    }

    ml_service = MagicMock()
    ml_service.get_by_id = AsyncMock(return_value=existing)
    updated = MagicMock()
    updated.id = existing.id
    ml_service.update = AsyncMock(return_value=updated)
    _patch_dependencies(monkeypatch, ml_service)

    node = _make_node()
    await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
        target_model_id=str(existing.id),
    )

    update_arg = ml_service.update.await_args.args[1]
    assert update_arg.inference_params == {"featureDefaults": {"x": 1}}


@pytest.mark.asyncio
async def test_retrain_warns_when_retained_default_is_not_a_fitted_category(monkeypatch):
    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing.model_type = "linear_regression"
    existing.inference_params = {"featureDefaults": {"kind": "removed"}}

    ml_service = MagicMock()
    ml_service.get_by_id = AsyncMock(return_value=existing)
    updated = MagicMock()
    updated.id = existing.id
    ml_service.update = AsyncMock(return_value=updated)
    _patch_dependencies(monkeypatch, ml_service)

    node = _make_node()
    _, _, error, warnings = await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["kind"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
        target_model_id=str(existing.id),
        categorical_feature_contracts={
            "kind": {"values": ["current"], "normalize_keys": False}
        },
    )

    assert error is None
    assert len(warnings) == 1
    assert "kind" in warnings[0]
    assert "no longer match categories" in warnings[0]


@pytest.mark.asyncio
async def test_uploaded_file_id_is_retained_when_registry_update_fails(monkeypatch):
    ml_service = MagicMock()
    ml_service.get_by_name = AsyncMock(return_value=None)
    ml_service.create = AsyncMock(side_effect=RuntimeError("registry unavailable"))
    uploaded_file_id = _patch_dependencies(monkeypatch, ml_service)

    node = _make_node()
    ml_model_id, pkl_file_id, error, warnings = await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
    )

    assert ml_model_id is None
    assert pkl_file_id == uploaded_file_id
    assert error == "registry unavailable"
    assert warnings == []


@pytest.mark.asyncio
async def test_a_second_run_of_the_same_node_updates_its_model(monkeypatch):
    """A retest under the same node id updates the model the first run made (68072)."""
    ml_service = MagicMock()
    ml_service.get_by_name = AsyncMock(return_value=None)
    created = MagicMock()
    created.id = uuid.uuid4()
    ml_service.create = AsyncMock(return_value=created)
    ml_service.update = AsyncMock(return_value=created)
    _patch_dependencies(monkeypatch, ml_service)

    node_id = str(uuid.uuid4())
    kwargs = dict(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
    )
    first = TrainModelNode(node_id=node_id, node_config={}, state=WorkflowState(workflow={}))
    await first._register_trained_model(**kwargs)
    created.description = ml_service.create.await_args.args[0].description
    created.inference_params = None
    ml_service.get_by_name = AsyncMock(return_value=created)

    second = TrainModelNode(node_id=node_id, node_config={}, state=WorkflowState(workflow={}))
    ml_model_id, _, error, _ = await second._register_trained_model(**kwargs)

    assert error is None
    assert ml_model_id == str(created.id)
    ml_service.create.assert_awaited_once()
    ml_service.update.assert_awaited_once()
    assert ml_service.update.await_args.args[0] == created.id


@pytest.mark.asyncio
async def test_another_node_does_not_take_over_a_model_with_the_same_name(monkeypatch):
    ml_service = MagicMock()
    other = MagicMock()
    other.id = uuid.uuid4()
    other.description = f"Trained by workflow Train Model node [train-model-node:{uuid.uuid4()}]"
    ml_service.get_by_name = AsyncMock(return_value=other)
    ml_service.create = AsyncMock(side_effect=Exception("A model with this name already exists."))
    ml_service.update = AsyncMock()
    _patch_dependencies(monkeypatch, ml_service)

    _, _, error, _ = await _make_node()._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
    )

    assert error == "A model with this name already exists."
    ml_service.update.assert_not_awaited()


def _node_test_node() -> TrainModelNode:
    """A Train Model node run by Test Node (test_individual_node's workflow id)."""
    return TrainModelNode(
        node_id=str(uuid.uuid4()),
        node_config={},
        state=WorkflowState(workflow={"config": {"id": "test-trainModelNode-1731000500"}}),
    )


def _legacy_test_model(target_variable: str = "y") -> MagicMock:
    legacy = MagicMock()
    legacy.id = uuid.uuid4()
    legacy.inference_params = None
    legacy.target_variable = target_variable
    legacy.description = (
        "Trained by workflow Train Model node (thread t) "
        "[train-model-node:test-trainModelNode-1731000000]"
    )
    return legacy


async def _register_over(monkeypatch, legacy: MagicMock, node: TrainModelNode):
    ml_service = MagicMock()
    ml_service.get_by_name = AsyncMock(return_value=legacy)
    ml_service.create = AsyncMock(side_effect=Exception("A model with this name already exists."))
    ml_service.update = AsyncMock(return_value=legacy)
    _patch_dependencies(monkeypatch, ml_service)
    result = await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
    )
    return ml_service, result


@pytest.mark.asyncio
async def test_a_model_left_by_an_old_node_test_is_taken_over(monkeypatch):
    """A retest updates the model an old test registered under a throwaway id (68072)."""
    legacy = _legacy_test_model()
    ml_service, (ml_model_id, _, error, _) = await _register_over(
        monkeypatch, legacy, _node_test_node()
    )

    assert error is None
    assert ml_model_id == str(legacy.id)
    ml_service.create.assert_not_awaited()
    assert ml_service.update.await_args.args[0] == legacy.id


@pytest.mark.asyncio
async def test_a_workflow_run_does_not_take_over_a_model_left_by_an_old_node_test(monkeypatch):
    # Only single-node tests registered such models, so only one may take it over.
    ml_service, (_, _, error, _) = await _register_over(
        monkeypatch, _legacy_test_model(), _make_node()
    )

    assert error == "A model with this name already exists."
    ml_service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_node_training_another_target_does_not_take_over_an_old_test_model(monkeypatch):
    ml_service, (_, _, error, _) = await _register_over(
        monkeypatch, _legacy_test_model(target_variable="churn"), _node_test_node()
    )

    assert error == "A model with this name already exists."
    ml_service.update.assert_not_awaited()
