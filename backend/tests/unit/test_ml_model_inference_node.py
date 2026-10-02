import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from app.modules.workflow.engine.nodes.ml import ml_model_inference_node as inference_module
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import (
    MLModelInferenceNode,
    _build_input_array,
    _build_prediction_outputs,
    _normalize_inference_inputs,
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
