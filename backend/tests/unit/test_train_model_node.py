import pickle
import uuid
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.train_model_node import (
    TREE_BASED_MODEL_TYPES,
    TrainModelNode,
    _join_reason_counts,
    _name_rows_by_reason,
    _rows_dropped_warning,
)
from app.modules.workflow.engine.workflow_state import WorkflowState
from tests.unit.ml_training_fixtures import training_sandbox


@pytest.fixture(autouse=True)
def _training_sandbox(monkeypatch, tmp_path):
    # Training only reads files inside the data volume; use pytest's temp folder as it.
    training_sandbox(monkeypatch, tmp_path)


@pytest.fixture
def node() -> TrainModelNode:
    return TrainModelNode(node_id="test", node_config={}, state=None)


class TestResolveAutoScalingMethod:
    @pytest.mark.parametrize("model_type", sorted(TREE_BASED_MODEL_TYPES))
    def test_tree_based_model_types_resolve_to_none(self, node, model_type):
        # Outlier-heavy data should still resolve to "none" for tree-based models,
        # since they're scale-invariant regardless of the data's outlier profile.
        X_train = pd.DataFrame({"a": [1, 2, 3, 4, 1000]})
        assert node._resolve_auto_scaling_method(model_type, X_train, ["a"]) == "none"

    def test_outlier_heavy_non_tree_model_resolves_to_robust(self, node):
        X_train = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 1000]})
        assert node._resolve_auto_scaling_method("linear_regression", X_train, ["a"]) == "robust"

    def test_clean_non_tree_model_resolves_to_standard(self, node):
        X_train = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
        assert node._resolve_auto_scaling_method("logistic_regression", X_train, ["a"]) == "standard"

    @pytest.mark.parametrize(
        "model_type", ["linear_regression", "logistic_regression", "neural_network", "svm", "knn"]
    )
    def test_scale_sensitive_model_types_are_not_tree_based(self, model_type):
        assert model_type not in TREE_BASED_MODEL_TYPES


class TestHasSignificantOutliers:
    def test_no_outliers_returns_false(self, node):
        X_train = pd.DataFrame({"a": list(range(1, 11))})
        assert node._has_significant_outliers(X_train, ["a"]) is False

    def test_significant_outliers_returns_true(self, node):
        X_train = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 1000]})
        assert node._has_significant_outliers(X_train, ["a"]) is True


class TestIsClassificationTask:
    def test_logistic_regression_is_always_classification(self, node):
        y = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        assert node._is_classification_task(y, "logistic_regression", "regression") is True

    def test_linear_regression_is_always_regression(self, node):
        y = pd.Series(["a", "b", "a", "b"])
        assert node._is_classification_task(y, "linear_regression", "classification") is False

    def test_explicit_classification_override_wins_over_continuous_target(self, node):
        y = pd.Series([1.1, 2.2, 3.3, 4.4, 5.5])
        assert node._is_classification_task(y, "xgboost", "classification") is True

    def test_explicit_regression_override_wins_over_low_cardinality_int_target(self, node):
        y = pd.Series([1, 2, 1, 2, 1])
        assert node._is_classification_task(y, "random_forest", "regression") is False

    def test_auto_infers_classification_for_low_cardinality_int_target(self, node):
        y = pd.Series([1, 2, 1, 2, 1])
        assert node._is_classification_task(y, "random_forest", "auto") is True

    def test_auto_infers_classification_for_string_target(self, node):
        y = pd.Series(["a", "b", "a", "b"])
        assert node._is_classification_task(y, "neural_network", "auto") is True

    def test_auto_infers_regression_for_continuous_target(self, node):
        y = pd.Series([1.1, 2.2, 3.3, 4.4, 5.5])
        assert node._is_classification_task(y, "neural_network", "auto") is False

    def test_defaults_to_auto_when_task_type_not_passed(self, node):
        y = pd.Series([1.1, 2.2, 3.3, 4.4, 5.5])
        assert node._is_classification_task(y, "neural_network") is False


class TestClassificationOverrideSplitFallback:
    """
    A `taskType` override lets a user force is_classification=True on a target
    the "auto" heuristic would never have called classification (since auto
    only does so for low-cardinality int/string targets, which the stratified
    split always handled safely). This covers the resulting edge case: some
    classes have too few members to stratify, which must fall back to an
    unstratified split instead of crashing the whole training run.
    """

    @pytest.mark.asyncio
    async def test_falls_back_to_unstratified_split_when_a_class_has_one_member(self, tmp_path):
        rng = np.random.default_rng(7)
        n = 60
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        # 5 classes, two of which have only a single member - stratify raises
        # ValueError on this without the fallback.
        y = np.array([0] * 30 + [1] * 27 + [2] * 1 + [3] * 1 + [4] * 1)
        rng.shuffle(y)
        df = pd.DataFrame({"x1": x1, "x2": x2, "target": y})
        csv_path = tmp_path / "imbalanced.csv"
        df.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"fallback-{uuid.uuid4().hex[:8]}",
                "modelType": "random_forest",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["x1", "x2"],
                "validationSplit": 0.2,
                "taskType": "classification",
            }
        )

        assert result["success"] is True
        assert "accuracy" in result["metrics"]


