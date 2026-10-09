"""
Train Model feature engineering: Log Transform, Quantile Transformer, Power
Transformer and PCA.

Each must be fit on the training split only, be replayed identically at
inference, fail clearly on inputs it can't take, and work when the user set
no Missing Value Handling (missing values are always filled before feature
engineering during training; inference requires an explicit model default).
"""

import pickle
import uuid

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import (
    _prepare_inference_inputs,
    _replay_feature_engineering,
)
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState


@pytest.fixture
def node() -> TrainModelNode:
    return TrainModelNode(node_id="test", node_config={}, state=None)


def _splits(n_train=40, n_val=10, seed=0):
    rng = np.random.default_rng(seed)
    make = lambda n: pd.DataFrame({
        "a": rng.uniform(1, 100, n),
        "b": rng.uniform(1, 10, n),
        "c": rng.normal(0, 1, n),
    })
    return make(n_train), make(n_val)


def _fe(node, X_train, X_val, item):
    return node._engineer_features(X_train, X_val, [item])


class TestLogTransform:
    def test_log1p_of_each_column_and_replay(self, node):
        X_train, X_val = _splits()
        X_train2, X_val2, steps = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "log", "strategy": "log_transform", "sourceColumns": ["a", "b"],
        })
        assert np.allclose(X_train2["log_a"], np.log1p(X_train["a"]))
        assert np.allclose(X_val2["log_b"], np.log1p(X_val["b"]))
        assert "a" in X_train2.columns  # sources kept by default
        replayed = _replay_feature_engineering({"a": [9.0], "b": [0.0]}, steps, 1)
        assert np.allclose(replayed["log_a"], [np.log1p(9.0)])
        assert np.allclose(replayed["log_b"], [0.0])

    def test_negative_values_fail_clearly_at_training_and_inference(self, node):
        X_train, X_val = _splits()
        X_train.loc[3, "c"] = -2.0
        with pytest.raises(AppException) as exc_info:
            _fe(node, X_train, X_val, {"newColumnName": "log", "strategy": "log_transform", "sourceColumns": ["c"]})
        assert "Log Transform" in exc_info.value.error_detail and "negative" in exc_info.value.error_detail

        X_train, X_val = _splits()
        _, _, steps = _fe(node, X_train, X_val, {"newColumnName": "log", "strategy": "log_transform", "sourceColumns": ["a"]})
        with pytest.raises(AppException) as exc_info:
            _replay_feature_engineering({"a": [-5.0]}, steps, 1)
        assert "negative" in exc_info.value.error_detail


class TestQuantileTransformer:
    def test_fit_on_training_only(self, node):
        X_train, X_val = _splits()
        # An extreme validation value must not move the fitted quantiles.
        X_val.loc[0, "a"] = 1e9
        _, X_val2, steps = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "q", "strategy": "quantile_transform", "sourceColumns": ["a"],
        })
        transformer = steps[0]["transformer"]
        assert transformer.n_quantiles_ == len(X_train)  # capped at training rows
        assert transformer.quantiles_[:, 0].max() == pytest.approx(X_train["a"].max())
        assert X_val2["q"].iloc[0] == pytest.approx(1.0)  # clipped to the top of the training range

    def test_normal_output_and_replay_matches_training(self, node):
        X_train, X_val = _splits()
        X_train2, _, steps = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "q", "strategy": "quantile_transform", "sourceColumns": ["a"],
            "quantileOutputDistribution": "normal",
        })
        replayed = _replay_feature_engineering({"a": X_train["a"].tolist()[:5]}, steps, 5)
        assert np.allclose(replayed["q"], X_train2["q"].iloc[:5])


class TestPowerTransformer:
    def test_yeo_johnson_does_not_standardize(self, node):
        X_train, X_val = _splits()
        _, _, steps = _fe(node, X_train, X_val, {
            "newColumnName": "p", "strategy": "power_transform", "sourceColumns": ["c"],
        })
        assert steps[0]["transformer"].method == "yeo-johnson"
        # Scaling Method standardizes afterwards; doing it here too would scale twice.
        assert steps[0]["transformer"].standardize is False

    def test_box_cox_needs_positive_values(self, node):
        X_train, X_val = _splits()
        with pytest.raises(AppException) as exc_info:
            _fe(node, X_train, X_val, {
                "newColumnName": "p", "strategy": "power_transform", "sourceColumns": ["c"], "powerMethod": "box-cox",
            })
        assert "Box-Cox" in exc_info.value.error_detail and "Yeo-Johnson" in exc_info.value.error_detail

    def test_box_cox_on_positive_values_and_replay(self, node):
        X_train, X_val = _splits()
        X_train2, _, steps = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "p", "strategy": "power_transform", "sourceColumns": ["a"], "powerMethod": "box-cox",
        })
        replayed = _replay_feature_engineering({"a": X_train["a"].tolist()[:3]}, steps, 3)
        assert np.allclose(replayed["p"], X_train2["p"].iloc[:3])
        with pytest.raises(AppException):
            _replay_feature_engineering({"a": [0.0]}, steps, 1)


