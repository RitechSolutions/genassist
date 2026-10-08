"""
End-to-end tests for four train -> save -> load -> predict metadata bugs:

1. Label/ordinal-encoded columns interleaved with numeric ones were silently
   reordered at inference (grouped to the end instead of staying where they
   actually sat in the training column order).
2. A model trained on a ratio target (target / baselineColumn) returned the
   raw ratio at inference instead of the real-unit value.
3. Engineered features (bin_numeric/normalize/standardize/polynomial/
   custom_expression) were never rebuilt at inference, so the model got
   fewer columns than it was trained on.
4. A column removed via missingValueHandling's "drop_column" stayed in the
   saved feature_columns metadata, so inference built one extra column the
   model was never trained on.
"""

import pickle
import uuid
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from app.modules.workflow.engine.nodes.ml import ml_model_inference_node as inference_module
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import MLModelInferenceNode
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState


def _make_node(node_cls, **kwargs):
    return node_cls(node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={}), **kwargs)


class _StubMLModelsService:
    def __init__(self, ml_model):
        self._ml_model = ml_model

    async def get_by_id(self, model_id):
        return self._ml_model

    async def update(self, model_id, update):  # pragma: no cover
        raise AssertionError("update() should not be called when pkl_file already exists locally")


@pytest.fixture
def patch_ml_models_service(monkeypatch):
    def _apply(ml_model):
        monkeypatch.setattr(
            inference_module.injector, "get", lambda cls: _StubMLModelsService(ml_model)
        )

    return _apply


def _make_ml_model(model_file_path, features, target_variable="y", model_type="linear_regression"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="e2e-model",
        pkl_file=model_file_path,
        pkl_file_id=None,
        updated_at=datetime.now(),
        model_type=model_type,
        target_variable=target_variable,
        features=features,
    )


@pytest.mark.asyncio
async def test_label_encoded_column_interleaved_with_numeric_keeps_correct_order(
    tmp_path, patch_ml_models_service
):
    # "cat" sits BETWEEN two numeric columns in the configured feature order -
    # exactly the layout that silently swapped columns before the fix.
    rows = [
        {"a": 1.0, "cat": "lo", "b": 10.0},
        {"a": 2.0, "cat": "lo", "b": 20.0},
        {"a": 3.0, "cat": "hi", "b": 5.0},
        {"a": 4.0, "cat": "hi", "b": 15.0},
        {"a": 5.0, "cat": "lo", "b": 8.0},
        {"a": 6.0, "cat": "hi", "b": 25.0},
    ]
    # label encoding is fit on sorted categories, so "hi" -> 0, "lo" -> 1.
    code = {"hi": 0, "lo": 1}
    for r in rows:
        r["y"] = r["a"] * 1.0 + code[r["cat"]] * 10.0 + r["b"] * 100.0

    csv_path = tmp_path / "train_data.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    train_node = _make_node(TrainModelNode)
    train_result = await train_node.process(
        {
            "name": f"e2e-order-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": str(csv_path),
            "targetColumn": "y",
            "featureColumns": ["a", "cat", "b"],
            "categoricalEncoding": [{"columnName": "cat", "strategy": "label"}],
            "validationSplit": 0.0,
            "scalingMethod": "none",
        }
    )
    assert train_result["success"] is True

    with open(train_result["model_file_path"], "rb") as f:
        payload = pickle.load(f)
    assert payload["metadata"]["model_input_columns"] == ["a", "cat", "b"]

    ml_model = _make_ml_model(train_result["model_file_path"], ["a", "cat", "b"])
    patch_ml_models_service(ml_model)

    inference_node = _make_node(MLModelInferenceNode)
    inference_result = await inference_node.process(
        {"modelId": str(ml_model.id), "inferenceInputs": {"a": 10, "cat": "hi", "b": 1}}
    )

    assert inference_result["status"] == "success"
    expected = 10.0 * 1.0 + code["hi"] * 10.0 + 1.0 * 100.0  # = 110
    # a=10 and b=1 are deliberately very different values - a column swap
    # between them would produce a wildly different (and wrong) number.
    assert inference_result["prediction"][0] == pytest.approx(expected, abs=0.5)


