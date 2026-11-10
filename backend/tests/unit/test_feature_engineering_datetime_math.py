"""
Train Model feature engineering: Date-Time Features and Math Function.

Date-Time Features turn one date/time column into calendar parts (year,
month, day, day of week, quarter, hour when the values have a time of day,
weekend flag). Math Function applies sin, cos, sqrt, abs, square or cube root
to numeric columns. Both must be replayed identically at inference and fail
clearly on values they can't take.
"""

import pickle
import uuid
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_model_inference_node as inference_module
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import (
    MLModelInferenceNode,
    _replay_feature_engineering,
)
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from tests.unit.ml_training_fixtures import training_sandbox


@pytest.fixture
def node() -> TrainModelNode:
    return TrainModelNode(node_id="test", node_config={}, state=None)


def _fe(node, X_train, X_val, item):
    return node._engineer_features(X_train, X_val, [item])


def _dates(values):
    return pd.DataFrame({"ts": values, "a": np.arange(len(values), dtype=float)})


# --- Date-Time Features -------------------------------------------------------


class TestDatetimeFeatures:
    def test_all_parts_from_timestamps_and_replay(self, node):
        # Saturday 2024-03-16 14:30 and Monday 2024-01-01 09:00
        X_train = _dates(["2024-03-16 14:30:00", "2024-01-01 09:00:00"])
        X_val = _dates(["2023-12-31 23:15:00"])

        X_train2, X_val2, steps = _fe(node, X_train, X_val, {
            "newColumnName": "when", "strategy": "datetime_features", "datetimeColumn": "ts",
        })

        assert list(X_train2.columns) == [
            "a", "when_year", "when_month", "when_day", "when_day_of_week",
            "when_quarter", "when_hour", "when_is_weekend",
        ]
        assert X_train2.iloc[0][1:].tolist() == [2024, 3, 16, 5, 1, 14, 1]
        assert X_train2.iloc[1][1:].tolist() == [2024, 1, 1, 0, 1, 9, 0]
        assert X_val2.iloc[0][1:].tolist() == [2023, 12, 31, 6, 4, 23, 1]

        replayed = _replay_feature_engineering({"ts": ["2024-03-16 14:30:00"]}, steps, 1)
        assert [replayed[c][0] for c in steps[0]["output_columns"]] == [2024, 3, 16, 5, 1, 14, 1]

    def test_hour_is_left_out_when_the_values_have_no_time_of_day(self, node):
        X_train2, _, steps = _fe(node, _dates(["2024-03-16", "2024-04-02"]), None, {
            "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
        })

        assert steps[0]["parts"] == ["year", "month", "day", "day_of_week", "quarter", "is_weekend"]
        assert "d_hour" not in X_train2.columns

    def test_only_the_chosen_parts_are_created(self, node):
        X_train2, _, steps = _fe(node, _dates(["2024-03-16", "2024-04-02"]), None, {
            "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
            "datetimeParts": ["month", "is_weekend"],
        })

        assert steps[0]["output_columns"] == ["d_month", "d_is_weekend"]
        assert X_train2["d_is_weekend"].tolist() == [1, 0]

    def test_already_parsed_dates_are_used_as_they_are(self, node):
        X_train = _dates(pd.to_datetime(["2024-03-16", "2024-04-02"]))
        X_train2, _, _ = _fe(node, X_train, None, {
            "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
            "datetimeParts": ["year"],
        })
        assert X_train2["d_year"].tolist() == [2024, 2024]

    def test_unreadable_dates_fail_at_training_and_inference(self, node):
        with pytest.raises(AppException) as exc_info:
            _fe(node, _dates(["2024-03-16", "not a date"]), None, {
                "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
            })
        assert "1 value(s) of 'ts' in the training data could not be read" in exc_info.value.error_detail
        assert "'not a date'" in exc_info.value.error_detail

        _, _, steps = _fe(node, _dates(["2024-03-16", "2024-04-02"]), None, {
            "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
        })
        problems = []
        replayed = _replay_feature_engineering({"ts": ["someday"]}, steps, 1, problems=problems)
        assert replayed == {}
        assert "could not be read as a date/time" in problems[0]["cause"]

    def test_mixed_utc_offsets_are_read_in_utc_alone_or_together(self, node):
        X_train = _dates(["2024-03-15T23:30:00+02:00", "2024-03-15T10:00:00Z", "2024-03-16T08:00:00+00:00"])
        X_train2, _, steps = _fe(node, X_train, None, {
            "newColumnName": "t", "strategy": "datetime_features", "datetimeColumn": "ts", "datetimeParts": ["day", "hour"],
        })

        assert X_train2["t_hour"].tolist() == [21, 10, 8]
        # The same value on its own at prediction gives the same parts.
        replayed = _replay_feature_engineering({"ts": ["2024-03-15T23:30:00+02:00"]}, steps, 1)
        assert [replayed["t_day"][0], replayed["t_hour"][0]] == [15, 21]

    def test_day_first_dates_read_day_first_in_every_row_and_at_prediction(self, node):
        # 13/02/2024 shows the column is day first, so 01/02/2024 is 1 February.
        X_train = _dates(["01/02/2024", "13/02/2024"])
        X_val = _dates(["05/03/2024"])
        X_train2, X_val2, steps = _fe(node, X_train, X_val, {
            "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
            "datetimeParts": ["month", "day"],
        })

        assert X_train2[["d_month", "d_day"]].values.tolist() == [[2, 1], [2, 13]]
        assert X_val2[["d_month", "d_day"]].values.tolist() == [[3, 5]]
        assert steps[0]["day_first"] is True

        # One ambiguous value at prediction is still read day first.
        replayed = _replay_feature_engineering({"ts": ["01/02/2024"]}, steps, 1)
        assert [replayed["d_month"][0], replayed["d_day"][0]] == [2, 1]

    def test_month_first_dates_and_year_first_dates_are_unchanged(self, node):
        X_train2, _, steps = _fe(node, _dates(["01/02/2024", "02/13/2024", "2024-03-04"]), None, {
            "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
            "datetimeParts": ["month", "day"],
        })
        assert X_train2[["d_month", "d_day"]].values.tolist() == [[1, 2], [2, 13], [3, 4]]
        assert steps[0]["day_first"] is False

    def test_day_first_does_not_change_year_first_dates(self, node):
        X_train2, _, _ = _fe(node, _dates(["13/02/2024", "2024-03-04", "2024-03-04T10:00:00+02:00"]), None, {
            "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
            "datetimeParts": ["month", "day"],
        })
        assert X_train2[["d_month", "d_day"]].values.tolist() == [[2, 13], [3, 4], [3, 4]]

    @pytest.mark.parametrize(
        "train, val, problem",
        [
            (["13/02/2024", "02/13/2024"], None, "mixes day-first and month-first dates"),
            # The day-first value is only in the validation data.
            (["02/13/2024"], ["13/02/2024"], "mixes day-first and month-first dates"),
            (["01/02/2024", "03/04/2024"], None, "could be day-first or month-first"),
        ],
    )
    def test_dates_whose_day_and_month_order_is_unclear_are_refused(self, node, train, val, problem):
        with pytest.raises(AppException) as exc_info:
            _fe(node, _dates(train), _dates(val) if val else None, {
                "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
            })
        assert problem in exc_info.value.error_detail

    def test_a_model_saved_before_the_date_order_was_recorded_reads_month_first(self):
        steps = [{
            "strategy": "datetime_features", "new_col": "d", "column": "ts",
            "parts": ["month", "day"], "output_columns": ["d_month", "d_day"],
        }]
        replayed = _replay_feature_engineering({"ts": ["01/02/2024"]}, steps, 1)
        assert [replayed["d_month"][0], replayed["d_day"][0]] == [1, 2]

    def test_a_numeric_column_is_refused(self, node):
        with pytest.raises(AppException) as exc_info:
            _fe(node, pd.DataFrame({"ts": [20240316, 20240402]}), None, {
                "newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts",
            })
        assert "holds numbers, not dates" in exc_info.value.error_detail

    @pytest.mark.parametrize(
        "item, problem",
        [
            ({"newColumnName": "d", "strategy": "datetime_features"}, "choose the date/time column"),
            (
                {"newColumnName": "d", "strategy": "datetime_features", "datetimeColumn": "ts", "datetimeParts": ["week"]},
                "unknown part(s) ['week']",
            ),
        ],
    )
    def test_invalid_config_is_refused_before_loading_data(self, item, problem):
        with pytest.raises(AppException) as exc_info:
            TrainModelNode._validate_datetime_features_config(item)
        assert problem in exc_info.value.error_detail


