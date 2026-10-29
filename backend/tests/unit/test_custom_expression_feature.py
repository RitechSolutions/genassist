"""
Custom Expression features are evaluated with DataFrame.eval, which takes
plain column names (price * quantity). The dialog used to suggest
df["column_name"], which failed with "name 'df' is not defined" - and the
feature was then silently skipped, training a "successful" model without it.
"""

import pickle
import uuid

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import _replay_feature_engineering
from app.modules.workflow.engine.nodes.ml.ml_utils import (
    normalize_feature_expression,
    translate_category_literals,
)
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState


class TestTranslateCategoryLiterals:
    # Label/ordinal columns hold codes by the time feature engineering runs,
    # so text compared against them must become the matching code.
    LABEL = {"color": {"blue": 0, "red": 1}}
    ORDINAL = {"size": {"Low": 0, "Medium": 1, "High": 2}}

    @pytest.mark.parametrize(
        "expression, expected",
        [
            ('size == "High"', "size == 2"),
            ('"High" == size', "2 == size"),
            ("size != 'Low'", "size != 0"),
            ('size >= "Medium"', "size >= 1"),
            ('size in ["Medium", "High"]', "size in [1, 2]"),
            ('color == "red"', "color == 1"),
            ('(size == "High") & (color == "blue")', "(size == 2) & (color == 0)"),
            ('size == " High"', "size == 2"),  # stray spaces match, like ordinal encoding
            # pandas binds & and | looser than comparisons, so no parentheses needed
            ('size == "High" & price > 3', "(size == 2) & (price > 3)"),
            ('size == "Low" | color == "red"', "(size == 0) | (color == 1)"),
            ('size == "High" and price > 3', "(size == 2) & (price > 3)"),
        ],
    )
    def test_translates_text_compared_to_encoded_column(self, expression, expected):
        assert translate_category_literals(expression, self.LABEL, self.ORDINAL) == expected

    @pytest.mark.parametrize("parenthesized", [False, True])
    @pytest.mark.parametrize("op", ["&", "|"])
    def test_unparenthesized_boolean_matches_parenthesized(self, op, parenthesized):
        # DataFrame.eval reads both forms the same way; so must the translation,
        # or "High" stays text and the feature is False on every row.
        df = pd.DataFrame({"size": [2, 2, 0, 1], "price": [5, 1, 5, 1]})
        expected = df.eval(f"(size == 2) {op} (price > 3)")
        expression = f'(size == "High") {op} (price > 3)' if parenthesized else f'size == "High" {op} price > 3'
        result = df.eval(translate_category_literals(expression, self.LABEL, self.ORDINAL))
        pd.testing.assert_series_equal(result, expected)

    def test_text_left_inside_operand_raises(self):
        with pytest.raises(ValueError, match="wrap each comparison in parentheses"):
            translate_category_literals('size == "Hi" + "gh"', self.LABEL, self.ORDINAL)

    @pytest.mark.parametrize(
        "expression",
        [
            "size * price",  # no text to translate
            "size == 2",  # already a code
            'name == "High"',  # not an encoded column
            "price > 3 and",  # invalid - left for DataFrame.eval to report
        ],
    )
    def test_leaves_other_expressions_unchanged(self, expression):
        assert translate_category_literals(expression, self.LABEL, self.ORDINAL) == expression

    def test_backtick_column_name(self):
        ordinal = {"shirt size": {"S": 0, "L": 1}}
        assert translate_category_literals('`shirt size` == "L"', {}, ordinal) == "`shirt size` == 1"

    def test_unknown_category_raises(self):
        with pytest.raises(ValueError, match="'Hgh', which is not one of its categories"):
            translate_category_literals('size == "Hgh"', self.LABEL, self.ORDINAL)


class TestNormalizeFeatureExpression:
    @pytest.mark.parametrize(
        "expression, expected",
        [
            ('df["price"] * df["quantity"]', "price * quantity"),
            ("df['price'] * df['quantity']", "price * quantity"),
            ('df[ "price" ] + 1', "price + 1"),
            ('df["unit price"] * df["qty"]', "`unit price` * qty"),
            ('df["class"] * 2', "`class` * 2"),  # a Python keyword needs quoting too
            ("price * quantity", "price * quantity"),  # already plain: unchanged
            ("`unit price` * qty", "`unit price` * qty"),
        ],
    )
    def test_rewrites_df_references_to_column_names(self, expression, expected):
        assert normalize_feature_expression(expression) == expected

    def test_rewritten_expressions_evaluate(self):
        df = pd.DataFrame({"price": [2.0, 3.0], "quantity": [4, 5], "unit price": [1.0, 2.0]})
        assert df.eval(normalize_feature_expression('df["price"] * df["quantity"]')).tolist() == [8.0, 15.0]
        assert df.eval(normalize_feature_expression('df["unit price"] * df["quantity"]')).tolist() == [4.0, 10.0]


async def _train(tmp_path, expression):
    rng = np.random.default_rng(4)
    n = 60
    df = pd.DataFrame({"price": rng.uniform(1, 10, n), "quantity": rng.integers(1, 20, n)})
    df["target"] = df["price"] * df["quantity"] + rng.normal(0, 0.5, n)
    path = tmp_path / f"expr_{uuid.uuid4().hex[:6]}.csv"
    df.to_csv(path, index=False)
    node = TrainModelNode(node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={}))
    return await node.process(
        {
            "name": f"expr-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": str(path),
            "targetColumn": "target",
            "featureColumns": ["price", "quantity"],
            "validationSplit": 0.25,
            "featureEngineering": [
                {"newColumnName": "revenue", "strategy": "custom_expression", "expression": expression}
            ],
        }
    )


def _feature_steps(result):
    with open(result["model_file_path"], "rb") as f:
        return pickle.load(f)["metadata"]["feature_engineering_steps"]


@pytest.mark.asyncio
@pytest.mark.parametrize("expression", ["price * quantity", 'df["price"] * df["quantity"]'])
async def test_both_syntaxes_train_with_the_feature_and_replay_it(tmp_path, expression):
    result = await _train(tmp_path, expression)
    assert result["success"] is True
    steps = _feature_steps(result)
    # The feature is in the model (before: the df[...] form was silently dropped).
    assert [s["new_col"] for s in steps] == ["revenue"]
    assert steps[0]["expression"] == "price * quantity"
    # And inference recomputes it from raw inputs.
    replayed = _replay_feature_engineering({"price": [2.0], "quantity": [3]}, steps, batch_size=1)
    assert replayed["revenue"].tolist() == [6.0]


@pytest.mark.asyncio
async def test_an_expression_that_cannot_be_evaluated_fails_clearly(tmp_path):
    with pytest.raises(AppException) as exc_info:
        await _train(tmp_path, "price * missing_column")
    detail = exc_info.value.error_detail
    assert "Feature engineering 'revenue'" in detail
    assert "price * missing_column" in detail
    assert "Reference columns by name" in detail


def test_inference_replays_older_df_syntax_steps():
    # A step stored with the df[...] form still replays.
    steps = [{"strategy": "custom_expression", "new_col": "revenue", "expression": 'df["price"] * df["quantity"]'}]
    replayed = _replay_feature_engineering({"price": [2.0], "quantity": [3]}, steps, batch_size=1)
    assert replayed["revenue"].tolist() == [6.0]
