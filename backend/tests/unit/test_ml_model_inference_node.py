import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_model_inference_node as inference_module
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import (
    MLModelInferenceNode,
    _build_input_array,
    _build_prediction_outputs,
    _normalize_inference_inputs,
    _validate_inference_values,
)


class TestNormalizeInferenceInputs:
    def test_skips_empty_strings(self):
        assert _normalize_inference_inputs({"a": "", "b": 1}) == {"b": [1]}

    def test_wraps_scalar(self):
        assert _normalize_inference_inputs({"hour": 10}) == {"hour": [10]}

    def test_preserves_batch(self):
        assert _normalize_inference_inputs({"hour": [10, 11]}) == {"hour": [10, 11]}


class TestBuildInputArray:
    FEATURES = ["day_of_week", "hour_of_day", "is_weekend"]

    def test_single_feature_batch_broadcasts_missing_to_zero(self):
        result = _build_input_array({"hour_of_day": [10, 10, 10, 10]}, self.FEATURES)
        assert result.shape == (4, 3)
        np.testing.assert_array_equal(result[:, 0], [0, 0, 0, 0])
        np.testing.assert_array_equal(result[:, 1], [10, 10, 10, 10])
        np.testing.assert_array_equal(result[:, 2], [0, 0, 0, 0])

    def test_scalar_feature_broadcasts_within_batch(self):
        result = _build_input_array(
            {"hour_of_day": [10, 11], "day_of_week": [3]},
            self.FEATURES,
        )
        assert result.shape == (2, 3)
        np.testing.assert_array_equal(result[:, 0], [3, 3])
        np.testing.assert_array_equal(result[:, 1], [10, 11])

    def test_rejects_incompatible_batch_lengths(self):
        with pytest.raises(ValueError, match="day_of_week.*batch size is 4"):
            _build_input_array(
                {"hour_of_day": [10, 10, 10, 10], "day_of_week": [1, 2]},
                self.FEATURES,
            )

    def test_single_row_inference(self):
        result = _build_input_array({"hour_of_day": [10]}, self.FEATURES)
        assert result.shape == (1, 3)
        np.testing.assert_array_equal(result[0], [0, 10, 0])


class TestBuildPredictionOutputs:
    def test_numpy_scalars_become_json_safe_python_scalars(self):
        predictions, labels, details = _build_prediction_outputs(
            [np.int64(2), np.float32(1.5), np.bool_(True), np.str_("ready")],
            class_labels=[2, 1.5, True, "ready"],
        )

        assert predictions == [2, 1.5, True, "ready"]
        assert [type(value) for value in predictions] == [int, float, bool, str]
        assert labels == predictions
        assert [detail["label"] for detail in details] == labels
        json.dumps({"prediction": predictions, "prediction_label": labels, "prediction_details": details})

    def test_regression_prediction_has_no_invented_label(self):
        predictions, labels, details = _build_prediction_outputs([np.float64(12.75)], class_labels=None)

        assert predictions == [12.75]
        assert labels == [None]
        assert details == [{"result": 12.75, "label": None}]


async def _run_inference(monkeypatch, model, model_type):
    model_record = SimpleNamespace(
        name="test-model",
        model_type=model_type,
        target_variable="target",
        features=["feature"],
        pkl_file=__file__,
        pkl_file_id=None,
        updated_at=None,
    )
    ml_service = SimpleNamespace(get_by_id=AsyncMock(return_value=model_record))
    model_manager = SimpleNamespace(
        get_model=AsyncMock(
            return_value={
                "version": "v2.0",
                "model": model,
                "metadata": {"feature_columns": ["feature"]},
            }
        )
    )
    monkeypatch.setattr(inference_module, "injector", SimpleNamespace(get=Mock(return_value=ml_service)))
    monkeypatch.setattr(inference_module, "get_ml_model_manager", Mock(return_value=model_manager))

    node = MLModelInferenceNode("node-id", {"data": {}}, Mock())
    return await node.process(
        {
            "modelId": "12345678-1234-5678-1234-567812345678",
            "inferenceInputs": {"feature": 1},
        }
    )