# --- Math Function -----------------------------------------------------------


class TestMathFunction:
    @pytest.mark.parametrize(
        "function, expected",
        [
            ("sin", np.sin), ("cos", np.cos), ("sqrt", np.sqrt),
            ("abs", np.abs), ("square", np.square), ("cbrt", np.cbrt),
        ],
    )
    def test_each_function_at_training_and_inference(self, node, function, expected):
        X_train = pd.DataFrame({"a": [0.0, 1.5, 4.0, 9.0], "b": [2.0, 3.0, 5.0, 7.0]})
        X_train2, _, steps = _fe(node, X_train.copy(), None, {
            "newColumnName": "m", "strategy": "math_transform", "mathFunction": function, "sourceColumns": ["a"],
        })

        assert np.allclose(X_train2["m"], expected(X_train["a"]))
        assert "a" in X_train2.columns  # sources kept by default
        replayed = _replay_feature_engineering({"a": [16.0]}, steps, 1)
        assert np.allclose(replayed["m"], expected(np.array([16.0])))

    def test_square_root_of_a_negative_value_fails_clearly(self, node):
        with pytest.raises(AppException) as exc_info:
            _fe(node, pd.DataFrame({"a": [1.0, -4.0]}), None, {
                "newColumnName": "r", "strategy": "math_transform", "mathFunction": "sqrt", "sourceColumns": ["a"],
            })
        assert "Square Root needs values of 0 or more" in exc_info.value.error_detail

        _, _, steps = _fe(node, pd.DataFrame({"a": [1.0, 4.0]}), None, {
            "newColumnName": "r", "strategy": "math_transform", "mathFunction": "sqrt", "sourceColumns": ["a"],
        })
        problems = []
        _replay_feature_engineering({"a": [-1.0]}, steps, 1, problems=problems)
        assert "Square Root needs values of 0 or more" in problems[0]["cause"]

    def test_an_infinite_result_fails_clearly(self, node):
        with pytest.raises(AppException) as exc_info:
            _fe(node, pd.DataFrame({"a": [1.0, 1e200]}), None, {
                "newColumnName": "sq", "strategy": "math_transform", "mathFunction": "square", "sourceColumns": ["a"],
            })
        assert "the result is infinite or empty for {'a': 1}" in exc_info.value.error_detail

        _, _, steps = _fe(node, pd.DataFrame({"a": [1.0, 2.0]}), None, {
            "newColumnName": "sq", "strategy": "math_transform", "mathFunction": "square", "sourceColumns": ["a"],
        })
        problems = []
        assert _replay_feature_engineering({"a": [1e200]}, steps, 1, problems=problems) == {}
        assert "the result is infinite or empty" in problems[0]["cause"]

    def test_an_unknown_function_is_refused(self):
        with pytest.raises(AppException) as exc_info:
            TrainModelNode._validate_column_transform_config({
                "newColumnName": "m", "strategy": "math_transform", "mathFunction": "exp", "sourceColumns": ["a"],
            })
        assert "function must be one of sin, cos, sqrt, abs, square, cbrt" in exc_info.value.error_detail


