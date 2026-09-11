import uuid

import numpy as np
import pandas as pd
import pytest

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
