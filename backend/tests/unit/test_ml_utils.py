import pandas as pd

from app.modules.workflow.engine.nodes.ml.ml_utils import is_classification_task


class TestIsClassificationTask:
    def test_classification_only_model_ignores_target_dtype(self):
        y = pd.Series([1.5, 2.5, 3.5])
        assert is_classification_task(y, "logistic_regression") is True

    def test_regression_only_model_ignores_target_dtype(self):
        y = pd.Series(["a", "b", "c"])
        assert is_classification_task(y, "linear_regression") is False

    def test_bool_dtype_target_is_classification(self):
        y = pd.Series([True, False, True, False])
        assert y.dtype == "bool"
        assert is_classification_task(y, "svm") is True

    def test_nullable_boolean_dtype_target_is_classification(self):
        y = pd.Series([True, False, None], dtype="boolean")
        assert is_classification_task(y, "knn") is True

    def test_yes_no_text_target_is_classification(self):
        y = pd.Series(["Yes", "No", "Yes"])
        assert y.dtype == "object"
        assert is_classification_task(y, "neural_network") is True

    def test_low_cardinality_int_target_is_classification(self):
        y = pd.Series([0, 1, 2, 0, 1])
        assert is_classification_task(y, "random_forest") is True

    def test_high_cardinality_int_target_is_regression(self):
        y = pd.Series(range(100))
        assert is_classification_task(y, "svm") is False

    def test_float_target_is_regression(self):
        y = pd.Series([1.1, 2.2, 3.3])
        assert is_classification_task(y, "xgboost") is False
