import pandas as pd
import pytest

from app.modules.workflow.engine.nodes.ml.train_model_node import (
    TREE_BASED_MODEL_TYPES,
    TrainModelNode,
)


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