class TestInferenceOutput:
    @pytest.mark.asyncio
    async def test_preserves_float_regression_output_without_labels(self, monkeypatch):
        class RegressionModel:
            def predict(self, _input_data):
                return np.array([np.float32(12.75)])

        result = await _run_inference(monkeypatch, RegressionModel(), "linear_regression")

        assert result["prediction"] == [12.75]
        assert isinstance(result["prediction"][0], float)
        assert result["prediction_label"] == [None]
        assert result["prediction_details"] == [{"result": 12.75, "label": None}]
        assert result["batch_size"] == 1
        json.dumps(result)

    @pytest.mark.asyncio
    async def test_preserves_string_classes_and_uses_them_consistently(self, monkeypatch):
        class StringClassifier:
            classes_ = np.array(["denied", "approved"])

            def predict(self, _input_data):
                return np.array(["approved"])

            def predict_proba(self, _input_data):
                return np.array([[0.25, 0.75]], dtype=np.float32)

        result = await _run_inference(monkeypatch, StringClassifier(), "logistic_regression")

        assert result["prediction"] == ["approved"]
        assert result["prediction_label"] == ["approved"]
        assert result["prediction_details"] == [{"result": "approved", "label": "approved"}]
        assert [detail["label"] for detail in result["prediction_details"]] == result["prediction_label"]
        assert result["probabilities"] == [{"Class_denied": 0.25, "Class_approved": 0.75}]
        assert result["confidences"] == [0.75]
        assert result["batch_size"] == 1
        json.dumps(result)


class _StubModel:
    def __init__(self, error=None):
        self.error = error

    def predict(self, X):
        if self.error:
            raise self.error
        return np.zeros(len(X), dtype=int)


async def _predict(monkeypatch, model, inputs, **metadata):
    ml_model = SimpleNamespace(
        name="forecast",
        model_type="xgboost",
        target_variable="y",
        features=list(inputs),
        pkl_file="forecast.pkl",
        pkl_file_id=None,
        updated_at=None,
    )
    service = MagicMock(get_by_id=AsyncMock(return_value=ml_model))
    manager = MagicMock(
        get_model=AsyncMock(
            return_value={
                "version": "v2.0",
                "model": model,
                "metadata": {"feature_columns": list(inputs), **metadata},
            }
        )
    )
    monkeypatch.setattr(inference_module, "injector", MagicMock(get=MagicMock(return_value=service)))
    monkeypatch.setattr(inference_module, "get_ml_model_manager", lambda: manager)
    monkeypatch.setattr(MLModelInferenceNode, "_ensure_pkl_file", AsyncMock())
    node = MLModelInferenceNode("ml1", {"id": "ml1", "type": "mlModelInferenceNode", "data": {}}, MagicMock())
    return await node.process({"modelId": str(uuid4()), "inferenceInputs": inputs})


class TestValidateInferenceValues:
    def test_does_not_blame_values_some_models_accept(self):
        inputs = {
            "a": [1, 2.5, True, np.int64(3), float("nan"), None],
            "b": ["1e5", "hourly"],
            "rows": [[1, 2], [3, 4]],
        }
        _validate_inference_values(inputs, ["a", "b", "rows"], ValueError("boom"))

    def test_ignores_columns_that_are_not_model_features(self):
        _validate_inference_values({"lag_24": [1.0], "timestamp": ["null"]}, ["lag_24"], ValueError("boom"))

    def test_rejects_empty_inputs(self):
        with pytest.raises(AppException) as exc:
            _validate_inference_values({}, [], ValueError("Found array with 0 sample(s)"))
        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID

    @pytest.mark.asyncio
    async def test_values_a_model_accepts_still_predict(self, monkeypatch):
        result = await _predict(monkeypatch, _StubModel(), {"hour": [1, None], "kind": "null"})
        assert result["status"] == "success"
        assert result["prediction"] == [0, 0]

    @pytest.mark.asyncio
    async def test_failed_prediction_names_the_unusable_feature(self, monkeypatch):
        model = _StubModel(ValueError("could not convert string to float: 'null'"))
        with pytest.raises(AppException) as exc:
            await _predict(monkeypatch, model, {"lag_24": "null", "hour": 3})
        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        detail = exc.value.error_detail
        assert detail.startswith("Unusable inference input for 1 feature(s): lag_24='null'")
        assert "upstream" in detail
        assert "could not convert string to float" in detail

    @pytest.mark.asyncio
    async def test_failed_preparation_names_the_unusable_feature(self, monkeypatch):
        scaler = StandardScaler().fit([[0.0], [1.0]])
        inputs = {"lag_24": "null", "hour": 3}
        with pytest.raises(AppException) as exc:
            await _predict(monkeypatch, _StubModel(), inputs, scaler=scaler, scaled_columns=["lag_24"])
        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert exc.value.error_detail.startswith("Unusable inference input for 1 feature(s): lag_24='null'")
        assert "Data preparation failed: could not convert string to float" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_failed_feature_replay_names_the_unusable_feature(self, monkeypatch):
        inputs = {"lag_24": "null", "hour": 3}
        steps = [{"strategy": "normalize", "column_stats": {"lag_24": {"out_col": "lag_24_norm", "min": 0, "max": 1}}}]
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                inputs,
                feature_engineering_steps=steps,
                model_input_columns=["lag_24_norm", "hour"],
            )
        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert exc.value.error_detail.startswith("Unusable inference input for 1 feature(s): lag_24='null'")
        assert "Could not reconstruct column(s) ['lag_24_norm']" in exc.value.error_detail
