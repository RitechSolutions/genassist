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