class TestPCA:
    def test_replaces_sources_by_default_and_reports_variance(self, node):
        X_train, X_val = _splits()
        X_train2, X_val2, steps = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "pc", "strategy": "pca", "sourceColumns": ["a", "b", "c"], "pcaComponents": 2,
        })
        assert list(X_train2.columns) == ["pc_1", "pc_2"]
        assert list(X_val2.columns) == ["pc_1", "pc_2"]
        assert len(steps[0]["explained_variance_ratio"]) == 2
        # Standardized before PCA by default.
        assert "scale" in steps[0]["transformer"].named_steps

    def test_keep_sources_and_variance_share(self, node):
        X_train, X_val = _splits()
        X_train2, _, steps = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "pc", "strategy": "pca", "sourceColumns": ["a", "b", "c"],
            "pcaComponents": 0.9, "replaceSourceColumns": False,
        })
        assert {"a", "b", "c"} <= set(X_train2.columns)
        assert sum(steps[0]["explained_variance_ratio"]) >= 0.9

    def test_fit_on_training_rows_only(self, node):
        X_train, X_val = _splits()
        X_val_extreme = X_val.copy() * 1000
        _, _, steps_a = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "pc", "strategy": "pca", "sourceColumns": ["a", "b"], "pcaComponents": 1,
        })
        _, _, steps_b = _fe(node, X_train.copy(), X_val_extreme, {
            "newColumnName": "pc", "strategy": "pca", "sourceColumns": ["a", "b"], "pcaComponents": 1,
        })
        comp_a = steps_a[0]["transformer"].named_steps["pca"].components_
        comp_b = steps_b[0]["transformer"].named_steps["pca"].components_
        assert np.allclose(comp_a, comp_b)

    def test_replay_matches_training(self, node):
        X_train, X_val = _splits()
        X_train2, _, steps = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "pc", "strategy": "pca", "sourceColumns": ["a", "b", "c"], "pcaComponents": 2,
        })
        rows = X_train.iloc[:4]
        replayed = _replay_feature_engineering({c: rows[c].tolist() for c in "abc"}, steps, 4)
        assert np.allclose(replayed["pc_1"], X_train2["pc_1"].iloc[:4])
        assert np.allclose(replayed["pc_2"], X_train2["pc_2"].iloc[:4])

    @pytest.mark.parametrize(
        "item, message",
        [
            ({"sourceColumns": ["a"]}, "at least 2 columns"),
            ({"sourceColumns": ["a", "b"], "pcaComponents": 3}, "3 components from only 2 columns"),
            ({"sourceColumns": ["a", "b"], "pcaComponents": 0}, "number of components"),
            ({"sourceColumns": ["a", "b"], "pcaComponents": 1.5}, "number of components"),
        ],
    )
    def test_invalid_config_fails_clearly(self, item, message):
        with pytest.raises(AppException) as exc_info:
            TrainModelNode._validate_column_transform_config({"newColumnName": "pc", "strategy": "pca", **item})
        assert message in exc_info.value.error_detail


class TestInputChecks:
    def test_empty_values_from_an_earlier_step_fail_clearly(self, node):
        X_train, X_val = _splits()
        X_train.loc[0, "b"] = 0.0
        with pytest.raises(AppException) as exc_info:
            node._engineer_features(X_train, X_val, [
                {"newColumnName": "ratio", "strategy": "custom_expression", "expression": "a / (b - b)"},
                {"newColumnName": "pc", "strategy": "pca", "sourceColumns": ["ratio", "a"], "pcaComponents": 1},
            ])
        detail = exc_info.value.error_detail
        assert "empty or infinite values" in detail and "earlier feature engineering step" in detail

    def test_non_numeric_and_unknown_columns_fail_clearly(self, node):
        X_train, X_val = _splits()
        X_train["t"] = "x"
        X_val["t"] = "x"
        with pytest.raises(AppException) as exc_info:
            _fe(node, X_train, X_val, {"newColumnName": "q", "strategy": "quantile_transform", "sourceColumns": ["t"]})
        assert "not numeric" in exc_info.value.error_detail
        with pytest.raises(AppException) as exc_info:
            _fe(node, X_train, X_val, {"newColumnName": "q", "strategy": "quantile_transform", "sourceColumns": ["zzz"]})
        assert "not found" in exc_info.value.error_detail

    @pytest.mark.parametrize(
        "item, message",
        [
            ({"strategy": "log_transform"}, "choose at least one column"),
            ({"strategy": "power_transform", "sourceColumns": ["a"], "powerMethod": "cube"}, "method must be"),
            ({"strategy": "quantile_transform", "sourceColumns": ["a"], "quantileOutputDistribution": "x"}, "output distribution"),
            ({"strategy": "quantile_transform", "sourceColumns": ["a"], "nQuantiles": 1}, "number of quantiles"),
        ],
    )
    def test_invalid_settings_fail_clearly(self, item, message):
        with pytest.raises(AppException) as exc_info:
            TrainModelNode._validate_column_transform_config({"newColumnName": "f", **item})
        assert message in exc_info.value.error_detail