class TestPipelineRunOutput:
    @pytest.mark.asyncio
    async def test_includes_uploaded_model_file_id(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
        monkeypatch.setattr(
            ml_utils, "extra_csv_directories", AsyncMock(return_value=[])
        )
        dataframe = pd.DataFrame(
            {
                "feature": np.arange(20, dtype=float),
                "target": np.arange(20, dtype=float) * 2,
            }
        )
        csv_path = tmp_path / "training.csv"
        dataframe.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        pkl_file_id = str(uuid.uuid4())
        monkeypatch.setattr(
            train_node,
            "_save_model",
            AsyncMock(
                return_value={
                    "model_file_path": str(tmp_path / "model.pkl"),
                    "model_version": "v2.0",
                }
            ),
        )
        monkeypatch.setattr(
            train_node,
            "_register_trained_model",
            AsyncMock(return_value=(str(uuid.uuid4()), pkl_file_id, None, [])),
        )

        result = await train_node.process(
            {
                "name": "pipeline-model",
                "modelType": "linear_regression",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["feature"],
                "validationSplit": 0.2,
                "taskType": "regression",
            }
        )

        assert result["pkl_file_id"] == pkl_file_id


class TestCategoricalEncodingEndToEnd:
    """
    Exercises categoricalEncoding through the full process() pipeline: mixed
    strategies (one_hot, label, ordinal, no_action) trained together, plus a
    validation-only category to confirm nothing crashes when a category
    appears in the validation split but not in training.
    """

    @pytest.mark.asyncio
    async def test_mixed_strategies_train_successfully(self, tmp_path):
        rng = np.random.default_rng(3)
        n = 80
        colors = rng.choice(["red", "blue", "green", "purple"], size=n)  # one_hot
        cities = rng.choice(["NY", "LA", "SF"], size=n)  # label
        sizes = rng.choice(["small", "medium", "large"], size=n)  # ordinal
        shapes = rng.choice(["circle", "square"], size=n)  # no_action
        num = rng.normal(0, 1, n)
        y = (num + (colors == "red").astype(int) > 0).astype(int)

        df = pd.DataFrame(
            {
                "color": colors,
                "city": cities,
                "size": sizes,
                "shape": shapes,
                "num": num,
                "target": y,
            }
        )
        csv_path = tmp_path / "mixed_encoding.csv"
        df.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"encoding-{uuid.uuid4().hex[:8]}",
                "modelType": "random_forest",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["color", "city", "size", "shape", "num"],
                "validationSplit": 0.25,
                "taskType": "classification",
                "categoricalEncoding": [
                    {"columnName": "color", "strategy": "one_hot", "dropFirst": False},
                    {"columnName": "city", "strategy": "label"},
                    {
                        "columnName": "size",
                        "strategy": "ordinal",
                        "ordinalMapping": {"small": 1, "medium": 2, "large": 3},
                    },
                    {"columnName": "shape", "strategy": "no_action"},
                ],
            }
        )

        assert result["success"] is True
        assert "accuracy" in result["metrics"]
        # The output names the model file inside the data volume, not the server path (TDS-24).
        assert result["model_file_path"].startswith("ml_models/")
        assert str(DATA_VOLUME) not in result["model_file_path"]

        with open(str(DATA_VOLUME / result["model_file_path"]), "rb") as f:
            payload = pickle.load(f)
        metadata = payload["metadata"]

        # "color" (one_hot, dropFirst=False) went through the no-drop encoder.
        assert metadata["categorical_columns_no_drop"] == ["color"]
        assert metadata["encoder_no_drop"] is not None
        # "city" (label) has a fitted train-only mapping.
        assert set(metadata["label_encodings"]["city"].keys()) <= {"NY", "LA", "SF"}
        # "size" (ordinal) kept the caller-supplied mapping as-is.
        assert metadata["ordinal_encodings"]["size"] == {"small": 1, "medium": 2, "large": 3}
        # "shape" (no_action) fell through to the default drop-first encoder.
        assert "shape" in metadata["categorical_columns"]

    @pytest.mark.asyncio
    async def test_validation_only_category_does_not_crash_training(self, tmp_path):
        # Sorted by "seq" and split with splitMethod="time_based" so the
        # earliest rows (all "red") become training and the row with a
        # category unseen in training ("teal") lands in validation.
        n = 40
        colors = ["red"] * (n - 1) + ["teal"]
        rng = np.random.default_rng(11)
        num = rng.normal(0, 1, n)
        y = (num > 0).astype(int)
        df = pd.DataFrame({"seq": range(n), "color": colors, "num": num, "target": y})
        csv_path = tmp_path / "unseen_category.csv"
        df.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"encoding-unseen-{uuid.uuid4().hex[:8]}",
                "modelType": "random_forest",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["color", "num"],
                "validationSplit": 0.2,
                "splitMethod": "time_based",
                "dateColumn": "seq",
                "taskType": "classification",
                "categoricalEncoding": [
                    {"columnName": "color", "strategy": "label"},
                ],
            }
        )

        assert result["success"] is True


class TestTargetTransformEndToEnd:
    """
    Exercises targetTransform (ratio target) through the full process()
    pipeline: the model is fit on target/baseline, and validation metrics
    must be computed after reconstructing predictions back to real units -
    not on the ratio scale.
    """

    @pytest.mark.asyncio
    async def test_ratio_target_trains_and_reconstructs_real_unit_metrics(self, tmp_path):
        rng = np.random.default_rng(21)
        n = 200
        feature1 = rng.normal(0, 1, n)
        baseline = rng.uniform(50, 150, n)
        # noise_ratio is learnable from feature1, so a correct reconstruction
        # should recover a strong R2 in real units. If reconstruction were
        # missing/wrong, comparing ~1.0-scale ratio predictions against a
        # 50-150-scale real target would produce an obviously broken (very
        # negative) R2 instead.
        noise_ratio = 1.0 + 0.3 * feature1 + rng.normal(0, 0.02, n)
        target = baseline * noise_ratio

        df = pd.DataFrame({"target": target, "baseline": baseline, "feature1": feature1})
        csv_path = tmp_path / "ratio_target.csv"
        df.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"ratio-target-{uuid.uuid4().hex[:8]}",
                "modelType": "random_forest",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                # baseline is deliberately NOT a feature - only used to compute
                # the ratio, same as the user's rolling_mean_28 baseline.
                "featureColumns": ["feature1"],
                "validationSplit": 0.25,
                "taskType": "regression",
                "targetTransform": {"type": "ratio", "baselineColumn": "baseline"},
            }
        )

        assert result["success"] is True
        assert result["metrics"]["r2_score"] > 0.5

        with open(str(DATA_VOLUME / result["model_file_path"]), "rb") as f:
            payload = pickle.load(f)
        metadata = payload["metadata"]
        assert metadata["target_transform"] == {"type": "ratio", "baselineColumn": "baseline"}
        # baseline was never added to the feature matrix.
        assert "baseline" not in payload["model"].feature_names_in_

    @pytest.mark.asyncio
    async def test_zero_baseline_rows_are_dropped_not_crashed(self, tmp_path):
        rng = np.random.default_rng(5)
        n = 60
        feature1 = rng.normal(0, 1, n)
        baseline = rng.uniform(10, 20, n)
        baseline[0] = 0.0  # would make the ratio undefined
        target = baseline * (1.0 + 0.1 * feature1)

        df = pd.DataFrame({"target": target, "baseline": baseline, "feature1": feature1})
        csv_path = tmp_path / "zero_baseline.csv"
        df.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"ratio-target-zero-{uuid.uuid4().hex[:8]}",
                "modelType": "random_forest",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["feature1"],
                "validationSplit": 0.25,
                "taskType": "regression",
                "targetTransform": {"type": "ratio", "baselineColumn": "baseline"},
            }
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_rejected_for_classification_task(self, tmp_path):
        rng = np.random.default_rng(1)
        n = 40
        feature1 = rng.normal(0, 1, n)
        baseline = rng.uniform(10, 20, n)
        target = (feature1 > 0).astype(int)

        df = pd.DataFrame({"target": target, "baseline": baseline, "feature1": feature1})
        csv_path = tmp_path / "classification_ratio.csv"
        df.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        with pytest.raises(AppException):
            await train_node.process(
                {
                    "name": f"ratio-target-clf-{uuid.uuid4().hex[:8]}",
                    "modelType": "random_forest",
                    "fileUrl": str(csv_path),
                    "targetColumn": "target",
                    "featureColumns": ["feature1"],
                    "validationSplit": 0.25,
                    "taskType": "classification",
                    "targetTransform": {"type": "ratio", "baselineColumn": "baseline"},
                }
            )


