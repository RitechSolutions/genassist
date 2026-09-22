import pickle
import uuid

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml.train_model_node import (
    TREE_BASED_MODEL_TYPES,
    TrainModelNode,
)
from app.modules.workflow.engine.workflow_state import WorkflowState


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

        with open(result["model_file_path"], "rb") as f:
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

        with open(result["model_file_path"], "rb") as f:
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
        X_train_out, y_train_out, X_val_out, y_val_out, _, _ = node._handle_missing_values(
            X_train, y_train, None, None, [{"columnName": "a", "strategy": "no_action"}]
        )
        assert X_train_out["a"].isna().sum() == 1

    def test_drop_column_removes_column_from_both_splits(self, node):
        X_train = pd.DataFrame({"a": [1.0, None], "b": [1, 2]})
        X_val = pd.DataFrame({"a": [None], "b": [3]})
        X_train_out, _, X_val_out, _, _, _ = node._handle_missing_values(
            X_train, pd.Series([0, 1]), X_val, pd.Series([0]),
            [{"columnName": "a", "strategy": "drop_column"}],
        )
        assert "a" not in X_train_out.columns
        assert "a" not in X_val_out.columns

    def test_drop_rows_removes_rows_with_missing_value_from_both_splits(self, node):
        X_train = pd.DataFrame({"a": [1.0, None, 3.0]})
        y_train = pd.Series([10, 20, 30])
        X_val = pd.DataFrame({"a": [None, 5.0]})
        y_val = pd.Series([40, 50])
        X_train_out, y_train_out, X_val_out, y_val_out, _, _ = node._handle_missing_values(
            X_train, y_train, X_val, y_val,
            [{"columnName": "a", "strategy": "drop_rows"}],
        )
        assert X_train_out["a"].tolist() == [1.0, 3.0]
        assert y_train_out.tolist() == [10, 30]
        assert X_val_out["a"].tolist() == [5.0]
        assert y_val_out.tolist() == [50]

    def test_impute_constant_uses_given_value(self, node):
        X_train = pd.DataFrame({"a": [1.0, None]})
        X_val = pd.DataFrame({"a": [None]})
        X_train_out, _, X_val_out, _, _, _ = node._handle_missing_values(
            X_train, pd.Series([0, 1]), X_val, pd.Series([0]),
            [{"columnName": "a", "strategy": "impute_constant", "imputeValue": -1}],
        )
        assert X_train_out["a"].tolist() == [1.0, -1]
        assert X_val_out["a"].tolist() == [-1]

    def test_impute_mean_fits_on_train_only(self, node):
        X_train = pd.DataFrame({"a": [1.0, 3.0, None]})  # mean of [1, 3] = 2.0
        X_val = pd.DataFrame({"a": [None, 100.0]})  # 100 must not affect train's fill value
        X_train_out, _, X_val_out, _, _, _ = node._handle_missing_values(
            X_train, pd.Series([0, 1, 2]), X_val, pd.Series([0, 1]),
            [{"columnName": "a", "strategy": "impute_mean"}],
        )
        assert X_train_out["a"].tolist() == [1.0, 3.0, 2.0]
        assert X_val_out["a"].tolist() == [2.0, 100.0]


class TestEngineerFeatures:
    def test_custom_expression_applies_to_both_splits(self, node):
        X_train = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        X_val = pd.DataFrame({"a": [5], "b": [6]})
        X_train_out, X_val_out = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "sum", "strategy": "custom_expression", "expression": "a + b"}],
        )
        assert X_train_out["sum"].tolist() == [4, 6]
        assert X_val_out["sum"].tolist() == [11]

    def test_bin_numeric_fits_edges_on_train_and_clips_val(self, node):
        X_train = pd.DataFrame({"a": [0.0, 10.0]})
        X_val = pd.DataFrame({"a": [999.0]})  # far outside train's range
        X_train_out, X_val_out = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "a_bin", "strategy": "bin_numeric", "binColumn": "a", "numBins": 2}],
        )
        assert X_train_out["a_bin"].notna().all()
        # Clipped into train's range instead of becoming NaN.
        assert X_val_out["a_bin"].notna().all()

    def test_normalize_fits_min_max_on_train_only(self, node):
        X_train = pd.DataFrame({"a": [0.0, 10.0]})  # min=0, max=10
        X_val = pd.DataFrame({"a": [100.0]})
        X_train_out, X_val_out = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "a_norm", "strategy": "normalize", "sourceColumns": ["a"]}],
        )
        assert X_train_out["a_norm"].tolist() == [0.0, 1.0]
        # (100 - 0) / (10 - 0) = 10.0 - proves min/max came from train, not val.
        assert X_val_out["a_norm"].tolist() == [10.0]

    def test_standardize_fits_mean_std_on_train_only(self, node):
        X_train = pd.DataFrame({"a": [1.0, 3.0]})  # mean=2, std=sqrt(2)
        X_val = pd.DataFrame({"a": [2.0]})
        X_train_out, X_val_out = node._engineer_features(
            X_train, X_val,
            [{"newColumnName": "a_std", "strategy": "standardize", "sourceColumns": ["a"]}],
        )
        assert X_val_out["a_std"].iloc[0] == pytest.approx(0.0)

    def test_polynomial_adds_degree_features_to_both_splits(self, node):
        X_train = pd.DataFrame({"a": [1.0, 2.0]})
        X_val = pd.DataFrame({"a": [3.0]})
        X_train_out, X_val_out = node._engineer_features(
            X_train, X_val,
            [{
                "newColumnName": "a_poly",
                "strategy": "polynomial",
                "polynomialColumns": ["a"],
                "polynomialDegree": 2,
            }],
        )
        assert "a_poly_a^2" in X_train_out.columns
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
