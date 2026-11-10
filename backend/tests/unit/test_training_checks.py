import numpy as np
import pandas as pd
import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import training_checks


class TestFormatValue:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (np.float64(49.0), "49"),
            (np.float64(0.123456789), "0.123457"),
            (np.int64(7), "7"),
            (np.float64("nan"), "empty"),
            ("high", "'high'"),
            (True, "True"),
        ],
    )
    def test_numbers_read_like_the_user_wrote_them(self, value, expected):
        assert training_checks.format_value(value) == expected


class TestTargetClasses:
    def test_text_labels_encode_to_codes_and_decode_back(self):
        y = pd.Series(["low", "high", "low", "medium"], index=[5, 6, 7, 8])
        encoded, _, labels = training_checks.encode_target_classes(y)

        assert labels == ["high", "low", "medium"]
        assert encoded.tolist() == [1, 0, 1, 2]
        assert encoded.index.tolist() == [5, 6, 7, 8]
        assert training_checks.decode_target_classes(np.array([2, 0]), labels).tolist() == ["medium", "high"]

    def test_numeric_labels_not_starting_at_zero_keep_their_values(self):
        encoded, _, labels = training_checks.encode_target_classes(pd.Series([3, 1, 2, 3]))

        assert labels == [1, 2, 3]
        assert all(type(label) is int for label in labels)
        assert encoded.tolist() == [2, 0, 1, 2]

    def test_unknown_code_is_refused(self):
        with pytest.raises(ValueError):
            training_checks.decode_target_classes(np.array([5]), ["A", "B"])


class TestDescribeTrainingError:
    def test_xgboost_stack_trace_and_server_paths_are_removed(self):
        error = Exception(
            "[10:27:26] /workspace/src/data/gradient_index.h:99: Check failed: valid: Input data "
            "contains `inf` or a value too large, while `missing` is not set to `inf`\n"
            "Stack trace:\n  [bt] (0) /usr/local/lib/python3.12/site-packages/xgboost/lib/libxgboost.so(+0x22dbbc)"
        )
        message = training_checks.describe_training_error(error, "XGBoost")

        assert "Stack trace" not in message
        assert "/workspace" not in message and "libxgboost" not in message
        assert message.startswith("Input data contains `inf`")

    def test_unknown_parameter_names_the_model(self):
        error = TypeError("RandomForestRegressor.__init__() got an unexpected keyword argument 'foo'")
        assert training_checks.describe_training_error(error, "Random Forest") == (
            "Model Parameters: 'foo' is not a setting of Random Forest. Remove it or check the spelling."
        )

    def test_xgboost_parameter_type(self):
        error = ValueError("Invalid Parameter format for max_depth expect int but value='abc'")
        assert training_checks.describe_training_error(error, "XGBoost") == (
            "Model Parameters: 'max_depth' must be a whole number - got 'abc'."
        )


class TestSettingChecks:
    @pytest.mark.parametrize("value", ["abc", 5, 1, -0.1, None])
    def test_validation_split_out_of_range(self, value):
        with pytest.raises(AppException) as exc:
            training_checks.check_validation_split(value)
        assert "Validation Split must be a fraction" in exc.value.error_detail

    def test_unknown_scoring_lists_supported_ones(self):
        with pytest.raises(AppException) as exc:
            training_checks.check_optimization_config("random_search", {"scoring": "foo"})
        assert "Scoring 'foo' is not supported" in exc.value.error_detail
        assert "Accuracy" in exc.value.error_detail

    def test_empty_scoring_means_auto(self):
        assert training_checks.check_optimization_config("grid_search", {"scoring": ""}) == {}

    def test_scoring_must_match_the_task(self):
        with pytest.raises(AppException) as exc:
            training_checks.check_search_against_data({"scoring": "r2"}, True, 100, False)
        assert "regression metric" in exc.value.error_detail

    def test_cv_folds_larger_than_training_rows(self):
        with pytest.raises(AppException) as exc:
            training_checks.check_search_against_data({"cvFolds": 10}, False, 5, False)
        assert "CV Folds is 10" in exc.value.error_detail


