"""
normalize/standardize feature engineering is retired: Scaling Method already
rescales numeric features (fit on the training split only). Workflows saved
with them must keep training, and models trained with them must keep
predicting - with a warning telling the user to move off them.
"""

import pickle
import uuid

import numpy as np
import pandas as pd
import pytest

from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import _replay_feature_engineering
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState


async def _train(tmp_path, feature_engineering):
    rng = np.random.default_rng(2)
    n = 60
    df = pd.DataFrame({"a": rng.normal(10, 3, n), "b": rng.normal(0, 1, n)})
    df["target"] = df["a"] * 2 + df["b"] + rng.normal(0, 0.1, n)
    path = tmp_path / f"fe_{uuid.uuid4().hex[:6]}.csv"
    df.to_csv(path, index=False)
    node = TrainModelNode(node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={}))
    return await node.process(
        {
            "name": f"fe-{uuid.uuid4().hex[:8]}",
            "modelType": "linear_regression",
            "fileUrl": str(path),
            "targetColumn": "target",
            "featureColumns": ["a", "b"],
            "validationSplit": 0.25,
            "featureEngineering": feature_engineering,
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", ["normalize", "standardize"])
async def test_saved_workflow_with_a_retired_strategy_still_trains_with_a_warning(tmp_path, strategy):
    result = await _train(
        tmp_path, [{"newColumnName": "a_scaled", "strategy": strategy, "sourceColumns": ["a"]}]
    )
    assert result["success"] is True
    assert len(result["warnings"]) == 1
    assert f"'{strategy}' strategy" in result["warnings"][0]
    assert "Scaling Method" in result["warnings"][0]

    # The model was still trained with the derived column, and inference can
    # still replay it from a raw input row.
    with open(result["model_file_path"], "rb") as f:
        metadata = pickle.load(f)["metadata"]
    steps = metadata["feature_engineering_steps"]
    assert steps[0]["strategy"] == strategy
    replayed = _replay_feature_engineering({"a": [10.0], "b": [0.0]}, steps, batch_size=1)
    assert "a_scaled" in replayed


@pytest.mark.asyncio
async def test_current_strategies_give_no_warning(tmp_path):
    result = await _train(
        tmp_path,
        [
            {"newColumnName": "ab", "strategy": "custom_expression", "expression": "a * b"},
            {"newColumnName": "a_bin", "strategy": "bin_numeric", "binColumn": "a", "numBins": 3},
            {"newColumnName": "poly", "strategy": "polynomial", "polynomialColumns": ["a", "b"], "polynomialDegree": 2},
        ],
    )
    assert result["success"] is True
    assert "warnings" not in result