class TestFullTrainingConfigurationEndToEnd:
    """
    Exercises all four Training Configuration steps together through the
    full process() pipeline: outlier handling, missing value handling,
    feature engineering, and categorical encoding.
    """

    @pytest.mark.asyncio
    async def test_all_four_steps_train_successfully(self, tmp_path):
        rng = np.random.default_rng(11)
        n = 100
        num1 = rng.normal(0, 1, n)
        num2 = rng.normal(0, 1, n)
        # Inject a few missing values and one extreme outlier into num1.
        num1[[5, 15, 25]] = np.nan
        num1[0] = 1000.0
        color = rng.choice(["red", "blue", "green"], size=n)
        y = (num2 + (color == "red").astype(int) > 0).astype(int)

        df = pd.DataFrame(
            {"num1": num1, "num2": num2, "color": color, "target": y}
        )
        csv_path = tmp_path / "full_training_config.csv"
        df.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"full-config-{uuid.uuid4().hex[:8]}",
                "modelType": "random_forest",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["num1", "num2", "color"],
                "validationSplit": 0.25,
                "taskType": "classification",
                "outlierHandling": [
                    {"columnName": "num1", "strategy": "cap_outliers", "method": "iqr"},
                ],
                "missingValueHandling": [
                    {"columnName": "num1", "strategy": "impute_median"},
                ],
                "featureEngineering": [
                    {
                        "newColumnName": "num_sum",
                        "strategy": "custom_expression",
                        "expression": "num1 + num2",
                    },
                ],
                "categoricalEncoding": [
                    {"columnName": "color", "strategy": "one_hot", "dropFirst": True},
                ],
            }
        )

        assert result["success"] is True
        assert "accuracy" in result["metrics"]


class TestEncodeCategoricals:
    def test_no_action_leaves_column_untouched(self, node):
        X_train = pd.DataFrame({"color": ["red", "blue", "red"]})
        X_val = pd.DataFrame({"color": ["blue", "green"]})
        X_train, X_val, labels, ordinals, no_drop = node._encode_categoricals(
            X_train, X_val, [{"columnName": "color", "strategy": "no_action"}]
        )
        assert X_train["color"].tolist() == ["red", "blue", "red"]
        assert X_val["color"].tolist() == ["blue", "green"]
        assert labels == {}
        assert ordinals == {}
        assert no_drop == set()

    def test_label_fits_codes_on_train_only_and_maps_unseen_val_to_negative_one(self, node):
        X_train = pd.DataFrame({"color": ["red", "blue", "red"]})
        X_val = pd.DataFrame({"color": ["blue", "green"]})  # "green" unseen in train
        X_train, X_val, labels, ordinals, no_drop = node._encode_categoricals(
            X_train, X_val, [{"columnName": "color", "strategy": "label"}]
        )
        mapping = labels["color"]
        assert X_train["color"].tolist() == [mapping["red"], mapping["blue"], mapping["red"]]
        assert X_val["color"].tolist() == [mapping["blue"], -1]
        assert ordinals == {}
        assert no_drop == set()

    def test_ordinal_applies_fixed_mapping_to_both_splits(self, node):
        X_train = pd.DataFrame({"size": ["small", "large"]})
        X_val = pd.DataFrame({"size": ["large", "small"]})
        mapping = {"small": 1, "large": 3}
        X_train, X_val, labels, ordinals, no_drop = node._encode_categoricals(
            X_train,
            X_val,
            [{"columnName": "size", "strategy": "ordinal", "ordinalMapping": mapping}],
        )
        assert X_train["size"].tolist() == [1, 3]
        assert X_val["size"].tolist() == [3, 1]
        assert ordinals == {"size": mapping}
        assert labels == {}
        assert no_drop == set()

    def test_one_hot_is_left_untouched_here_and_tracked_by_drop_first(self, node):
        X_train = pd.DataFrame({"a": ["x", "y"], "b": ["x", "y"]})
        X_val = pd.DataFrame({"a": ["x", "y"], "b": ["x", "y"]})
        X_train, X_val, labels, ordinals, no_drop = node._encode_categoricals(
            X_train,
            X_val,
            [
                {"columnName": "a", "strategy": "one_hot", "dropFirst": True},
                {"columnName": "b", "strategy": "one_hot", "dropFirst": False},
            ],
        )
        # Still raw, untouched object columns - the one-hot pass runs separately.
        assert X_train["a"].tolist() == ["x", "y"]
        assert X_train["b"].tolist() == ["x", "y"]
        assert no_drop == {"b"}
        assert labels == {} and ordinals == {}


class TestFitOneHot:
    def test_drop_first_removes_one_category_per_column(self, node):
        X_train = pd.DataFrame({"color": ["red", "blue", "green"]})
        X_val = pd.DataFrame({"color": ["blue", "red"]})
        X_train, X_val, encoder = node._fit_one_hot(X_train, X_val, ["color"], drop="first")
        assert len(encoder.get_feature_names_out(["color"])) == 2
        assert X_train.shape[1] == 2
        assert X_val.shape[1] == 2

    def test_no_drop_keeps_every_category(self, node):
        X_train = pd.DataFrame({"color": ["red", "blue", "green"]})
        X_train, X_val, encoder = node._fit_one_hot(X_train, None, ["color"], drop=None)
        assert len(encoder.get_feature_names_out(["color"])) == 3
        assert X_val is None

    def test_unseen_validation_category_encodes_to_all_zeros(self, node):
        X_train = pd.DataFrame({"color": ["red", "blue"]})
        X_val = pd.DataFrame({"color": ["purple"]})
        X_train, X_val, encoder = node._fit_one_hot(X_train, X_val, ["color"], drop=None)
        encoded_columns = encoder.get_feature_names_out(["color"]).tolist()
        assert X_val.loc[0, encoded_columns].tolist() == [0.0, 0.0]