@pytest.mark.asyncio
async def test_ratio_target_reconstructs_real_value_at_inference(tmp_path, patch_ml_models_service):
    rows = [{"x": x, "base": base} for x, base in [(1, 100), (2, 50), (3, 200), (4, 80), (5, 150), (6, 60)]]
    for r in rows:
        r["y"] = r["base"] * (2.0 * r["x"])  # y = base * ratio, ratio = 2x

    csv_path = tmp_path / "train_data.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    train_node = _make_node(TrainModelNode)
    train_result = await train_node.process(
        {
            "name": f"e2e-ratio-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": str(csv_path),
            "targetColumn": "y",
            "featureColumns": ["x"],
            "targetTransform": {"type": "ratio", "baselineColumn": "base"},
            "validationSplit": 0.0,
            "scalingMethod": "none",
        }
    )
    assert train_result["success"] is True

    with open(train_result["model_file_path"], "rb") as f:
        payload = pickle.load(f)
    assert payload["metadata"]["target_transform"] == {"type": "ratio", "baselineColumn": "base"}

    ml_model = _make_ml_model(train_result["model_file_path"], ["x"])
    patch_ml_models_service(ml_model)

    inference_node = _make_node(MLModelInferenceNode)

    # Supplying the baseline reconstructs the real-unit prediction.
    result = await inference_node.process(
        {"modelId": str(ml_model.id), "inferenceInputs": {"x": 7, "base": 40}}
    )
    assert result["status"] == "success"
    expected = 40 * (2.0 * 7)  # = 560
    assert result["prediction"][0] == pytest.approx(expected, abs=1.0)

    # Omitting it is a clear, actionable error - not a silently-wrong ratio.
    from app.core.exceptions.exception_classes import AppException

    with pytest.raises(AppException) as exc_info:
        await inference_node.process({"modelId": str(ml_model.id), "inferenceInputs": {"x": 7}})
    assert "base" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_engineered_polynomial_feature_rebuilt_at_inference(tmp_path, patch_ml_models_service):
    xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    rows = [{"x": x, "y": x * x} for x in xs]  # noiseless y = x^2

    csv_path = tmp_path / "train_data.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    train_node = _make_node(TrainModelNode)
    train_result = await train_node.process(
        {
            "name": f"e2e-poly-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": str(csv_path),
            "targetColumn": "y",
            "featureColumns": ["x"],
            "featureEngineering": [{
                "newColumnName": "x_poly",
                "strategy": "polynomial",
                "polynomialColumns": ["x"],
                "polynomialDegree": 2,
            }],
            "validationSplit": 0.0,
            "scalingMethod": "none",
        }
    )
    assert train_result["success"] is True

    with open(train_result["model_file_path"], "rb") as f:
        payload = pickle.load(f)
    assert payload["metadata"]["model_input_columns"] == ["x", "x_poly_x^2"]
    assert len(payload["metadata"]["feature_engineering_steps"]) == 1

    ml_model = _make_ml_model(train_result["model_file_path"], ["x"])
    patch_ml_models_service(ml_model)

    inference_node = _make_node(MLModelInferenceNode)
    # x=7 is unseen; without replaying the polynomial step this previously
    # raised a shape-mismatch (model fit on 2 columns, given only 1).
    result = await inference_node.process(
        {"modelId": str(ml_model.id), "inferenceInputs": {"x": 7}}
    )
    assert result["status"] == "success"
    assert result["prediction"][0] == pytest.approx(49.0, abs=0.5)


