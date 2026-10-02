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

    from app.services.file_manager import FileManagerService
    from app.services.app_settings import AppSettingsService
    from app.services.ml_models import MLModelsService

    def _get(cls):
        return {
            FileManagerService: file_manager,
            AppSettingsService: app_settings_service,
            MLModelsService: ml_service,
        }[cls]

    monkeypatch.setattr(injector, "get", _get)


@pytest.mark.asyncio
async def test_ratio_target_surfaces_baseline_column_as_inference_params(monkeypatch):
    ml_service = MagicMock()
    ml_service.get_by_name = AsyncMock(return_value=None)
    created = MagicMock()
    created.id = uuid.uuid4()
    ml_service.create = AsyncMock(return_value=created)
    _patch_dependencies(monkeypatch, ml_service)

    node = _make_node()
    ml_model_id, error = await node._register_trained_model(
        name="my-model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
        target_transform={"type": "ratio", "baselineColumn": "base"},
    )

    assert error is None
    assert ml_model_id == str(created.id)
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