class TestHandleMissingValues:
    def test_no_action_leaves_column_untouched(self, node):
        X_train = pd.DataFrame({"a": [1.0, None, 3.0]})
        y_train = pd.Series([0, 1, 0])
        X_train_out, y_train_out, X_val_out, y_val_out, _, _, fills = node._handle_missing_values(
            X_train, y_train, None, None, [{"columnName": "a", "strategy": "no_action"}]
        )
        assert X_train_out["a"].isna().sum() == 1
        assert fills == {}

    def test_drop_column_removes_column_from_both_splits(self, node):
        X_train = pd.DataFrame({"a": [1.0, None], "b": [1, 2]})
        X_val = pd.DataFrame({"a": [None], "b": [3]})
        X_train_out, _, X_val_out, _, _, _, fills = node._handle_missing_values(
            X_train, pd.Series([0, 1]), X_val, pd.Series([0]),
            [{"columnName": "a", "strategy": "drop_column"}],
        )
        assert "a" not in X_train_out.columns
        assert "a" not in X_val_out.columns
        assert fills == {}

    def test_drop_rows_removes_rows_with_missing_value_from_both_splits(self, node):
        X_train = pd.DataFrame({"a": [1.0, None, 3.0]})
        y_train = pd.Series([10, 20, 30])
        X_val = pd.DataFrame({"a": [None, 5.0]})
        y_val = pd.Series([40, 50])
        X_train_out, y_train_out, X_val_out, y_val_out, _, _, fills = node._handle_missing_values(
            X_train, y_train, X_val, y_val,
            [{"columnName": "a", "strategy": "drop_rows"}],
        )
        assert X_train_out["a"].tolist() == [1.0, 3.0]
        assert y_train_out.tolist() == [10, 30]
        assert X_val_out["a"].tolist() == [5.0]
        assert y_val_out.tolist() == [50]
        assert fills == {}

    def test_impute_constant_uses_given_value(self, node):
        X_train = pd.DataFrame({"a": [1.0, None]})
        X_val = pd.DataFrame({"a": [None]})
        X_train_out, _, X_val_out, _, _, _, fills = node._handle_missing_values(
            X_train, pd.Series([0, 1]), X_val, pd.Series([0]),
            [{"columnName": "a", "strategy": "impute_constant", "imputeValue": -1}],
        )
        assert X_train_out["a"].tolist() == [1.0, -1]
        assert X_val_out["a"].tolist() == [-1]
        assert fills == {"a": -1}

    def test_impute_mean_fits_on_train_only(self, node):
        X_train = pd.DataFrame({"a": [1.0, 3.0, None]})  # mean of [1, 3] = 2.0
        X_val = pd.DataFrame({"a": [None, 100.0]})  # 100 must not affect train's fill value
        X_train_out, _, X_val_out, _, _, _, fills = node._handle_missing_values(
            X_train, pd.Series([0, 1, 2]), X_val, pd.Series([0, 1]),
            [{"columnName": "a", "strategy": "impute_mean"}],
        )
        assert X_train_out["a"].tolist() == [1.0, 3.0, 2.0]
        assert X_val_out["a"].tolist() == [2.0, 100.0]
        assert fills == {"a": 2.0}


class TestEngineerFeatures:
    def test_custom_expression_applies_to_both_splits(self, node):
        X_train = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        X_val = pd.DataFrame({"a": [5], "b": [6]})
        X_train_out, X_val_out, steps = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "sum", "strategy": "custom_expression", "expression": "a + b"}],
        )
        assert X_train_out["sum"].tolist() == [4, 6]
        assert X_val_out["sum"].tolist() == [11]
        assert steps == [{"strategy": "custom_expression", "new_col": "sum", "expression": "a + b"}]

    def test_bin_numeric_fits_edges_on_train_and_clips_val(self, node):
        X_train = pd.DataFrame({"a": [0.0, 10.0]})
        X_val = pd.DataFrame({"a": [999.0]})  # far outside train's range
        X_train_out, X_val_out, steps = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "a_bin", "strategy": "bin_numeric", "binColumn": "a", "numBins": 2}],
        )
        assert X_train_out["a_bin"].notna().all()
        # Clipped into train's range instead of becoming NaN.
        assert X_val_out["a_bin"].notna().all()
        assert len(steps) == 1
        assert steps[0]["strategy"] == "bin_numeric"
        assert steps[0]["new_col"] == "a_bin"
        assert steps[0]["bin_column"] == "a"
        assert steps[0]["bin_edges"][0] <= 0.0 and steps[0]["bin_edges"][-1] >= 10.0
        assert steps[0]["bin_strategy"] == "uniform"

    def test_bin_numeric_quantile_gives_equal_frequency_bins_on_skewed_data(self, node):
        # Skewed: uniform bins would put 9 of 10 rows in bin 0.
        X_train = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 1000.0]})
        X_val = pd.DataFrame({"a": [-50.0, 5000.0]})
        X_train_out, X_val_out, steps = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "a_bin", "strategy": "bin_numeric", "binColumn": "a",
              "numBins": 5, "binStrategy": "quantile"}],
        )
        assert X_train_out["a_bin"].value_counts().tolist() == [2, 2, 2, 2, 2]
        # Out-of-range val values clip into the first/last bin.
        assert X_val_out["a_bin"].tolist() == [0, 4]
        assert steps[0]["bin_strategy"] == "quantile"
        assert len(steps[0]["bin_edges"]) == 6

    def test_bin_numeric_quantile_drops_duplicate_edges(self, node):
        X_train = pd.DataFrame({"a": [0.0] * 8 + [5.0, 10.0]})
        X_train_out, _, steps = node._engineer_features(
            X_train, None,
            [{"newColumnName": "a_bin", "strategy": "bin_numeric", "binColumn": "a",
              "numBins": 5, "binStrategy": "quantile"}],
        )
        assert X_train_out["a_bin"].notna().all()
        assert len(steps[0]["bin_edges"]) < 6

    def test_bin_numeric_quantile_replays_identically_at_inference(self, node):
        from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import (
            _replay_feature_engineering,
        )
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 1000.0]
        X_train_out, _, steps = node._engineer_features(
            pd.DataFrame({"a": values}), None,
            [{"newColumnName": "a_bin", "strategy": "bin_numeric", "binColumn": "a",
              "numBins": 5, "binStrategy": "quantile"}],
        )
        replayed = _replay_feature_engineering({"a": values}, steps, len(values))
        assert replayed["a_bin"].tolist() == X_train_out["a_bin"].tolist()

    def test_normalize_fits_min_max_on_train_only(self, node):
        X_train = pd.DataFrame({"a": [0.0, 10.0]})  # min=0, max=10
        X_val = pd.DataFrame({"a": [100.0]})
        X_train_out, X_val_out, steps = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "a_norm", "strategy": "normalize", "sourceColumns": ["a"]}],
        )
        assert X_train_out["a_norm"].tolist() == [0.0, 1.0]
        # (100 - 0) / (10 - 0) = 10.0 - proves min/max came from train, not val.
        assert X_val_out["a_norm"].tolist() == [10.0]
        assert steps == [{
            "strategy": "normalize",
            "new_col": "a_norm",
            "column_stats": {"a": {"out_col": "a_norm", "min": 0.0, "max": 10.0}},
        }]

    def test_standardize_fits_mean_std_on_train_only(self, node):
        X_train = pd.DataFrame({"a": [1.0, 3.0]})  # mean=2, std=sqrt(2)
        X_val = pd.DataFrame({"a": [2.0]})
        X_train_out, X_val_out, steps = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "a_std", "strategy": "standardize", "sourceColumns": ["a"]}],
        )
        assert X_val_out["a_std"].iloc[0] == pytest.approx(0.0)
        assert steps[0]["strategy"] == "standardize"
        assert steps[0]["column_stats"]["a"]["mean"] == pytest.approx(2.0)

    def test_polynomial_adds_degree_features_to_both_splits(self, node):
        X_train = pd.DataFrame({"a": [1.0, 2.0]})
        X_val = pd.DataFrame({"a": [3.0]})
        X_train_out, X_val_out, steps = node._engineer_features(
            X_train, X_val,
            [{
                "newColumnName": "a_poly",
                "strategy": "polynomial",
                "polynomialColumns": ["a"],
                "polynomialDegree": 2,
            }],
        )
        assert "a_poly_a^2" in X_train_out.columns
        assert steps[0]["strategy"] == "polynomial"
        assert steps[0]["poly_columns"] == ["a"]
        assert steps[0]["new_names"] == ["a_poly_a^2"]
        assert hasattr(steps[0]["poly"], "transform")
        assert X_train_out["a_poly_a^2"].tolist() == [1.0, 4.0]
        assert X_val_out["a_poly_a^2"].tolist() == [9.0]


