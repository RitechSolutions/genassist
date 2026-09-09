"""
End-to-end test of the Train Model -> ML Model Inference flow for feature
scaling: trains a model with `scalingMethod="auto"`, confirms Auto resolves
sensibly for the model type, and confirms the fitted scaler persisted in the
.pkl metadata is correctly reapplied at inference time.
"""

import pickle
import uuid
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from sklearn.preprocessing import RobustScaler

from app.modules.workflow.engine.nodes.ml import ml_model_inference_node as inference_module
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import MLModelInferenceNode
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState


def _make_outlier_heavy_csv(tmp_path) -> str:
    """28 clean rows (x=0..27) + 2 outlier rows (x=1000), y = 3x + 5 exactly."""
    xs = list(range(28)) + [1000, 1000]
    df = pd.DataFrame({"x": [float(v) for v in xs], "y": [3.0 * v + 5.0 for v in xs]})
    file_path = tmp_path / "train_data.csv"
    df.to_csv(file_path, index=False)
    return str(file_path)


def _make_node(node_cls, **kwargs):
    return node_cls(node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={}), **kwargs)


class _StubMLModelsService:
    """Stands in for the DB-backed MLModelsService for a single known model."""

    def __init__(self, ml_model):
        self._ml_model = ml_model

    async def get_by_id(self, model_id):
        return self._ml_model

    async def update(self, model_id, update):  # pragma: no cover - not expected to run
        raise AssertionError("update() should not be called when pkl_file already exists locally")


@pytest.fixture
def patch_ml_models_service(monkeypatch):
    """Patch the injector lookup used by MLModelInferenceNode to return a stub service."""

    def _apply(ml_model):
        monkeypatch.setattr(
            inference_module.injector, "get", lambda cls: _StubMLModelsService(ml_model)
        )

    return _apply


@pytest.mark.asyncio
async def test_train_then_infer_reapplies_persisted_scaler(tmp_path, patch_ml_models_service):
    csv_path = _make_outlier_heavy_csv(tmp_path)

    train_node = _make_node(TrainModelNode)
    train_result = await train_node.process(
        {
            "name": f"e2e-linreg-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": csv_path,
            "targetColumn": "y",
            "featureColumns": ["x"],
            "validationSplit": 0.0,
            "scalingMethod": "auto",
        }
    )

    assert train_result["success"] is True
    # Outlier-heavy data + a scale-sensitive model type => Auto picks Robust.
    assert train_result["scaling_method"] == "robust"

    model_file_path = train_result["model_file_path"]
    with open(model_file_path, "rb") as f:
        payload = pickle.load(f)

    scaler = payload["metadata"]["scaler"]
    assert isinstance(scaler, RobustScaler)
    assert payload["metadata"]["scaled_columns"] == ["x"]

    # Counterfactual: predicting on a RAW (unscaled) input with the model
    # trained on scaled input gives a wildly wrong answer - this is exactly
    # the bug the inference-side reapplication fixes.
    raw_prediction = payload["model"].predict([[15.0]])[0]
    assert abs(raw_prediction - 50.0) > 1.0, (
        "expected the raw (unscaled) prediction to diverge from the true "
        "y=3x+5 relationship, proving scaling reapplication is necessary"
    )

    # Run inference through the real node (only the DB lookup is stubbed).
    ml_model = SimpleNamespace(
        id=uuid.uuid4(),
        name="e2e-linreg",
        pkl_file=model_file_path,
        pkl_file_id=None,
        updated_at=datetime.now(),
        model_type="linear_regression",
        target_variable="y",
        features=["x"],
    )
    patch_ml_models_service(ml_model)

    inference_node = _make_node(MLModelInferenceNode)
    inference_result = await inference_node.process(
        {"modelId": str(ml_model.id), "inferenceInputs": {"x": 15}}
    )

    assert inference_result["status"] == "success"
    # y = 3*15 + 5 = 50, exactly recovered once the persisted scaler is
    # correctly reapplied to the raw input before calling model.predict().
    assert inference_result["prediction"] == [50]


@pytest.mark.asyncio
async def test_auto_scaling_skips_tree_based_models(tmp_path, patch_ml_models_service):
    csv_path = _make_outlier_heavy_csv(tmp_path)

    train_node = _make_node(TrainModelNode)
    train_result = await train_node.process(
        {
            "name": f"e2e-rf-{uuid.uuid4().hex[:8]}",
            "modelType": "random_forest",
            "fileUrl": csv_path,
            "targetColumn": "y",
            "featureColumns": ["x"],
            "validationSplit": 0.0,
            "scalingMethod": "auto",
        }
    )

    assert train_result["success"] is True
    assert train_result["scaling_method"] == "none"

    with open(train_result["model_file_path"], "rb") as f:
        payload = pickle.load(f)
    assert "scaler" not in payload["metadata"]

    # Inference on a "none"-scaling model should be an unaffected no-op path.
    ml_model = SimpleNamespace(
        id=uuid.uuid4(),
        name="e2e-rf",
        pkl_file=train_result["model_file_path"],
        pkl_file_id=None,
        updated_at=datetime.now(),
        model_type="random_forest",
        target_variable="y",
        features=["x"],
    )
    patch_ml_models_service(ml_model)

    inference_node = _make_node(MLModelInferenceNode)
    inference_result = await inference_node.process(
        {"modelId": str(ml_model.id), "inferenceInputs": {"x": 15}}
    )
    assert inference_result["status"] == "success"