# --- Train, then predict -----------------------------------------------------


class _StubMLModelsService:
    def __init__(self, ml_model):
        self._ml_model = ml_model

    async def get_by_id(self, model_id):
        return self._ml_model


@pytest.mark.asyncio
async def test_train_then_predict_with_datetime_and_math_features(tmp_path, monkeypatch):
    data_volume = training_sandbox(monkeypatch, tmp_path)
    rng = np.random.default_rng(3)
    n = 120
    timestamps = pd.date_range("2023-01-01 08:00", periods=n, freq="37h")
    df = pd.DataFrame({
        "ts": timestamps.strftime("%Y-%m-%d %H:%M:%S"),
        "a": rng.uniform(0, 10, n),
    })
    df["target"] = 3 * (timestamps.dayofweek >= 5) + np.sqrt(df["a"]) + rng.normal(0, 0.05, n)
    path = tmp_path / "sales.csv"
    df.to_csv(path, index=False)

    train_node = TrainModelNode(node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={}))
    result = await train_node.process({
        "name": f"dt-math-{uuid.uuid4().hex[:8]}",
        "modelType": "linear_regression",
        "fileUrl": str(path),
        "targetColumn": "target",
        "featureColumns": ["ts", "a"],
        "validationSplit": 0.25,
        "featureEngineering": [
            {"newColumnName": "when", "strategy": "datetime_features", "datetimeColumn": "ts"},
            {"newColumnName": "root_a", "strategy": "math_transform", "mathFunction": "sqrt", "sourceColumns": ["a"]},
        ],
    })

    assert result["success"] is True, result
    model_path = str(data_volume / result["model_file_path"])
    with open(model_path, "rb") as f:
        metadata = pickle.load(f)["metadata"]
    # The timestamp is a raw input, but the model only sees its parts.
    assert metadata["feature_columns"] == ["ts", "a"]
    assert "ts" not in metadata["model_input_columns"]
    assert {"when_hour", "when_is_weekend", "root_a"} <= set(metadata["model_input_columns"])
    assert not metadata.get("categorical_columns")

    ml_model = SimpleNamespace(
        id=uuid.uuid4(), name="dt-math", pkl_file=model_path, pkl_file_id=None,
        updated_at=datetime.now(), model_type="linear_regression", target_variable="target",
        features=["ts", "a"],
    )
    monkeypatch.setattr(inference_module.injector, "get", lambda cls: _StubMLModelsService(ml_model))
    inference_node = MLModelInferenceNode(node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={}))

    predicted = await inference_node.process({
        "modelId": str(ml_model.id),
        "inferenceInputs": {"ts": ["2024-03-16 10:00:00", "2024-03-18 10:00:00"], "a": [4.0, 4.0]},
    })
    assert predicted["status"] == "success", predicted
    saturday, monday = predicted["prediction"]
    # Weekend adds about 3; sqrt(4) = 2 in both.
    assert saturday - monday == pytest.approx(3, abs=0.3)

    with pytest.raises(AppException) as exc_info:
        await inference_node.process({
            "modelId": str(ml_model.id), "inferenceInputs": {"ts": "someday", "a": 4.0},
        })
    assert "could not be read as a date/time" in exc_info.value.error_detail

    # A date left out of the request falls back to the model's Feature Default, kept as text.
    ml_model.inference_params = {"featureDefaults": {"ts": "2024-03-16 10:00:00"}}
    defaulted = await inference_node.process({"modelId": str(ml_model.id), "inferenceInputs": {"a": 4.0}})
    assert defaulted["status"] == "success", defaulted
    assert defaulted["prediction"][0] == pytest.approx(saturday)
