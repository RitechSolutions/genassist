import numpy as np
import pytest

from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import (
    _build_input_array,
    _build_prediction_entries,
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


class TestBuildPredictionEntries:
    def test_single_prediction_object(self):
        entries = _build_prediction_entries([3891])
        assert entries == [{"result": 3891, "label": "Not Available"}]

    def test_batch_prediction_objects(self):
        entries = _build_prediction_entries([1, 0, 3891])
        assert entries == [
            {"result": 1, "label": "Available"},
            {"result": 0, "label": "Not Available"},
            {"result": 3891, "label": "Not Available"},
        ]
