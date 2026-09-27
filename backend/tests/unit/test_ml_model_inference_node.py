from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_model_inference_node as inference_module
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import (
    MLModelInferenceNode,
    _build_input_array,
    _build_prediction_entries,
    _label_for_prediction,
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


class TestLabelForPrediction:
    def test_zero_is_not_available(self):
        assert _label_for_prediction(0) == "Not Available"

    def test_non_zero_number_is_available(self):
        assert _label_for_prediction(3891) == "Available"

    def test_bool_false_is_not_available(self):
        assert _label_for_prediction(False) == "Not Available"


class TestBuildPredictionEntries:
    def test_single_prediction_object(self):
        entries = _build_prediction_entries([3891])
        assert entries == [{"result": 3891, "label": "Available"}]

    def test_batch_prediction_objects(self):
        entries = _build_prediction_entries([1, 0, 3891])
        assert entries == [
            {"result": 1, "label": "Available"},
            {"result": 0, "label": "Not Available"},
            {"result": 3891, "label": "Available"},
        ]


class _StubModel:
    def __init__(self, error=None):
        self.error = error

    def predict(self, X):
        if self.error:
            raise self.error
        return np.zeros(len(X), dtype=int)


async def _predict(monkeypatch, model, inputs):
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
            return_value={"version": "v2.0", "model": model, "metadata": {"feature_columns": list(inputs)}}
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