class TestFitScaler:
    @pytest.mark.parametrize(
        "method,expected_class",
        [
            ("standard", "StandardScaler"),
            ("minmax", "MinMaxScaler"),
            ("maxabs", "MaxAbsScaler"),
            ("robust", "RobustScaler"),
        ],
    )
    def test_returns_expected_scaler_type(self, node, method, expected_class):
        assert type(node._fit_scaler(method)).__name__ == expected_class


class TestTextClassLabels:
    """
    TM-10: XGBoost rejected text classes ("Invalid classes inferred") and the
    Neural Network failed in early stopping ("ufunc 'isnan' not supported").
    Every classifier now trains on class codes and saves the labels.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_type", ["xgboost", "neural_network", "random_forest"])
    @pytest.mark.parametrize("labels", [["A", "B", "C"], ["high", "low"]])
    async def test_text_classes_train_and_save_their_labels(self, tmp_path, model_type, labels):
        rng = np.random.default_rng(3)
        n = 90
        target = np.array([labels[i % len(labels)] for i in range(n)])
        df = pd.DataFrame(
            {
                "x1": rng.normal(size=n) + np.array([labels.index(t) for t in target]),
                "x2": rng.normal(size=n),
                "target": target,
            }
        )
        csv_path = tmp_path / "text_classes.csv"
        df.to_csv(csv_path, index=False)

        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"text-classes-{uuid.uuid4().hex[:8]}",
                "modelType": model_type,
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["x1", "x2"],
            }
        )

        assert result["success"] is True
        assert result["target_classes"] == sorted(labels)
        with open(str(DATA_VOLUME / result["model_file_path"]), "rb") as f:
            payload = pickle.load(f)
        assert payload["metadata"]["target_classes"] == sorted(labels)
        predictions = payload["model"].predict(
            pd.DataFrame({"x1": [0.0], "x2": [0.0]})[payload["metadata"]["model_input_columns"]]
        )
        assert int(predictions[0]) in range(len(labels))


class TestClassCodesFollowTheTrainingSplit:
    @pytest.mark.asyncio
    async def test_xgboost_trains_when_a_middle_class_is_only_in_validation(self, tmp_path):
        # Codes are taken from the training rows: with 'low' (the middle label
        # alphabetically) only in the latest rows, the training codes must
        # still be 0..n-1 or XGBoost raises "Invalid classes inferred".
        n = 50
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=n, freq="D").astype(str),
                "x1": np.arange(n, dtype=float),
                "target": ["high", "medium"] * 20 + ["low"] * 10,
            }
        )
        csv_path = tmp_path / "late_class.csv"
        df.to_csv(csv_path, index=False)
        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"late-class-{uuid.uuid4().hex[:8]}",
                "modelType": "xgboost",
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["x1"],
                "splitMethod": "time_based",
                "dateColumn": "date",
                "validationSplit": 0.2,
            }
        )

        assert result["success"] is True
        assert result["target_classes"] == ["high", "medium"]


class TestValidationOnlyClass:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_type", ["xgboost", "lightgbm", "random_forest"])
    async def test_rows_of_a_class_missing_from_training_are_left_out_of_validation(
        self, tmp_path, model_type
    ):
        pytest.importorskip(model_type) if model_type in ("xgboost", "lightgbm") else None
        n = 60
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=n, freq="D").astype(str),
                "x1": np.arange(n, dtype=float),
                "target": ["a", "b", "c"] * 16 + ["d"] * 12,
            }
        )
        csv_path = tmp_path / "new_class.csv"
        df.to_csv(csv_path, index=False)
        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"new-class-{uuid.uuid4().hex[:8]}",
                "modelType": model_type,
                "fileUrl": str(csv_path),
                "targetColumn": "target",
                "featureColumns": ["x1"],
                "splitMethod": "time_based",
                "dateColumn": "date",
                "validationSplit": 0.3,
            }
        )

        assert result["success"] is True
        assert result["target_classes"] == ["a", "b", "c"]
        assert any("left out of the validation metrics" in w for w in result["warnings"])
        assert result["validation_samples"] == 6


class TestPlainTrainingErrors:
    """TM-14: bad data or settings are reported in the node's own terms."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"targetColumn": "label", "taskType": "regression"}, "has text values"),
            ({"featureColumns": ["x1", "num"]}, "also selected as a feature column"),
            ({"validationSplit": 5}, "Validation Split must be a fraction"),
            ({"modelParameters": {"foo": 1}}, "'foo' is not a setting of Random Forest"),
            ({"modelType": "xgboost", "modelParameters": {"max_depth": "abc"}}, "'max_depth' must be a whole number"),
            (
                {"hyperparameterOptimization": "random_search", "optimizationConfig": {"scoring": "accuracy", "nIter": 2}},
                "is a classification metric",
            ),
        ],
    )
    async def test_message_names_the_setting(self, tmp_path, overrides, expected):
        rng = np.random.default_rng(5)
        n = 40
        df = pd.DataFrame(
            {
                "x1": rng.normal(size=n),
                "num": rng.normal(size=n) * 10,
                "label": rng.choice(["p", "q"], n),
            }
        )
        csv_path = tmp_path / "data.csv"
        df.to_csv(csv_path, index=False)
        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        config = {
            "name": f"plain-{uuid.uuid4().hex[:8]}",
            "modelType": "random_forest",
            "fileUrl": str(csv_path),
            "targetColumn": "num",
            "featureColumns": ["x1"],
            **overrides,
        }

        with pytest.raises(AppException) as exc:
            await train_node.process(config)

        assert expected in exc.value.error_detail
        assert "np.float64" not in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_auto_fill_warning_shows_plain_number(self, tmp_path):
        df = pd.DataFrame({"x1": [1.0, None, 49.0, 49.0, 97.0] * 6, "num": list(range(30))})
        csv_path = tmp_path / "fill.csv"
        df.to_csv(csv_path, index=False)
        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        result = await train_node.process(
            {
                "name": f"fill-{uuid.uuid4().hex[:8]}",
                "modelType": "random_forest",
                "fileUrl": str(csv_path),
                "targetColumn": "num",
                "featureColumns": ["x1"],
                "validationSplit": 0,
            }
        )

        fill_warning = next(w for w in result["warnings"] if "filled automatically" in w)
        assert "median (49)" in fill_warning



