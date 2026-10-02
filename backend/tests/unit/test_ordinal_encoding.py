"""
DP-5: ordinal encoding must actually be applied - values such as Low, Medium,
High converted into their configured order before training - never silently
turned into missing values.
"""

import pickle
import uuid

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import _mapped_transform
from app.modules.workflow.engine.nodes.ml.ml_utils import ordinal_key
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState

ORDER = {"Low": 0, "Medium": 1, "High": 2}


@pytest.fixture
def node() -> TrainModelNode:
    return TrainModelNode(node_id="test", node_config={}, state=None)


def _encode(node, X_train, X_val, mapping, column="level"):
    return node._encode_categoricals(
        X_train, X_val, [{"columnName": column, "strategy": "ordinal", "ordinalMapping": mapping}]
    )


class TestOrdinalKey:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("High", "High"),
            ("  High ", "High"),
            (2, "2"),
            (np.int64(2), "2"),
            (2.0, "2"),
            (2.5, "2.5"),
            (True, "True"),
            (None, None),
            (np.nan, None),
            (pd.NA, None),
        ],
    )
    def test_normalizes_values_for_lookup(self, value, expected):
        assert ordinal_key(value) == expected

    def test_matching_is_case_sensitive(self):
        assert ordinal_key("a") != ordinal_key("A")


class TestOrdinalIsApplied:
    def test_low_medium_high_become_their_configured_positions(self, node):
        X_train = pd.DataFrame({"level": ["Low", "High", "Medium", "Low"]})
        X_val = pd.DataFrame({"level": ["High", "Low"]})
        X_train, X_val, _, ordinals, _ = _encode(node, X_train, X_val, ORDER)
        assert X_train["level"].tolist() == [0, 2, 1, 0]
        assert X_val["level"].tolist() == [2, 0]
        assert ordinals == {"level": ORDER}

    def test_stray_spaces_in_the_data_still_match(self, node):
        X_train = pd.DataFrame({"level": [" Low", "High  "]})
        X_train, _, _, _, _ = _encode(node, X_train, None, ORDER)
        assert X_train["level"].tolist() == [0, 2]

    def test_numeric_categories_match_json_string_keys(self, node):
        # A CSV column of 1/2/3 loads as int (or float 1.0/2.0 when values are
        # missing), while the mapping's JSON keys are strings. Before the fix
        # every value silently became NaN.
        mapping = {"1": 10, "2": 20, "3": 30}
        X_int = pd.DataFrame({"grade": [1, 2, 3]})
        X_int, _, _, _, _ = _encode(node, X_int, None, mapping, column="grade")
        assert X_int["grade"].tolist() == [10, 20, 30]

        X_float = pd.DataFrame({"grade": [1.0, np.nan, 3.0]})
        X_float, _, _, _, _ = _encode(node, X_float, None, mapping, column="grade")
        assert X_float["grade"].tolist()[0] == 10
        assert np.isnan(X_float["grade"].tolist()[1])
        assert X_float["grade"].tolist()[2] == 30

    def test_missing_values_stay_missing(self, node):
        X_train = pd.DataFrame({"level": ["Low", None, "High"]})
        X_train, _, _, _, _ = _encode(node, X_train, None, ORDER)
        values = X_train["level"].tolist()
        assert values[0] == 0 and np.isnan(values[1]) and values[2] == 2


class TestUnmappedValuesFailClearly:
    def test_training_value_with_no_position_fails_with_the_value_named(self, node):
        X_train = pd.DataFrame({"level": ["Low", "Very High", "High"]})
        with pytest.raises(AppException) as exc_info:
            _encode(node, X_train, None, ORDER)
        detail = exc_info.value.error_detail
        assert "level" in detail
        assert "Very High" in detail
        assert "training" in detail

    def test_validation_value_with_no_position_fails_too(self, node):
        X_train = pd.DataFrame({"level": ["Low", "High"]})
        X_val = pd.DataFrame({"level": ["Extreme"]})
        with pytest.raises(AppException) as exc_info:
            _encode(node, X_train, X_val, ORDER)
        assert "Extreme" in exc_info.value.error_detail
        assert "validation" in exc_info.value.error_detail

    def test_different_case_is_reported_not_merged(self, node):
        X_train = pd.DataFrame({"level": ["low"]})
        with pytest.raises(AppException) as exc_info:
            _encode(node, X_train, None, ORDER)
        assert "'low'" in exc_info.value.error_detail


class TestOrdinalConfigValidation:
    """The checks process() runs before loading any data."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mapping", [None, {}])
    async def test_missing_order_gives_an_actionable_message(self, tmp_path, mapping):
        result_or_error = await _run_process(tmp_path, mapping)
        assert isinstance(result_or_error, AppException)
        assert "has no value order" in result_or_error.error_detail
        assert "Categorical Encoding" in result_or_error.error_detail

    @pytest.mark.asyncio
    async def test_non_numeric_position_is_rejected(self, tmp_path):
        result_or_error = await _run_process(tmp_path, {"Low": "first", "High": 2})
        assert isinstance(result_or_error, AppException)
        assert "numeric position" in result_or_error.error_detail
        assert "Low" in result_or_error.error_detail


class TestOrdinalEndToEnd:
    @pytest.mark.asyncio
    async def test_trains_with_the_order_and_inference_reapplies_it(self, tmp_path):
        result = await _run_process(tmp_path, ORDER)
        assert not isinstance(result, AppException)
        assert result["success"] is True

        with open(result["model_file_path"], "rb") as f:
            metadata = pickle.load(f)["metadata"]
        assert metadata["ordinal_encodings"]["level"] == ORDER

        # Inference matches the same way training does (spaces, numbers).
        encoded = _mapped_transform(
            {"level": [" High", "Low", "Unknown"]},
            ["level"],
            metadata["ordinal_encodings"],
            batch_size=3,
            unseen_value=np.nan,
            normalize_keys=True,
        )
        assert encoded[0, 0] == 2 and encoded[1, 0] == 0 and np.isnan(encoded[2, 0])

    def test_inference_matches_numeric_inputs_for_models_saved_before_the_fix(self):
        # An older model's metadata holds the mapping exactly as configured.
        encoded = _mapped_transform(
            {"grade": [2, 3.0]}, ["grade"], {"grade": {"2": 1, "3": 2}},
            batch_size=2, unseen_value=np.nan, normalize_keys=True,
        )
        assert encoded[:, 0].tolist() == [1, 2]


async def _run_process(tmp_path, mapping):
    rng = np.random.default_rng(5)
    n = 60
    levels = rng.choice(["Low", "Medium", "High"], size=n)
    num = rng.normal(0, 1, n)
    y = (num + (levels == "High") > 0.5).astype(int)
    csv_path = tmp_path / f"ordinal_{uuid.uuid4().hex[:6]}.csv"
    pd.DataFrame({"level": levels, "num": num, "target": y}).to_csv(csv_path, index=False)

    encoding = {"columnName": "level", "strategy": "ordinal"}
    if mapping is not None:
        encoding["ordinalMapping"] = mapping
    train_node = TrainModelNode(
        node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
    )
    try:
        return await train_node.process(
            {
                "name": f"ordinal-{uuid.uuid4().hex[:8]}",
                "modelType": "random_forest",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["level", "num"],
                "validationSplit": 0.25,
                "taskType": "classification",
                "categoricalEncoding": [encoding],
            }
        )
    except AppException as e:
        return e