@pytest.mark.asyncio
async def test_drop_column_is_removed_from_saved_feature_columns(tmp_path, patch_ml_models_service):
    # b is deliberately NOT a linear function of a (e.g. not simply 10*a) -
    # otherwise a/b would be perfectly collinear and linear regression could
    # fit y=a+b via infinitely many different (a, b) coefficient splits,
    # making an out-of-sample prediction meaningless to assert on.
    rows = [
        {"a": 1.0, "junk": "x", "b": 10.0},
        {"a": 2.0, "junk": "y", "b": 5.0},
        {"a": 3.0, "junk": "x", "b": 30.0},
        {"a": 4.0, "junk": "y", "b": 8.0},
        {"a": 5.0, "junk": "x", "b": 25.0},
        {"a": 6.0, "junk": "y", "b": 15.0},
    ]
    for r in rows:
        r["y"] = r["a"] + r["b"]

    csv_path = tmp_path / "train_data.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    train_node = _make_node(TrainModelNode)
    train_result = await train_node.process(
        {
            "name": f"e2e-dropcol-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": str(csv_path),
            "targetColumn": "y",
            "featureColumns": ["a", "junk", "b"],
            "missingValueHandling": [{"columnName": "junk", "strategy": "drop_column"}],
            "validationSplit": 0.0,
            "scalingMethod": "none",
        }
    )
    assert train_result["success"] is True
    assert train_result["feature_columns"] == ["a", "b"]

    with open(train_result["model_file_path"], "rb") as f:
        payload = pickle.load(f)
    assert payload["metadata"]["feature_columns"] == ["a", "b"]
    assert payload["metadata"]["model_input_columns"] == ["a", "b"]

    ml_model = _make_ml_model(train_result["model_file_path"], ["a", "b"])
    patch_ml_models_service(ml_model)

    inference_node = _make_node(MLModelInferenceNode)
    # Previously raised a shape mismatch: model fit on 2 columns, metadata
    # claimed 3, so inference built an array one column too wide.
    result = await inference_node.process(
        {"modelId": str(ml_model.id), "inferenceInputs": {"a": 10, "b": 20}}
    )
    assert result["status"] == "success"
    assert result["prediction"][0] == pytest.approx(30.0, abs=0.5)


@pytest.mark.asyncio
async def test_feature_engineering_uses_ordinal_codes_at_train_and_inference(
    tmp_path, patch_ml_models_service
):
    # Categorical encoding now runs before feature engineering, so a derived
    # feature can be built from the encoded numbers. Before, size was still
    # "Low"/"High" text when size * price ran, and the step was skipped.
    order = {"Low": 0, "Medium": 1, "High": 2}
    rows = []
    for size, price in [("Low", 5.0), ("Medium", 7.0), ("High", 3.0), ("Low", 9.0),
                        ("High", 8.0), ("Medium", 2.0), ("High", 6.0), ("Low", 4.0),
                        ("Low", 3.0)]:
        rows.append({"size": size, "price": price, "y": 3.0 * order[size] * price})
    # A missing size is filled with the mode ("Low" -> 0) before it is
    # encoded, at training and again at inference.
    rows.append({"size": None, "price": 6.0, "y": 0.0})

    csv_path = tmp_path / "train_data.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    train_result = await _make_node(TrainModelNode).process(
        {
            "name": f"e2e-ordinal-fe-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": str(csv_path),
            "targetColumn": "y",
            "featureColumns": ["size", "price"],
            "missingValueHandling": [{"columnName": "size", "strategy": "impute_mode"}],
            "categoricalEncoding": [
                {"columnName": "size", "strategy": "ordinal", "ordinalMapping": order}
            ],
            "featureEngineering": [
                {"newColumnName": "size_x_price", "strategy": "custom_expression",
                 "expression": "size * price"}
            ],
            "validationSplit": 0.0,
            "scalingMethod": "none",
        }
    )
    assert train_result["success"] is True

    with open(train_result["model_file_path"], "rb") as f:
        metadata = pickle.load(f)["metadata"]
    assert "size_x_price" in metadata["model_input_columns"]
    assert metadata["encoding_before_feature_engineering"] is True

    ml_model = _make_ml_model(train_result["model_file_path"], ["size", "price"])
    patch_ml_models_service(ml_model)
    result = await _make_node(MLModelInferenceNode).process(
        {"modelId": str(ml_model.id),
         "inferenceInputs": {"size": ["High", "Medium"], "price": [10, 4]}}
    )
    assert result["status"] == "success"
    assert result["prediction"][0] == pytest.approx(3.0 * 2 * 10, abs=0.5)
    assert result["prediction"][1] == pytest.approx(3.0 * 1 * 4, abs=0.5)