class TestTargetTypeEdgeCases:
    @staticmethod
    async def _train(tmp_path, model_type, task_type, y):
        df = pd.DataFrame({"x1": np.arange(30, dtype=float), "y": y})
        csv_path = tmp_path / f"{model_type}.csv"
        df.to_csv(csv_path, index=False)
        train_node = TrainModelNode(
            node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
        )
        return await train_node.process(
            {
                "name": f"{model_type}-{uuid.uuid4().hex[:8]}",
                "modelType": model_type,
                "fileUrl": str(csv_path),
                "targetColumn": "y",
                "featureColumns": ["x1"],
                "taskType": task_type,
            }
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "model_type", ["linear_regression", "ridge_regression", "lasso_regression", "elastic_net"]
    )
    async def test_regression_only_model_rejects_classification(self, tmp_path, model_type):
        # Numbers stored as text: with Classification they used to stay text and
        # fail as "has text values (e.g. )" while the model trained as regression.
        with pytest.raises(AppException) as exc:
            await self._train(tmp_path, model_type, "classification", ["1", "2", "3"] * 10)
        assert "incompatible" in exc.value.error_detail
        assert f"'{model_type}'" in exc.value.error_detail
        assert "only supports regression" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_logistic_regression_rejects_regression(self, tmp_path):
        with pytest.raises(AppException) as exc:
            await self._train(tmp_path, "logistic_regression", "regression", [0, 1] * 15)
        assert "only supports classification" in exc.value.error_detail

    @pytest.mark.asyncio
    async def test_ridge_reads_numbers_stored_as_text(self, tmp_path):
        result = await self._train(tmp_path, "ridge_regression", "auto", ["1", "2", "3"] * 10)
        assert "target_classes" not in result
        assert "r2_score" in result["metrics"]


def _dropped_rows_frame(n: int = 200) -> pd.DataFrame:
    """
    Hourly rows for a time-based 75/25 split (rows 0-149 train, 150-199
    validate). x is uniform in [-1, 1], so it has no IQR outliers of its own;
    tests plant them at known rows. baseline is a clean 50-150 ratio baseline.
    """
    rng = np.random.default_rng(11)
    x = rng.uniform(-1, 1, n)
    baseline = rng.uniform(50, 150, n)
    target = baseline * (1.0 + 0.3 * x) + rng.normal(0, 0.5, n)
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=n, freq="h").astype(str),
            "x": x,
            "baseline": baseline,
            "target": target,
        }
    )


def _plant_outliers(df: pd.DataFrame) -> pd.DataFrame:
    df.loc[[10, 40, 90, 120], "x"] = [9.0, -9.0, 12.0, -12.0]  # 4 training rows
    df.loc[[160, 175, 190], "x"] = [10.0, -11.0, 14.0]  # 3 validation rows
    return df


def _plant_bad_baselines(df: pd.DataFrame) -> pd.DataFrame:
    baseline = df["baseline"].astype(object)
    baseline[[1, 2, 3]] = 0.0  # training: zero x3
    baseline[[4, 5]] = np.nan  # training: missing x2
    baseline[6] = "abc"  # training: not a number
    baseline[[7, 8]] = [np.inf, -np.inf]  # training: infinite x2
    baseline[155] = 0.0  # validation: zero
    baseline[156] = np.nan  # validation: missing
    baseline[[157, 158]] = ["abc", "abc"]  # validation: not a number x2
    baseline[159] = np.inf  # validation: infinite
    df["baseline"] = baseline
    return df


async def _train_dropped_rows(tmp_path, df: pd.DataFrame, **extra):
    csv_path = tmp_path / f"dropped_rows_{uuid.uuid4().hex[:8]}.csv"
    df.to_csv(csv_path, index=False)
    train_node = TrainModelNode(
        node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={})
    )
    return await train_node.process(
        {
            "name": f"dropped-rows-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": str(csv_path),
            "targetColumn": "target",
            "featureColumns": ["x"],
            "validationSplit": 0.25,
            "splitMethod": "time_based",
            "dateColumn": "date",
            "taskType": "regression",
            **extra,
        }
    )