class TestMissingValuesAtInference:
    def test_explicit_defaults_fill_missing_and_null_inputs_before_replay(self, node):
        X_train, X_val = _splits()
        _, _, steps = _fe(node, X_train.copy(), X_val.copy(), {
            "newColumnName": "pc", "strategy": "pca", "sourceColumns": ["a", "b"], "pcaComponents": 1,
        })
        defaults = {"a": 50.0, "b": 5.0}
        full = _replay_feature_engineering({"a": [50.0], "b": [5.0]}, steps, 1)
        absent_inputs, _ = _prepare_inference_inputs(
            {"a": [50.0]}, ["a", "b"], defaults=defaults
        )
        null_inputs, _ = _prepare_inference_inputs(
            {"a": [50.0], "b": [None]}, ["a", "b"], defaults=defaults
        )
        absent = _replay_feature_engineering(absent_inputs, steps, 1)
        null = _replay_feature_engineering(null_inputs, steps, 1)
        assert np.allclose(absent["pc_1"], full["pc_1"])
        assert np.allclose(null["pc_1"], full["pc_1"])

    def test_existing_strategies_also_rebuild_with_a_missing_input(self):
        steps = [{"strategy": "custom_expression", "new_col": "double", "expression": "count * 2"}]
        prepared, _ = _prepare_inference_inputs({}, ["count"], defaults={"count": 24.0})
        assert _replay_feature_engineering(prepared, steps, 1)["double"].tolist() == [48.0]


async def _train(tmp_path, feature_engineering, with_gaps=False):
    rng = np.random.default_rng(9)
    n = 80
    df = pd.DataFrame({"a": rng.uniform(1, 100, n), "b": rng.uniform(1, 10, n), "c": rng.normal(0, 1, n)})
    df["target"] = df["a"] * 0.5 + df["b"] * 2 + rng.normal(0, 0.5, n)
    if with_gaps:
        df.loc[::9, "a"] = np.nan
    path = tmp_path / f"fe_{uuid.uuid4().hex[:6]}.csv"
    df.to_csv(path, index=False)
    train_node = TrainModelNode(node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={}))
    return await train_node.process({
        "name": f"fe-{uuid.uuid4().hex[:8]}",
        "modelType": "linear_regression",
        "fileUrl": str(path),
        "targetColumn": "target",
        "featureColumns": ["a", "b", "c"],
        "validationSplit": 0.25,
        "featureEngineering": feature_engineering,
    })


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "item",
    [
        {"newColumnName": "log_a", "strategy": "log_transform", "sourceColumns": ["a"]},
        {"newColumnName": "q", "strategy": "quantile_transform", "sourceColumns": ["a", "b"]},
        {"newColumnName": "p", "strategy": "power_transform", "sourceColumns": ["c"]},
        {"newColumnName": "pc", "strategy": "pca", "sourceColumns": ["a", "b", "c"], "pcaComponents": 2},
    ],
)
async def test_each_strategy_trains_end_to_end_with_gaps_and_no_missing_value_settings(tmp_path, item):
    result = await _train(tmp_path, [item], with_gaps=True)
    assert result["success"] is True
    # The automatic fill is reported instead of silent.
    assert any("Column 'a'" in w and "filled automatically" in w for w in result["warnings"])
    assert any(
        "Training-time missing-value fills are not used automatically during inference" in warning
        for warning in result["warnings"]
    )
    with open(result["model_file_path"], "rb") as f:
        metadata = pickle.load(f)["metadata"]
    steps = metadata["feature_engineering_steps"]
    assert steps[0]["strategy"] == item["strategy"]
    assert "missing_value_fills" not in metadata
    # A model owner may configure a deliberate inference default independently.
    prepared, _ = _prepare_inference_inputs(
        {"b": [5.0], "c": [0.1]},
        ["a", "b", "c"],
        defaults={"a": 50.0},
    )
    replayed = _replay_feature_engineering(prepared, steps, 1)
    assert all(np.isfinite(v).all() for v in replayed.values())


@pytest.mark.asyncio
async def test_pca_replacing_sources_trains_on_the_components(tmp_path):
    result = await _train(tmp_path, [
        {"newColumnName": "pc", "strategy": "pca", "sourceColumns": ["a", "b"], "pcaComponents": 1},
    ])
    with open(result["model_file_path"], "rb") as f:
        metadata = pickle.load(f)["metadata"]
    assert metadata["model_input_columns"] == ["c", "pc_1"]
    assert "warnings" not in result  # no gaps, nothing filled
