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
from app.modules.workflow.engine.nodes.ml.ml_utils import normalize_feature_expression
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState


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