_REMOVE_X_OUTLIERS = [{"columnName": "x", "strategy": "remove_outliers", "method": "iqr"}]
_RATIO_ON_BASELINE = {"type": "ratio", "baselineColumn": "baseline"}
_OUTLIER_WARNING = "Removed 4 training rows with outliers in 'x' (iqr)"
_BASELINE_WARNING = (
    "Dropped 8 training and 5 validation rows whose 'baseline' baseline is zero (4), "
    "missing (3), not a number (3) or infinite (3); a ratio target can't be computed there. "
    "Rows, numbered from 1 in the data Train Model received: zero 2, 3, 4, 156; missing 5, 6, 157; "
    "not a number 7, 158, 159; infinite 8, 9, 160."
)


class TestRowsDroppedWarning:
    def test_lists_each_split_with_rows(self):
        assert (
            _rows_dropped_warning("Dropped", {"training": 18, "validation": 4}, "for a reason.")
            == "Dropped 18 training and 4 validation rows for a reason."
        )

    def test_leaves_out_empty_splits_and_uses_singular_for_one_row(self):
        assert (
            _rows_dropped_warning("Removed", {"training": 1, "validation": 0}, "with outliers in 'x' (iqr)")
            == "Removed 1 training row with outliers in 'x' (iqr)"
        )

    def test_joins_reason_counts_and_skips_zero_counts(self):
        assert _join_reason_counts({"zero": 12, "missing": 0, "not a number": 3}) == "zero (12) or not a number (3)"
        assert _join_reason_counts({"zero": 2}) == "zero (2)"
        assert _join_reason_counts({"zero": 0}) == ""
        assert (
            _join_reason_counts({"zero": 12, "missing": 7, "not a number": 3})
            == "zero (12), missing (7) or not a number (3)"
        )

    def test_names_rows_smallest_first_and_skips_reasons_without_rows(self):
        assert (
            _name_rows_by_reason(
                {"zero": [9, 2], "missing": [], "infinite": [4]}, {"zero": 2, "missing": 0, "infinite": 1}
            )
            == "zero 2, 9; infinite 4"
        )

    def test_names_at_most_ten_rows_per_reason_and_counts_the_rest(self):
        assert _name_rows_by_reason(
            {"zero": list(range(25, 0, -1)), "missing": [30]}, {"zero": 25, "missing": 1}
        ) == ("zero 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 …and 15 more; missing 30")


class TestRemoveOutliersKeepsValidationRows:
    """TM-12: Remove drops outlier rows from training only."""

    def test_handle_outliers_leaves_validation_untouched(self, node):
        X_train = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 100.0]})
        y_train = pd.Series([1, 2, 3, 4, 5])
        X_val = pd.DataFrame({"x": [2.0, 500.0, -500.0]})
        y_val = pd.Series([6, 7, 8])

        X_train, y_train, X_val_out, y_val_out, _, _, warnings = node._handle_outliers(
            X_train, y_train, X_val, y_val,
            [{"columnName": "x", "strategy": "remove_outliers", "method": "iqr"}],
        )

        assert X_train["x"].tolist() == [1.0, 2.0, 3.0, 4.0]
        assert y_train.tolist() == [1, 2, 3, 4]
        assert X_val_out["x"].tolist() == [2.0, 500.0, -500.0]
        assert y_val_out.tolist() == [6, 7, 8]
        assert warnings == ["Removed 1 training row with outliers in 'x' (iqr)"]

    def test_empty_values_are_reported_apart_from_outliers(self, node):
        X_train = pd.DataFrame({"x": [1.0, 2.0, np.nan, 3.0, 4.0, np.nan]})
        X_val = pd.DataFrame({"x": [np.nan, 2.0]})

        X_train, _, X_val_out, _, _, _, warnings = node._handle_outliers(
            X_train, pd.Series(range(6)), X_val, pd.Series([6, 7]),
            [{"columnName": "x", "strategy": "remove_outliers", "method": "iqr"}],
        )

        assert X_train["x"].tolist() == [1.0, 2.0, 3.0, 4.0]
        assert len(X_val_out) == 2
        assert warnings == [
            "Removed 2 training rows with an empty 'x'; Remove outliers can't check them against the bounds"
        ]

    def test_cap_outliers_still_clips_validation_without_a_warning(self, node):
        X_train = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 100.0]})
        X_val = pd.DataFrame({"x": [500.0]})

        _, _, X_val_out, _, _, _, warnings = node._handle_outliers(
            X_train, pd.Series([1, 2, 3, 4, 5]), X_val, pd.Series([6]),
            [{"columnName": "x", "strategy": "cap_outliers", "method": "iqr"}],
        )

        assert X_val_out["x"].iloc[0] < 500.0
        assert warnings == []

    @pytest.mark.asyncio
    async def test_metrics_are_scored_on_every_validation_row(self, tmp_path):
        result = await _train_dropped_rows(
            tmp_path, _plant_outliers(_dropped_rows_frame()), outlierHandling=_REMOVE_X_OUTLIERS
        )

        assert result["training_samples"] == 146
        assert result["validation_samples"] == 50
        assert result["warnings"] == [_OUTLIER_WARNING]


