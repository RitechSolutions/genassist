import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import numpy as np
import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.string_utils import truncate_for_log
from app.modules.workflow.engine.nodes.ml import ml_model_inference_node as inference_module
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import (
    MLModelInferenceNode,
    _build_input_array,
    _build_prediction_outputs,
    _normalize_inference_inputs,
    _prepare_inference_inputs,
    _validate_categorical_inputs,
    convert_input_types,
)
from app.modules.workflow.engine.utils import describe_exception


class TestNormalizeInferenceInputs:
    def test_skips_empty_strings(self):
        assert _normalize_inference_inputs({"a": "", "b": 1}) == {"b": [1]}

    def test_wraps_scalar(self):
        assert _normalize_inference_inputs({"hour": 10}) == {"hour": [10]}

    def test_preserves_batch(self):
        assert _normalize_inference_inputs({"hour": [10, 11]}) == {"hour": [10, 11]}

    def test_preserves_number_like_text_categories(self):
        converted = convert_input_types(
            {"kind": ["100", "A12", "200"]},
            categorical_features=["kind"],
            categorical_values={"kind": {"100", "A12", "200"}},
        )

        assert converted == {"kind": ["100", "A12", "200"]}

    def test_converts_text_when_the_fitted_category_is_numeric(self):
        converted = convert_input_types(
            {"kind": "100"},
            categorical_features=["kind"],
            categorical_values={"kind": {100, 200}},
        )

        assert converted == {"kind": 100}

    def test_boolean_does_not_match_an_integer_category(self):
        with pytest.raises(AppException):
            _validate_categorical_inputs(
                {"kind": [True]},
                ["kind"],
                [np.array([1, 2], dtype=object)],
            )


class TestBuildInputArray:
    FEATURES = ["day_of_week", "hour_of_day", "is_weekend"]

    def test_refuses_to_build_an_unprepared_missing_feature(self):
        with pytest.raises(ValueError, match="day_of_week, is_weekend"):
            _build_input_array({"hour_of_day": [10, 10, 10, 10]}, self.FEATURES)

    def test_scalar_feature_broadcasts_within_batch(self):
        result = _build_input_array(
            {"hour_of_day": [10, 11], "day_of_week": [3], "is_weekend": [0]},
            self.FEATURES,
        )
        assert result.shape == (2, 3)
        np.testing.assert_array_equal(result[:, 0], [3, 3])
        np.testing.assert_array_equal(result[:, 1], [10, 11])

    def test_rejects_incompatible_batch_lengths(self):
        with pytest.raises(AppException) as exc:
            _build_input_array(
                {
                    "hour_of_day": [10, 10, 10, 10],
                    "day_of_week": [1, 2],
                    "is_weekend": [0],
                },
                self.FEATURES,
            )
        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "day_of_week" in exc.value.error_detail
        assert "batch size is 4" in exc.value.error_detail

    def test_single_row_inference(self):
        result = _build_input_array(
            {"day_of_week": [3], "hour_of_day": [10], "is_weekend": [0]},
            self.FEATURES,
        )
        assert result.shape == (1, 3)
        np.testing.assert_array_equal(result[0], [3, 10, 0])