class TestReviewFollowUps:
    def test_saved_sklearn_scorer_and_auto_still_accepted(self):
        assert training_checks.check_optimization_config("grid_search", {"scoring": "roc_auc"}) == {
            "scoring": "roc_auc"
        }
        assert training_checks.check_optimization_config("grid_search", {"scoring": "auto"}) == {}

    def test_decode_accepts_codes_returned_as_strings_or_floats(self):
        labels = ["A", "B", "C"]
        assert training_checks.decode_target_classes(np.array(["2", "0"]), labels).tolist() == ["C", "A"]
        assert training_checks.decode_target_classes(np.array([[1.0]]), labels).tolist() == ["B"]

    def test_validation_only_class_gets_minus_one(self):
        _, y_val, labels = training_checks.encode_target_classes(
            pd.Series(["A", "B"]), pd.Series(["B", "Z"], index=[9, 10])
        )
        assert labels == ["A", "B"]
        assert y_val.tolist() == [1, -1]
        assert y_val.index.tolist() == [9, 10]

    def test_datetime_classes_encode_and_store_as_text(self):
        y = pd.Series(pd.to_datetime(["2024-01-02", "2024-01-01", "2024-01-02"]))
        encoded, _, labels = training_checks.encode_target_classes(y)
        assert encoded.tolist() == [1, 0, 1]
        assert labels == ["2024-01-01T00:00:00", "2024-01-02T00:00:00"]

    def test_numeric_text_regression_target_becomes_numbers(self):
        converted = training_checks.numeric_target(pd.Series(["1.5", "2", None]))
        assert pd.api.types.is_float_dtype(converted)
        mixed = pd.Series(["1.5", "abc"])
        assert training_checks.numeric_target(mixed) is mixed

    def test_class_weight_follows_the_codes(self):
        params = training_checks.remap_class_weight({"class_weight": {"yes": 3, "no": 1}}, ["no", "yes"])
        assert params["class_weight"] == {1: 3, 0: 1}
        assert training_checks.remap_class_weight({"class_weight": "balanced"}, ["no"]) == {
            "class_weight": "balanced"
        }
        with pytest.raises(AppException):
            training_checks.remap_class_weight({"class_weight": {"maybe": 2}}, ["no", "yes"])

    def test_cleared_search_numbers_use_defaults(self):
        assert training_checks.check_optimization_config("random_search", {"cvFolds": None, "nIter": ""}) == {}

    def test_data_file_paths_are_hidden(self):
        error = FileNotFoundError("[Errno 2] No such file or directory: '/app/datavolume/ml_models/abc/x_v2.0.pkl'")
        message = training_checks.describe_training_error(error, "XGBoost")
        assert "/app" not in message and "<path>" in message

    def test_drop_column_columns_are_not_reported_empty(self):
        X = pd.DataFrame({"x": [1.0, 2.0], "notes": [np.nan, np.nan]})
        training_checks.check_training_data(
            X, pd.Series([1.0, 2.0]), "y", False, "Random Forest",
            missing_value_strategies={"notes": "drop_column"},
        )

    def test_other_type_errors_are_not_blamed_on_model_parameters(self):
        error = TypeError("to_datetime() got an unexpected keyword argument 'infer_datetime_format'")
        assert "Model Parameters" not in training_checks.describe_training_error(error, "XGBoost")

    def test_dates_and_units_with_slashes_are_kept(self):
        error = ValueError("bad value 2024/01/15 in speed/km/h")
        assert training_checks.describe_training_error(error, "XGBoost") == "bad value 2024/01/15 in speed/km/h"


class TestThirdReviewFollowUps:
    def test_filled_columns_still_get_the_infinity_check(self):
        X = pd.DataFrame({"x": [1.0, np.inf, np.nan]})
        with pytest.raises(AppException) as exc:
            training_checks.check_training_data(
                X, pd.Series([1.0, 2.0, 3.0]), "y", False, "Random Forest",
                missing_value_strategies={"x": "impute_constant"},
            )
        assert "infinite values" in exc.value.error_detail

    def test_many_empty_columns_are_summarised(self):
        X = pd.DataFrame({f"c{i}": [np.nan, np.nan] for i in range(12)})
        with pytest.raises(AppException) as exc:
            training_checks.check_training_data(X, pd.Series([1.0, 2.0]), "y", False, "Random Forest")
        assert "and 7 more" in exc.value.error_detail

    def test_class_weight_keys_match_float_labels(self):
        params = training_checks.remap_class_weight({"class_weight": {"0": 1, "1": 5}}, [0.0, 1.0])
        assert params["class_weight"] == {0: 1, 1: 5}

    def test_catboost_class_parameters_follow_the_codes(self):
        params = training_checks.remap_class_weight(
            {"class_weights": {"A": 1, "B": 3}, "class_names": ["A", "B"]}, ["A", "B"]
        )
        assert params == {"class_weights": {0: 1, 1: 3}, "class_names": [0, 1]}

    def test_svm_probability_scoring_needs_probability(self):
        with pytest.raises(AppException) as exc:
            training_checks.check_search_against_data(
                {"scoring": "neg_log_loss"}, True, 100, False, model_type="svm", model_parameters={}
            )
        assert '"probability": true' in exc.value.error_detail
        training_checks.check_search_against_data(
            {"scoring": "neg_log_loss"}, True, 100, False,
            model_type="svm", model_parameters={"probability": True},
        )

    def test_random_points_is_validated(self):
        with pytest.raises(AppException) as exc:
            training_checks.check_optimization_config("random_search", {"randomPoints": "abc"})
        assert "Random Points" in exc.value.error_detail

    @pytest.mark.parametrize(
        "text", ["datavolume/ml_models/abc-123/model.pkl", "./app/x/y.py:12", "/app/datavolume/u/x.csv"]
    )
    def test_relative_and_absolute_paths_are_hidden(self, text):
        message = training_checks.describe_training_error(ValueError(f"failed at {text}"), "XGBoost")
        assert message == "failed at <path>"

    def test_parameter_messages_are_capped(self):
        error = ValueError(
            "The 'x' parameter of SVC must be an int. Got " + "[" + "1, " * 400 + "1] instead."
        )
        assert len(training_checks.describe_training_error(error, "SVM")) <= 500