class TestRatioTargetBadBaselines:
    """TM-13: every unusable ratio baseline is dropped and reported."""

    def test_check_ratio_baseline_classifies_each_reason(self, node):
        values = pd.Series(
            [10.0, 0.0, np.nan, "abc", np.inf, -np.inf, "12.5", "  ", True, False], dtype=object
        )
        baseline = pd.DataFrame({"value": values, "row": range(101, 111)})

        numeric, keep, reasons, rows = node._check_ratio_baseline(baseline)

        assert keep.tolist() == [True, False, False, False, False, False, True, False, False, False]
        assert numeric[keep].tolist() == [10.0, 12.5]
        # Blank text counts as missing and true/false as not a number, the
        # same as the inference node's baseline check.
        assert reasons == {"zero": 1, "missing": 2, "not a number": 3, "infinite": 2}
        assert rows == {"zero": [102], "missing": [103, 108], "not a number": [104, 109, 110], "infinite": [105, 106]}

    @pytest.mark.asyncio
    async def test_bad_baselines_are_dropped_from_both_splits_with_counts(self, tmp_path):
        result = await _train_dropped_rows(
            tmp_path, _plant_bad_baselines(_dropped_rows_frame()), targetTransform=_RATIO_ON_BASELINE
        )

        assert result["success"] is True
        assert result["training_samples"] == 150 - 8
        assert result["validation_samples"] == 50 - 5
        assert result["warnings"] == [_BASELINE_WARNING]

    @pytest.mark.asyncio
    async def test_named_rows_are_the_file_rows_when_the_time_split_reorders_them(self, tmp_path):
        # Newest first in the file: the time-based sort reverses it, but the
        # warning still names rows as they are numbered in the file.
        df = _plant_bad_baselines(_dropped_rows_frame()).iloc[::-1].reset_index(drop=True)

        result = await _train_dropped_rows(tmp_path, df, targetTransform=_RATIO_ON_BASELINE)

        assert result["training_samples"] == 150 - 8
        assert result["validation_samples"] == 50 - 5
        assert result["warnings"][0].endswith(
            "Rows, numbered from 1 in the data Train Model received: zero 45, 197, 198, 199; missing 44, 195, 196; "
            "not a number 42, 43, 194; infinite 41, 192, 193."
        )

    @pytest.mark.asyncio
    async def test_random_split_names_rows_from_both_splits(self, tmp_path):
        df = _dropped_rows_frame()
        df["baseline"] = df["baseline"].astype(object)
        df.loc[[3, 50, 120, 180], "baseline"] = 0.0

        result = await _train_dropped_rows(
            tmp_path, df, splitMethod="random", targetTransform=_RATIO_ON_BASELINE
        )

        assert result["success"] is True
        assert result["training_samples"] + result["validation_samples"] == 200 - 4
        assert result["warnings"][0].endswith(
            "Rows, numbered from 1 in the data Train Model received: zero 4, 51, 121, 181."
        )

    @pytest.mark.asyncio
    async def test_more_than_ten_bad_rows_per_reason_are_cut_short(self, tmp_path):
        df = _dropped_rows_frame()
        df.loc[0:13, "baseline"] = 0.0

        result = await _train_dropped_rows(tmp_path, df, targetTransform=_RATIO_ON_BASELINE)

        assert result["training_samples"] == 150 - 14
        assert result["warnings"] == [
            "Dropped 14 training rows whose 'baseline' baseline is zero (14); a ratio target can't be "
            "computed there. Rows, numbered from 1 in the data Train Model received: "
            "zero 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 …and 4 more."
        ]

    @pytest.mark.asyncio
    async def test_cut_off_counts_rows_from_both_splits(self, tmp_path):
        df = _dropped_rows_frame()
        df.loc[list(range(0, 8)) + list(range(150, 155)), "baseline"] = 0.0

        result = await _train_dropped_rows(tmp_path, df, targetTransform=_RATIO_ON_BASELINE)

        assert result["warnings"][0].endswith(
            "Rows, numbered from 1 in the data Train Model received: zero 1, 2, 3, 4, 5, 6, 7, 8, 151, 152 "
            "…and 3 more."
        )

    @pytest.mark.asyncio
    async def test_named_rows_survive_outlier_removal_renumbering(self, tmp_path):
        # Removing the outlier at row 11 renumbers the training rows after
        # it; the bad baseline at row 21 must still be named as row 21.
        df = _dropped_rows_frame()
        df.loc[10, "x"] = 9.0
        df["baseline"] = df["baseline"].astype(object)
        df.loc[20, "baseline"] = 0.0

        result = await _train_dropped_rows(
            tmp_path, df, outlierHandling=_REMOVE_X_OUTLIERS, targetTransform=_RATIO_ON_BASELINE
        )

        assert result["training_samples"] == 150 - 1 - 1
        assert result["warnings"][-1].endswith("Rows, numbered from 1 in the data Train Model received: zero 21.")

    @pytest.mark.asyncio
    async def test_named_rows_without_a_validation_split(self, tmp_path):
        df = _dropped_rows_frame()
        df["baseline"] = df["baseline"].astype(object)
        df.loc[[5, 180], "baseline"] = 0.0

        result = await _train_dropped_rows(tmp_path, df, validationSplit=0, targetTransform=_RATIO_ON_BASELINE)

        assert result["training_samples"] == 200 - 2
        assert result["warnings"] == [
            "Dropped 2 training rows whose 'baseline' baseline is zero (2); a ratio target can't be "
            "computed there. Rows, numbered from 1 in the data Train Model received: zero 6, 181."
        ]

    @pytest.mark.asyncio
    async def test_every_training_baseline_bad_fails_with_a_clear_error(self, tmp_path):
        df = _dropped_rows_frame()
        df["baseline"] = 0.0

        with pytest.raises(AppException) as exc_info:
            await _train_dropped_rows(tmp_path, df, targetTransform=_RATIO_ON_BASELINE)

        assert "Every training row has a zero, missing, non-numeric or infinite 'baseline' baseline" in (
            exc_info.value.error_detail
        )

    @pytest.mark.asyncio
    async def test_every_validation_baseline_bad_fails_with_a_clear_error(self, tmp_path):
        df = _dropped_rows_frame()
        df.loc[150:, "baseline"] = 0.0

        with pytest.raises(AppException) as exc_info:
            await _train_dropped_rows(tmp_path, df, targetTransform=_RATIO_ON_BASELINE)

        assert "Every validation row has a zero, missing, non-numeric or infinite 'baseline' baseline" in (
            exc_info.value.error_detail
        )


class TestDroppedRowWarningsTogether:
    @pytest.mark.asyncio
    async def test_outlier_removal_and_bad_baselines_both_report(self, tmp_path):
        df = _plant_bad_baselines(_plant_outliers(_dropped_rows_frame()))

        result = await _train_dropped_rows(
            tmp_path, df, outlierHandling=_REMOVE_X_OUTLIERS, targetTransform=_RATIO_ON_BASELINE
        )

        # Outliers (rows 10/40/90/120) and bad baselines (rows 1-8) don't
        # overlap; validation loses only its 5 bad-baseline rows.
        assert result["training_samples"] == 150 - 4 - 8
        assert result["validation_samples"] == 50 - 5
        assert result["warnings"] == [_OUTLIER_WARNING, _BASELINE_WARNING]

    @pytest.mark.asyncio
    async def test_clean_data_adds_no_warnings(self, tmp_path):
        result = await _train_dropped_rows(
            tmp_path,
            _dropped_rows_frame(),
            outlierHandling=_REMOVE_X_OUTLIERS,
            targetTransform=_RATIO_ON_BASELINE,
        )

        assert result["training_samples"] == 150
        assert result["validation_samples"] == 50
        assert "warnings" not in result