class TestPrepareInferenceInputs:
    FEATURES = ["hour", "is_weekend", "lag_24"]

    def test_missing_feature_error_names_missing_and_complete_contract(self):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs({"hour": [8]}, self.FEATURES)

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "is_weekend, lag_24" in exc.value.error_detail
        assert "hour, is_weekend, lag_24" in exc.value.error_detail

    def test_unexpected_feature_is_ignored_with_a_warning(self, caplog):
        warnings = []

        with caplog.at_level(logging.WARNING):
            prepared, applied = _prepare_inference_inputs(
                {"hour": [8], "is_weekend": [0], "lag_24": [12], "weather": [3]},
                self.FEATURES,
                inference_warnings=warnings,
            )

        assert prepared == {"hour": [8], "is_weekend": [0], "lag_24": [12]}
        assert applied == []
        assert "weather" in warnings[0]
        assert "hour, is_weekend, lag_24" in warnings[0]
        assert any("weather" in record.getMessage() for record in caplog.records)

    def test_configured_defaults_fill_absent_and_null_values(self):
        prepared, applied = _prepare_inference_inputs(
            {"hour": [8, 9], "lag_24": [12, None]},
            self.FEATURES,
            defaults={"is_weekend": 0, "lag_24": 24},
        )

        assert prepared == {
            "hour": [8, 9],
            "lag_24": [12, 24],
            "is_weekend": [0, 0],
        }
        assert applied == ["is_weekend", "lag_24"]

    @pytest.mark.parametrize("missing_value", ["null", " NULL ", "nan", "NaN", "None"])
    def test_unresolved_string_values_use_a_configured_default(self, missing_value):
        prepared, applied = _prepare_inference_inputs(
            {"hour": [8], "is_weekend": [0], "lag_24": [missing_value]},
            self.FEATURES,
            defaults={"lag_24": 24},
        )

        assert prepared["lag_24"] == [24]
        assert applied == ["lag_24"]

    @pytest.mark.parametrize("missing_value", ["null", "nan", "None"])
    def test_unresolved_string_values_are_rejected_without_a_default(self, missing_value):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs(
                {"hour": [8], "is_weekend": [0], "lag_24": [missing_value]},
                self.FEATURES,
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "lag_24" in exc.value.error_detail

    def test_unresolved_null_points_to_the_upstream_node(self):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs(
                {"hour": [" null "], "is_weekend": ["NULL"], "lag_24": [12]},
                self.FEATURES,
            )

        assert "upstream node did not produce that field" in exc.value.error_detail
        assert "hour, is_weekend" in exc.value.error_detail
        assert "configure 'featureDefaults'" not in exc.value.error_detail

    @pytest.mark.parametrize("missing_value", ["nan", "None", None])
    def test_other_missing_values_keep_the_general_default_advice(self, missing_value):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs(
                {"hour": [8], "is_weekend": [0], "lag_24": [missing_value]},
                self.FEATURES,
            )

        assert "upstream node did not produce" not in exc.value.error_detail
        assert "configure 'featureDefaults'" in exc.value.error_detail

    def test_string_default_is_rejected_for_a_numeric_feature(self):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs(
                {"hour": [8], "is_weekend": [0]},
                self.FEATURES,
                defaults={"lag_24": "abc"},
                categorical_features=[],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "numeric feature" in exc.value.error_detail.lower()
        assert "lag_24" in exc.value.error_detail

    def test_quoted_numeric_default_is_converted_like_caller_input(self):
        prepared, applied = _prepare_inference_inputs(
            {"hour": [8], "is_weekend": [0]},
            self.FEATURES,
            defaults={"lag_24": "5"},
        )

        assert prepared["lag_24"] == [5]
        assert applied == ["lag_24"]

    def test_known_missing_sentinel_category_remains_a_real_value(self):
        prepared, applied = _prepare_inference_inputs(
            {"kind": ["None"]},
            ["kind"],
            categorical_features=["kind"],
            categorical_values={"kind": {"None", "wood"}},
        )

        assert prepared == {"kind": ["None"]}
        assert applied == []

    def test_categorical_default_must_match_a_fitted_category(self):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs(
                {},
                ["kind"],
                defaults={"kind": 0},
                categorical_features=["kind"],
                categorical_values={"kind": {"None", "wood"}},
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "categorical default" in exc.value.error_detail
        assert "kind" in exc.value.error_detail

    def test_categorical_default_preserves_numeric_looking_text(self):
        prepared, applied = _prepare_inference_inputs(
            {},
            ["kind"],
            defaults={"kind": "007"},
            categorical_features=["kind"],
            categorical_values={"kind": {"007", "008"}},
        )

        assert prepared == {"kind": ["007"]}
        assert applied == ["kind"]

    def test_boolean_default_does_not_match_an_integer_category(self):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs(
                {},
                ["kind"],
                defaults={"kind": True},
                categorical_features=["kind"],
                categorical_values={"kind": {1, 2}},
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "categorical default" in exc.value.error_detail

    def test_ordinal_default_uses_the_ordinal_lookup_key(self):
        prepared, applied = _prepare_inference_inputs(
            {},
            ["rank"],
            defaults={"rank": 2.0},
            categorical_features=["rank"],
            categorical_values={"rank": {"1", "2", "3"}},
            normalized_categorical_features=["rank"],
        )

        assert prepared == {"rank": [2.0]}
        assert applied == ["rank"]

    def test_non_finite_converted_default_is_rejected(self):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs(
                {},
                ["amount"],
                defaults={"amount": "1.0e999"},
                categorical_features=[],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "finite" in exc.value.error_detail
        assert "amount" in exc.value.error_detail

    def test_unused_stale_categorical_default_does_not_block_request(self):
        prepared, applied = _prepare_inference_inputs(
            {"kind": ["current"]},
            ["kind"],
            defaults={"kind": "removed"},
            categorical_features=["kind"],
            categorical_values={"kind": {"current"}},
        )

        assert prepared == {"kind": ["current"]}
        assert applied == []

    def test_inference_only_feature_is_allowed_but_not_added_to_model_contract(self):
        prepared, applied = _prepare_inference_inputs(
            {"hour": [8], "is_weekend": [0], "lag_24": [12], "baseline": [100]},
            self.FEATURES,
            allowed_extra_features=["baseline"],
        )

        assert prepared["baseline"] == [100]
        assert applied == []

    def test_model_without_feature_contract_is_refused(self):
        with pytest.raises(AppException) as exc:
            _prepare_inference_inputs({"hour": [8]}, [])
        assert "does not record its required feature set" in exc.value.error_detail


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
                "metadata": {
                    "metadata_schema_version": 2,
                    "feature_columns": ["feature"],
                },
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
        assert "feature_order_source" not in result
        json.dumps(result)

    @pytest.mark.asyncio
    async def test_preserves_column_shaped_regression_output(self, monkeypatch):
        class ColumnRegressionModel:
            def predict(self, _input_data):
                return np.array([[np.float32(12.75)]])

        result = await _run_inference(
            monkeypatch,
            ColumnRegressionModel(),
            "linear_regression",
        )

        assert result["prediction"] == ["[12.75]"]
        assert result["prediction_label"] == [None]
        assert result["prediction_details"] == [{"result": "[12.75]", "label": None}]

    @pytest.mark.asyncio
    async def test_uses_predict_for_class_when_probabilities_disagree(self, monkeypatch):
        class StringClassifier:
            classes_ = np.array(["denied", "approved"])

            def __init__(self):
                self.predict_calls = 0
                self.predict_proba_calls = 0

            def predict(self, _input_data):
                self.predict_calls += 1
                return np.array(["denied"])

            def predict_proba(self, _input_data):
                self.predict_proba_calls += 1
                return np.array([[0.25, 0.75]], dtype=np.float32)

        model = StringClassifier()
        result = await _run_inference(monkeypatch, model, "logistic_regression")

        assert model.predict_calls == 1
        assert model.predict_proba_calls == 1
        assert result["prediction"] == ["denied"]
        assert result["prediction_label"] == ["denied"]
        assert result["prediction_details"] == [{"result": "denied", "label": "denied"}]
        assert [detail["label"] for detail in result["prediction_details"]] == result["prediction_label"]
        assert result["probabilities"] == [{"Class_denied": 0.25, "Class_approved": 0.75}]
        assert result["confidences"] == [0.25]
        assert result["batch_size"] == 1
        json.dumps(result)

    @pytest.mark.asyncio
    async def test_flattens_single_column_classifier_predictions(self, monkeypatch):
        class SingleColumnClassifier:
            classes_ = np.array(["denied", "approved"])

            def predict(self, _input_data):
                return np.array([["approved"]])

            def predict_proba(self, _input_data):
                return np.array([[0.125, 0.875]], dtype=np.float32)

        result = await _run_inference(
            monkeypatch,
            SingleColumnClassifier(),
            "catboost",
        )

        assert result["prediction"] == ["approved"]
        assert result["prediction_label"] == ["approved"]
        assert result["prediction_details"] == [{"result": "approved", "label": "approved"}]
        assert result["probabilities"] == [{"Class_denied": 0.125, "Class_approved": 0.875}]
        assert result["confidences"] == [0.875]

    @pytest.mark.asyncio
    async def test_returns_prediction_when_probability_generation_fails(self, monkeypatch, caplog):
        class ProbabilityFailureClassifier:
            classes_ = np.array(["denied", "approved"])

            def predict(self, _input_data):
                return np.array(["approved"])

            def predict_proba(self, _input_data):
                raise RuntimeError("probabilities unavailable")

        with caplog.at_level(logging.WARNING):
            result = await _run_inference(
                monkeypatch,
                ProbabilityFailureClassifier(),
                "logistic_regression",
            )

        assert result["prediction"] == ["approved"]
        assert result["prediction_label"] == ["approved"]
        assert result["prediction_details"] == [{"result": "approved", "label": "approved"}]
        assert "probabilities" not in result
        assert "confidences" not in result
        assert "Probabilities unavailable" in caplog.text
        assert "RuntimeError: probabilities unavailable" in caplog.text

    @pytest.mark.asyncio
    async def test_classifier_without_probability_support_uses_predict(self, monkeypatch):
        class PredictionOnlyClassifier:
            classes_ = np.array(["denied", "approved"])

            def predict(self, _input_data):
                return np.array(["approved"])

        result = await _run_inference(
            monkeypatch,
            PredictionOnlyClassifier(),
            "logistic_regression",
        )

        assert result["prediction"] == ["approved"]
        assert result["prediction_label"] == ["approved"]
        assert result["prediction_details"] == [{"result": "approved", "label": "approved"}]
        assert "probabilities" not in result
        assert "confidences" not in result

    @pytest.mark.asyncio
    async def test_omits_confidence_when_prediction_is_not_in_class_list(self, monkeypatch, caplog):
        class UnknownClassClassifier:
            classes_ = np.array(["denied", "approved"])

            def predict(self, _input_data):
                return np.array(["review"])

            def predict_proba(self, _input_data):
                return np.array([[0.25, 0.75]], dtype=np.float32)

        with caplog.at_level(logging.WARNING):
            result = await _run_inference(
                monkeypatch,
                UnknownClassClassifier(),
                "logistic_regression",
            )

        assert result["prediction"] == ["review"]
        assert result["probabilities"] == [{"Class_denied": 0.25, "Class_approved": 0.75}]
        assert "confidences" not in result
        assert "predicted class" in caplog.text

    @pytest.mark.asyncio
    async def test_ignores_probability_row_count_mismatch(self, monkeypatch, caplog):
        class MismatchedProbabilityClassifier:
            classes_ = np.array(["denied", "approved"])

            def predict(self, _input_data):
                return np.array(["approved"])

            def predict_proba(self, _input_data):
                return np.array(
                    [[0.25, 0.75], [0.75, 0.25]],
                    dtype=np.float32,
                )

        with caplog.at_level(logging.WARNING):
            result = await _run_inference(
                monkeypatch,
                MismatchedProbabilityClassifier(),
                "logistic_regression",
            )

        assert result["prediction"] == ["approved"]
        assert "probabilities" not in result
        assert "confidences" not in result
        assert "row count" in caplog.text


class _StubModel:
    def __init__(self, error=None):
        self.error = error

    def predict(self, X):
        if self.error:
            raise self.error
        return np.zeros(len(X), dtype=int)


async def _predict(
    monkeypatch,
    model,
    inputs,
    *,
    feature_names=None,
    registered_feature_names=None,
    inference_params=None,
    legacy=False,
    artifact_version="v2.0",
    include_metadata_schema_version=True,
    **metadata,
):
    expected_features = list(inputs) if feature_names is None else list(feature_names)
    ml_model = SimpleNamespace(
        name="forecast",
        model_type="xgboost",
        target_variable="y",
        features=(
            expected_features
            if registered_feature_names is None
            else list(registered_feature_names)
        ),
        inference_params=inference_params,
        pkl_file="forecast.pkl",
        pkl_file_id=None,
        updated_at=None,
    )
    service = MagicMock(get_by_id=AsyncMock(return_value=ml_model))
    model_response = {"model": model}
    if not legacy:
        artifact_metadata = {
            "feature_columns": expected_features,
            **metadata,
        }
        if (
            include_metadata_schema_version
            and "metadata_schema_version" not in artifact_metadata
        ):
            artifact_metadata["metadata_schema_version"] = 2
        model_response = {
            "version": artifact_version,
            "model": model,
            "metadata": artifact_metadata,
        }
    manager = MagicMock(get_model=AsyncMock(return_value=model_response))
    monkeypatch.setattr(inference_module, "injector", MagicMock(get=MagicMock(return_value=service)))
    monkeypatch.setattr(inference_module, "get_ml_model_manager", lambda: manager)
    monkeypatch.setattr(MLModelInferenceNode, "_ensure_pkl_file", AsyncMock())
    node = MLModelInferenceNode("ml1", {"id": "ml1", "type": "mlModelInferenceNode", "data": {}}, MagicMock())
    return await node.process({"modelId": str(uuid4()), "inferenceInputs": inputs})


class TestInferenceFeatureContract:
    @pytest.mark.parametrize(
        "artifact_version",
        ["v2.0", "sha256:4f83c0a", "v2.1", ""],
    )
    @pytest.mark.asyncio
    async def test_artifact_version_does_not_control_metadata_schema(
        self,
        monkeypatch,
        artifact_version,
    ):
        class RecordingModel(_StubModel):
            received = None

            def predict(self, input_data):
                self.received = input_data
                return np.zeros(len(input_data), dtype=int)

        model = RecordingModel()
        await _predict(
            monkeypatch,
            model,
            {"lag_24": 12, "hour": 8},
            feature_names=["hour", "lag_24"],
            artifact_version=artifact_version,
        )

        assert list(model.received.columns) == ["hour", "lag_24"]
        np.testing.assert_array_equal(model.received, [[8, 12]])

    @pytest.mark.asyncio
    async def test_metadata_without_schema_version_is_refused(self, monkeypatch):
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {"hour": 8},
                feature_names=["hour"],
                include_metadata_schema_version=False,
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert (
            "has metadata but does not declare a metadata schema version"
            in exc.value.error_detail
        )
        assert "cannot be read safely" in exc.value.error_detail
        assert "Retrain the model" in exc.value.error_detail

    @pytest.mark.parametrize("schema_version", [True, "2", 0])
    @pytest.mark.asyncio
    async def test_invalid_artifact_schema_is_refused(
        self,
        monkeypatch,
        schema_version,
    ):
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {"hour": 8},
                feature_names=["hour"],
                metadata_schema_version=schema_version,
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "invalid metadata schema version" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_schema_one_artifact_uses_metadata(self, monkeypatch):
        class RecordingModel(_StubModel):
            received = None

            def predict(self, input_data):
                self.received = input_data
                return np.zeros(len(input_data), dtype=int)

        model = RecordingModel()
        await _predict(
            monkeypatch,
            model,
            {"lag_24": 12, "hour": 8},
            feature_names=["hour", "lag_24"],
            metadata_schema_version=1,
        )

        assert list(model.received.columns) == ["hour", "lag_24"]
        np.testing.assert_array_equal(model.received, [[8, 12]])

    @pytest.mark.asyncio
    async def test_future_artifact_schema_is_refused(self, monkeypatch):
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {"hour": 8},
                feature_names=["hour"],
                metadata_schema_version=3,
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "artifact schema v3" in exc.value.error_detail
        assert "supports up to v2" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_missing_feature_is_rejected_before_prediction(self, monkeypatch):
        model = _StubModel()

        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                model,
                {"hour": 8},
                feature_names=["hour", "is_weekend"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "is_weekend" in exc.value.error_detail
        assert "hour, is_weekend" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_unexpected_feature_is_ignored_and_reported(self, monkeypatch):
        result = await _predict(
            monkeypatch,
            _StubModel(),
            {"hour": 8, "is_weekend": 0, "weather": 3},
            feature_names=["hour", "is_weekend"],
        )

        assert result["input_data"] == {"hour": [8], "is_weekend": [0]}
        assert "weather" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_unresolved_null_is_rejected_before_label_encoding(self, monkeypatch):
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {"hour": 8, "kind": "null"},
                feature_names=["hour", "kind"],
                label_encodings={"kind": {"a": 0, "b": 1}},
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "kind" in exc.value.error_detail
        assert "upstream node did not produce that field" in exc.value.error_detail
        assert "configure 'featureDefaults'" not in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_batch_length_mismatch_is_an_input_error(self, monkeypatch):
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {"hour": [8, 9, 10], "lag_24": [1, 2]},
                feature_names=["hour", "lag_24"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "lag_24" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_wide_contract_keeps_remediation_visible(self, monkeypatch):
        features = [f"feature_number_{index:02d}" for index in range(60)]
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {
                    **{feature: 1 for feature in features[:-1]},
                    "unexpected_feature": 1,
                },
                feature_names=features,
            )

        visible_detail = truncate_for_log(describe_exception(exc.value), 500)
        assert "featureDefaults" in visible_detail
        assert "feature_number_59" in visible_detail

    @pytest.mark.asyncio
    async def test_raw_estimator_uses_its_recorded_feature_order(self, monkeypatch):
        import pandas as pd
        from sklearn.linear_model import LinearRegression

        training_data = pd.DataFrame(
            {
                "lag_24": [0, 1, 0, 1],
                "hour": [0, 0, 1, 1],
            }
        )
        model = LinearRegression().fit(
            training_data,
            100 * training_data["lag_24"] + training_data["hour"],
        )
        result = await _predict(
            monkeypatch,
            model,
            {"hour": 8, "lag_24": 12},
            feature_names=["hour", "lag_24"],
            legacy=True,
        )

        assert result["prediction"] == pytest.approx([1208])

    @pytest.mark.asyncio
    async def test_v2_artifact_uses_estimator_order_when_metadata_order_differs(
        self, monkeypatch
    ):
        import pandas as pd
        from sklearn.linear_model import LinearRegression

        training_data = pd.DataFrame(
            {
                "lag_24": [0, 1, 0, 1],
                "hour": [0, 0, 1, 1],
            }
        )
        model = LinearRegression().fit(
            training_data,
            100 * training_data["lag_24"] + training_data["hour"],
        )

        result = await _predict(
            monkeypatch,
            model,
            {"hour": 8, "lag_24": 12},
            feature_names=["hour", "lag_24"],
        )

        assert result["prediction"] == pytest.approx([1208])

    @pytest.mark.asyncio
    async def test_v2_artifact_refuses_names_that_disagree_with_estimator(
        self, monkeypatch
    ):
        import pandas as pd
        from sklearn.linear_model import LinearRegression

        training_data = pd.DataFrame(
            {
                "lag_24": [0, 1, 0, 1],
                "hour": [0, 0, 1, 1],
            }
        )
        model = LinearRegression().fit(training_data, [0, 100, 1, 101])

        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                model,
                {"hour": 8, "lag24": 12},
                feature_names=["lag24", "hour"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "artifact feature names disagree" in exc.value.error_detail
        assert "consistent model artifact" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_real_xgboost_wrapper_uses_native_feature_order(
        self, monkeypatch
    ):
        import pandas as pd

        xgboost = pytest.importorskip("xgboost")
        training_data = pd.DataFrame(
            {
                "lag_24": [0, 1, 0, 1],
                "hour": [0, 0, 1, 1],
            }
        )
        model = xgboost.XGBRegressor(
            n_estimators=2,
            max_depth=1,
            learning_rate=1,
            n_jobs=1,
        ).fit(training_data, [0, 100, 1, 101])
        expected = model.predict(
            pd.DataFrame({"lag_24": [12], "hour": [8]})
        ).tolist()

        result = await _predict(
            monkeypatch,
            model,
            {"hour": 8, "lag_24": 12},
            feature_names=["hour", "lag_24"],
            legacy=True,
        )

        assert result["prediction"] == pytest.approx(expected)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("library", ["lightgbm", "catboost"])
    async def test_real_optional_estimators_use_recorded_feature_order(
        self, monkeypatch, library
    ):
        import pandas as pd

        package = pytest.importorskip(library)
        training_data = pd.DataFrame(
            {
                "lag_24": [0, 1, 0, 1],
                "hour": [0, 0, 1, 1],
            }
        )
        if library == "lightgbm":
            model = package.LGBMRegressor(n_estimators=2, verbosity=-1)
        else:
            model = package.CatBoostRegressor(
                iterations=2,
                verbose=False,
                allow_writing_files=False,
            )
        model.fit(training_data, [0, 100, 1, 101])
        expected = model.predict(
            pd.DataFrame({"lag_24": [12], "hour": [8]})
        ).tolist()

        result = await _predict(
            monkeypatch,
            model,
            {"hour": 8, "lag_24": 12},
            feature_names=["hour", "lag_24"],
            legacy=True,
        )

        assert result["prediction"] == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_sklearn_pipeline_receives_named_dataframe(self, monkeypatch):
        import pandas as pd
        from sklearn.compose import ColumnTransformer
        from sklearn.linear_model import LinearRegression
        from sklearn.pipeline import Pipeline

        training_data = pd.DataFrame(
            {
                "lag_24": [0, 1, 0, 1],
                "hour": [0, 0, 1, 1],
            }
        )
        model = Pipeline(
            [
                (
                    "columns",
                    ColumnTransformer(
                        [
                            ("lag", "passthrough", ["lag_24"]),
                            ("hour", "passthrough", ["hour"]),
                        ]
                    ),
                ),
                ("regressor", LinearRegression()),
            ]
        ).fit(
            training_data,
            100 * training_data["lag_24"] + training_data["hour"],
        )

        result = await _predict(
            monkeypatch,
            model,
            {"hour": 8, "lag_24": 12},
            feature_names=["lag_24", "hour"],
            legacy=True,
        )

        assert result["prediction"] == pytest.approx([1208])

    @pytest.mark.parametrize(
        ("feature_names_attribute", "estimator_module"),
        [
            ("feature_names_", "catboost.core"),
            ("feature_name_", "lightgbm.sklearn"),
        ],
    )
    @pytest.mark.asyncio
    async def test_raw_estimator_uses_library_specific_recorded_feature_order(
        self,
        monkeypatch,
        feature_names_attribute,
        estimator_module,
    ):
        class RawModel(_StubModel):
            n_features_in_ = 2
            received = None

            def predict(self, input_data):
                self.received = input_data
                return np.zeros(len(input_data), dtype=int)

        RawModel.__module__ = estimator_module
        model = RawModel()
        setattr(model, feature_names_attribute, ["lag_24", "hour"])
        await _predict(
            monkeypatch,
            model,
            {"hour": 8, "lag_24": 12},
            feature_names=["lag_24", "hour"],
            legacy=True,
        )

        np.testing.assert_array_equal(model.received, [[12, 8]])

    @pytest.mark.asyncio
    async def test_lightgbm_matches_whitespace_normalized_registry_names(
        self, monkeypatch
    ):
        class RawModel(_StubModel):
            n_features_in_ = 2
            feature_name_ = ["lag_24", "hour"]
            received = None

            def predict(self, input_data):
                self.received = input_data
                return np.zeros(len(input_data), dtype=int)

        RawModel.__module__ = "lightgbm.sklearn"
        model = RawModel()
        result = await _predict(
            monkeypatch,
            model,
            {"hour": 8, "lag 24": 12},
            feature_names=["lag 24", "hour"],
            legacy=True,
        )

        assert list(model.received.columns) == ["lag_24", "hour"]
        np.testing.assert_array_equal(model.received, [[12, 8]])
        assert result["input_data"] == {"lag 24": [12], "hour": [8]}

    @pytest.mark.parametrize(
        "estimator_names",
        [
            "lag_24",
            {"lag_24": 1, "hour": 2},
            ["lag_24", 2],
            ["lag_24", "lag_24"],
            ["lag_24"],
        ],
    )
    def test_estimator_feature_names_must_match_fitted_feature_contract(
        self,
        estimator_names,
    ):
        from sklearn.linear_model import LinearRegression

        model = LinearRegression().fit(
            np.array([[0, 0], [1, 0], [0, 1], [1, 1]]),
            np.array([0, 1, 1, 2]),
        )
        model.feature_names_in_ = estimator_names

        with pytest.raises(AppException) as exc:
            inference_module._resolve_feature_order(
                {},
                model,
                "forecast",
                registered_names=["lag_24", "hour"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Feature order source: refused" in exc.value.error_detail

    def test_real_placeholder_like_feature_names_are_preserved(self):
        import pandas as pd
        from sklearn.linear_model import LinearRegression

        training_data = pd.DataFrame(
            {
                "f1": [0, 1, 0, 1],
                "2023": [0, 0, 1, 1],
            }
        )
        model = LinearRegression().fit(training_data, [0, 1, 1, 2])

        caller_names, estimator_names, source = inference_module._resolve_feature_order(
            {},
            model,
            "forecast",
            registered_names=["f1", "2023"],
        )

        assert caller_names == ["f1", "2023"]
        assert estimator_names == ["f1", "2023"]
        assert source == "estimator"

    def test_custom_model_with_valid_feature_names_is_supported(self):
        class RawModel(_StubModel):
            n_features_in_ = 2
            feature_names_in_ = ["lag_24", "hour"]

        caller_names, estimator_names, source = inference_module._resolve_feature_order(
            {},
            RawModel(),
            "forecast",
            registered_names=["hour", "lag_24"],
        )

        assert caller_names == ["lag_24", "hour"]
        assert estimator_names == ["lag_24", "hour"]
        assert source == "estimator"

    @pytest.mark.parametrize(
        "registered_names",
        [None, [], ["lag_24"], ["lag24", "hour"]],
    )
    def test_registry_mismatch_names_both_contracts_and_the_registry_fix(
        self, registered_names
    ):
        class RawModel(_StubModel):
            n_features_in_ = 2
            feature_names_in_ = ["lag_24", "hour"]

        with pytest.raises(AppException) as exc:
            inference_module._resolve_feature_order(
                {},
                RawModel(),
                "forecast",
                registered_names=registered_names,
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "estimator feature names ['lag_24', 'hour']" in exc.value.error_detail
        assert f"registered features are {registered_names!r}" in exc.value.error_detail
        assert "Update the registered feature list" in exc.value.error_detail
        assert "Retrain only if the estimator names are incorrect" in exc.value.error_detail
        assert "does not record a safe" not in exc.value.error_detail

    def test_estimator_feature_name_method_is_not_treated_as_a_name_list(self):
        class RawModel(_StubModel):
            n_features_in_ = 2

            def feature_names_in_(self):
                return ["lag_24", "hour"]

        RawModel.__module__ = "sklearn.fake"
        with pytest.raises(AppException) as exc:
            inference_module._resolve_feature_order(
                {},
                RawModel(),
                "forecast",
                registered_names=["lag_24", "hour"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Feature order source: refused" in exc.value.error_detail

    def test_raising_estimator_feature_name_property_is_refused(self):
        class RawModel(_StubModel):
            n_features_in_ = 2

            @property
            def feature_names_in_(self):
                raise RuntimeError("model is not fitted")

        RawModel.__module__ = "sklearn.fake"
        with pytest.raises(AppException) as exc:
            inference_module._resolve_feature_order(
                {},
                RawModel(),
                "forecast",
                registered_names=["lag_24", "hour"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Feature order source: refused" in exc.value.error_detail

    def test_raising_estimator_feature_count_property_is_refused(self):
        class RawModel(_StubModel):
            feature_names_in_ = ["lag_24", "hour"]

            @property
            def n_features_in_(self):
                raise RuntimeError("model is not fitted")

        assert inference_module._model_feature_count(RawModel()) == -1

    def test_disagreeing_estimator_feature_name_sources_are_refused(self):
        class RawModel(_StubModel):
            n_features_in_ = 2
            feature_names_in_ = ["lag_24", "hour"]
            feature_names_ = ["hour", "lag_24"]

        RawModel.__module__ = "catboost.core"
        with pytest.raises(AppException) as exc:
            inference_module._resolve_feature_order(
                {},
                RawModel(),
                "forecast",
                registered_names=["lag_24", "hour"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Feature order source: refused" in exc.value.error_detail

    def test_raw_xgboost_booster_feature_names_are_not_used(self):
        import pandas as pd

        xgboost = pytest.importorskip("xgboost")
        training_data = pd.DataFrame(
            {
                "lag_24": [0, 1, 0, 1],
                "hour": [0, 0, 1, 1],
            }
        )
        model = xgboost.train(
            {"objective": "reg:squarederror", "nthread": 1},
            xgboost.DMatrix(training_data, label=[0, 100, 1, 101]),
            num_boost_round=1,
        )

        with pytest.raises(AppException) as exc:
            inference_module._resolve_feature_order(
                {},
                model,
                "forecast",
                registered_names=["lag_24", "hour"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Feature order source: refused" in exc.value.error_detail

    def test_constructor_defined_generic_feature_names_are_not_trusted(self):
        class RawModel(_StubModel):
            n_features_in_ = 2
            feature_names = ["lag_24", "hour"]

        with pytest.raises(AppException) as exc:
            inference_module._resolve_feature_order(
                {},
                RawModel(),
                "forecast",
                registered_names=["lag_24", "hour"],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Feature order source: refused" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_raw_estimator_refuses_matching_registry_feature_contract(
        self, monkeypatch
    ):
        class RawModel(_StubModel):
            n_features_in_ = 2

        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                RawModel(),
                {"hour": 8, "lag_24": 12},
                feature_names=["hour", "lag_24"],
                legacy=True,
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Feature order source: refused" in exc.value.error_detail
        assert "Model 'forecast'" in exc.value.error_detail
        assert "swap values between columns" in exc.value.error_detail
        assert "pandas DataFrame" in exc.value.error_detail
        assert "upload the new file" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_v2_artifact_without_feature_columns_is_refused_early(
        self, monkeypatch
    ):
        class RawModel(_StubModel):
            feature_names_in_ = np.array(["lag_24", "hour"])

        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                RawModel(),
                {"hour": 8, "lag_24": 12},
                feature_names=[],
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "artifact does not record its required feature set" in (
            exc.value.error_detail
        )
        assert "feature_columns" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_raw_estimator_converts_quoted_numeric_default(self, monkeypatch):
        class RawModel(_StubModel):
            feature_names_in_ = np.array(["hour", "lag_24"])
            received = None

            def predict(self, input_data):
                self.received = input_data
                return np.zeros(len(input_data), dtype=int)

        model = RawModel()
        result = await _predict(
            monkeypatch,
            model,
            {"hour": 8},
            feature_names=["hour", "lag_24"],
            inference_params={"featureDefaults": {"lag_24": "5"}},
        )

        np.testing.assert_array_equal(model.received, [[8, 5]])
        assert result["defaults_applied"] == ["lag_24"]

    @pytest.mark.asyncio
    async def test_model_failure_names_applied_default(self, monkeypatch):
        class RawModel(_StubModel):
            feature_names_in_ = np.array(["hour", "lag_24"])

            def predict(self, input_data):
                raise ValueError("model rejected prepared input")

        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                RawModel(),
                {"hour": 8},
                feature_names=["hour", "lag_24"],
                inference_params={"featureDefaults": {"lag_24": 5}},
            )

        assert exc.value.error_key is ErrorKey.INTERNAL_ERROR
        assert "configured feature default(s) were applied" in exc.value.error_detail
        assert "lag_24" in exc.value.error_detail
        assert "model rejected prepared input" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_text_default_does_not_block_complete_request(self, monkeypatch):
        class RawModel(_StubModel):
            feature_names_in_ = np.array(["region", "hour"])

        result = await _predict(
            monkeypatch,
            RawModel(),
            {"region": "east", "hour": 8},
            feature_names=["region", "hour"],
            inference_params={"featureDefaults": {"region": "unknown"}},
        )

        assert result["status"] == "success"
        assert result["defaults_applied"] == []

    @pytest.mark.asyncio
    async def test_data_preparation_failure_keeps_original_cause_with_applied_default(
        self, monkeypatch
    ):
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {"hour": "abc"},
                feature_names=["hour", "lag_24"],
                inference_params={"featureDefaults": {"lag_24": 0}},
                scaler=MagicMock(),
                scaled_columns=["hour"],
            )

        assert exc.value.error_key is ErrorKey.INTERNAL_ERROR
        assert "Data preparation failed after configured feature default(s)" in exc.value.error_detail
        assert "abc" in exc.value.error_detail
        assert "applied for: lag_24" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_long_prediction_failure_keeps_default_hint_visible(self, monkeypatch):
        class RawModel(_StubModel):
            feature_names_in_ = np.array(["hour", "lag_24"])

            def predict(self, input_data):
                raise ValueError("invalid value 'abc' for hour\nStack trace:\n" + "x" * 2000)

        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                RawModel(),
                {"hour": "abc"},
                feature_names=["hour", "lag_24"],
                inference_params={"featureDefaults": {"lag_24": 0}},
            )

        visible_detail = truncate_for_log(describe_exception(exc.value), 500)
        assert exc.value.error_key is ErrorKey.INTERNAL_ERROR
        assert "configured feature default(s) were applied for: lag_24" in visible_detail
        assert "invalid value 'abc' for hour" in visible_detail
        assert "Stack trace" not in visible_detail

    @pytest.mark.asyncio
    async def test_raw_estimator_feature_count_does_not_replace_feature_names(
        self, monkeypatch
    ):
        class RawModel(_StubModel):
            n_features_in_ = 3

        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                RawModel(),
                {"hour": 8, "lag_24": 12},
                feature_names=["hour", "lag_24"],
                legacy=True,
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Model 'forecast'" in exc.value.error_detail
        assert "does not record a safe, unambiguous feature-name order" in (
            exc.value.error_detail
        )
        assert "swap values between columns" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_raw_estimator_without_names_or_count_gets_retraining_guidance(
        self, monkeypatch
    ):
        class RawModel(_StubModel):
            pass

        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                RawModel(),
                {"hour": 8, "lag_24": 12},
                feature_names=["hour", "lag_24"],
                legacy=True,
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "Feature order source: refused" in exc.value.error_detail
        assert "Model 'forecast'" in exc.value.error_detail
        assert "pandas DataFrame" in exc.value.error_detail
        assert "upload the new file" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_known_none_category_is_not_treated_as_missing(self, monkeypatch):
        result = await _predict(
            monkeypatch,
            _StubModel(),
            {"hour": 8, "kind": "None"},
            feature_names=["hour", "kind"],
            label_encodings={"kind": {"None": 0, "wood": 1}},
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_number_like_text_category_reaches_label_encoder_unchanged(
        self, monkeypatch
    ):
        class CapturingModel:
            received = None

            def predict(self, input_data):
                self.received = input_data
                return np.zeros(len(input_data), dtype=int)

        model = CapturingModel()
        await _predict(
            monkeypatch,
            model,
            {"kind": "100"},
            feature_names=["kind"],
            label_encodings={"kind": {"100": 0, "A12": 1, "200": 2}},
        )

        np.testing.assert_array_equal(model.received, [[0]])

    @pytest.mark.asyncio
    async def test_known_none_category_can_be_a_default(self, monkeypatch):
        result = await _predict(
            monkeypatch,
            _StubModel(),
            {"hour": 8},
            feature_names=["hour", "kind"],
            inference_params={"featureDefaults": {"kind": "None"}},
            label_encodings={"kind": {"None": 0, "wood": 1}},
        )

        assert result["defaults_applied"] == ["kind"]

    @pytest.mark.asyncio
    async def test_unknown_categorical_default_is_rejected_before_prediction(self, monkeypatch):
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {"hour": 8},
                feature_names=["hour", "kind"],
                inference_params={"featureDefaults": {"kind": 0}},
                label_encodings={"kind": {"None": 0, "wood": 1}},
            )

        assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
        assert "categorical default" in exc.value.error_detail
        assert "kind" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_legacy_training_fill_is_applied_and_reported(self, monkeypatch):
        result = await _predict(
            monkeypatch,
            _StubModel(),
            {"hour": 8},
            feature_names=["hour", "is_weekend"],
            missing_value_fills={"is_weekend": 0},
        )

        assert result["input_data"] == {"hour": [8], "is_weekend": [0]}
        assert result["defaults_applied"] == ["is_weekend"]
        assert "saved training fill" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_explicit_empty_defaults_keep_saved_training_fills(self, monkeypatch):
        result = await _predict(
            monkeypatch,
            _StubModel(),
            {"hour": 8},
            feature_names=["hour", "is_weekend"],
            inference_params={"featureDefaults": {}},
            missing_value_fills={"is_weekend": 0},
        )

        assert result["input_data"] == {"hour": [8], "is_weekend": [0]}
        assert result["defaults_applied"] == ["is_weekend"]

    @pytest.mark.asyncio
    async def test_explicit_default_overrides_its_fill_and_keeps_other_fills(
        self,
        monkeypatch,
    ):
        result = await _predict(
            monkeypatch,
            _StubModel(),
            {},
            feature_names=["hour", "is_weekend"],
            inference_params={"featureDefaults": {"hour": 12}},
            missing_value_fills={"hour": 3, "is_weekend": 0},
        )

        assert result["input_data"] == {"hour": [12], "is_weekend": [0]}
        assert result["defaults_applied"] == ["hour", "is_weekend"]
        assert "is_weekend" in result["warnings"][0]
        assert "hour" not in result["warnings"][0].split(":", 1)[-1]

    @pytest.mark.asyncio
    async def test_invalid_saved_training_fill_is_identified_as_a_fallback(
        self,
        monkeypatch,
    ):
        with pytest.raises(AppException) as exc:
            await _predict(
                monkeypatch,
                _StubModel(),
                {"hour": 8},
                feature_names=["hour", "is_weekend"],
                missing_value_fills={"is_weekend": float("nan")},
            )

        assert "Inference fallback value" in exc.value.error_detail
        assert "Model default" not in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_registry_valid_default_for_old_artifact_feature_is_ignored(
        self,
        monkeypatch,
    ):
        result = await _predict(
            monkeypatch,
            _StubModel(),
            {"hour": 8},
            feature_names=["hour"],
            registered_feature_names=["hour", "retired_feature"],
            inference_params={"featureDefaults": {"retired_feature": 1}},
        )

        assert result["defaults_applied"] == []
        assert "retired_feature" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_deliberate_model_default_is_applied_and_reported(self, monkeypatch):
        class CapturingModel:
            received = None

            def predict(self, input_data):
                self.received = input_data
                return np.zeros(len(input_data), dtype=int)

        model = CapturingModel()
        result = await _predict(
            monkeypatch,
            model,
            {"hour": [8, 9]},
            feature_names=["hour", "is_weekend"],
            inference_params={"featureDefaults": {"is_weekend": 0}},
        )

        np.testing.assert_array_equal(model.received, [[8, 0], [9, 0]])
        assert result["input_data"] == {"hour": [8, 9], "is_weekend": [0, 0]}
        assert result["defaults_applied"] == ["is_weekend"]

    @pytest.mark.asyncio
    async def test_complete_inputs_report_no_defaults(self, monkeypatch):
        result = await _predict(
            monkeypatch,
            _StubModel(),
            {"hour": 8, "is_weekend": 0},
            feature_names=["hour", "is_weekend"],
            inference_params={"featureDefaults": {"is_weekend": 1}},
        )

        assert result["defaults_applied"] == []

    @pytest.mark.asyncio
    async def test_ratio_baseline_remains_an_allowed_inference_only_input(self, monkeypatch):
        class RatioModel:
            def predict(self, input_data):
                return np.full(len(input_data), 0.5)

        result = await _predict(
            monkeypatch,
            RatioModel(),
            {"feature": 2, "baseline": 10},
            feature_names=["feature"],
            inference_params={"ratioBaselineColumn": "baseline"},
            target_transform={"baselineColumn": "baseline"},
        )

        assert result["prediction"] == [5.0]
        assert result["defaults_applied"] == []

    @pytest.mark.asyncio
    async def test_model_feature_order_wins_over_caller_order(self, monkeypatch):
        class CapturingModel:
            received = []

            def predict(self, input_data):
                self.received.append(input_data.to_numpy())
                return input_data.iloc[:, 0] * 10 + input_data.iloc[:, 1]

        model = CapturingModel()
        first = await _predict(
            monkeypatch,
            model,
            {"hour": 20, "is_weekend": 1},
            feature_names=["hour", "is_weekend"],
        )
        second = await _predict(
            monkeypatch,
            model,
            {"is_weekend": 1, "hour": 20},
            feature_names=["hour", "is_weekend"],
        )

        np.testing.assert_array_equal(model.received, [[[20, 1]], [[20, 1]]])
        assert first["prediction"] == second["prediction"] == [201]

    @pytest.mark.asyncio
    async def test_raw_feature_columns_remain_the_caller_contract(self, monkeypatch):
        class CapturingModel:
            received = None

            def predict(self, input_data):
                self.received = input_data
                return np.zeros(len(input_data), dtype=int)

        model = CapturingModel()
        await _predict(
            monkeypatch,
            model,
            {"hour": 8, "lag_24": 12},
            feature_names=["hour", "lag_24"],
            fitted_feature_names=["hour", "lag_24_encoded"],
        )

        np.testing.assert_array_equal(model.received, [[8, 12]])


class TestEnsurePklFile:
    @pytest.mark.asyncio
    async def test_downloaded_copy_is_recorded_without_registry_revalidation(self, monkeypatch, tmp_path):
        model_id = uuid4()
        ml_model = SimpleNamespace(id=model_id, name="forecast", pkl_file=None, pkl_file_id=str(uuid4()))
        service = MagicMock(record_local_pkl_file=AsyncMock(), update=AsyncMock())

        async def fake_download(_file_id, destination_path):
            return destination_path

        monkeypatch.setattr(inference_module, "download_pkl_file", fake_download)
        monkeypatch.setattr(inference_module, "ML_MODELS_UPLOAD_DIR", str(tmp_path))
        node = MLModelInferenceNode("ml1", {"id": "ml1", "type": "mlModelInferenceNode", "data": {}}, MagicMock())

        await node._ensure_pkl_file(ml_model, service)

        expected_path = str(tmp_path / f"forecast_{model_id}.pkl")
        service.record_local_pkl_file.assert_awaited_once_with(model_id, expected_path)
        service.update.assert_not_awaited()
        assert ml_model.pkl_file == expected_path
