"""
Curated hyperparameter search spaces for the Train Model node's
hyperparameter optimization feature (Random Search / Grid Search / Bayesian
Optimization).

Each model type maps to a small, declarative space of its highest-impact
tunable parameters (4-6 params) rather than every constructor argument —
grid/random/bayesian search all get slower and noisier as dimensionality
grows, and params like `random_state`, `n_jobs`, or `verbose` are never
worth searching. A curated core keeps searches fast and results meaningful.

Each param entry is one of:
    {"type": "int", "low": <int>, "high": <int>, "nullable": <bool, optional>}
    {"type": "float", "low": <float>, "high": <float>, "log": <bool, optional>}
    {"type": "categorical", "choices": [...]}

`nullable` (int/float only) means None is also a valid value (e.g. unbounded
`max_depth`) and gets included as an extra choice by the search adapters.
"""

from typing import Any, Dict

HYPERPARAMETER_SPACES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "xgboost": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 2, "high": 12},
        "learning_rate": {"type": "float", "low": 1e-3, "high": 0.3, "log": True},
        "subsample": {"type": "float", "low": 0.5, "high": 1.0},
        "colsample_bytree": {"type": "float", "low": 0.5, "high": 1.0},
    },
    "lightgbm": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 2, "high": 16, "nullable": True},
        "learning_rate": {"type": "float", "low": 1e-3, "high": 0.3, "log": True},
        "num_leaves": {"type": "int", "low": 15, "high": 127},
        "subsample": {"type": "float", "low": 0.5, "high": 1.0},
    },
    "catboost": {
        "iterations": {"type": "int", "low": 50, "high": 500},
        "depth": {"type": "int", "low": 3, "high": 10},
        "learning_rate": {"type": "float", "low": 1e-3, "high": 0.3, "log": True},
        "l2_leaf_reg": {"type": "float", "low": 1.0, "high": 10.0},
    },
    "random_forest": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 3, "high": 30, "nullable": True},
        "min_samples_split": {"type": "int", "low": 2, "high": 20},
        "min_samples_leaf": {"type": "int", "low": 1, "high": 10},
        "max_features": {"type": "categorical", "choices": ["sqrt", "log2", None]},
        "bootstrap": {"type": "categorical", "choices": [True, False]},
    },
    "extra_trees": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 3, "high": 30, "nullable": True},
        "min_samples_split": {"type": "int", "low": 2, "high": 20},
        "min_samples_leaf": {"type": "int", "low": 1, "high": 10},
        "max_features": {"type": "categorical", "choices": ["sqrt", "log2", None]},
    },
    "gradient_boosting": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 2, "high": 10},
        "learning_rate": {"type": "float", "low": 1e-3, "high": 0.3, "log": True},
        "subsample": {"type": "float", "low": 0.5, "high": 1.0},
        "min_samples_split": {"type": "int", "low": 2, "high": 20},
    },
    "decision_tree": {
        "max_depth": {"type": "int", "low": 2, "high": 30, "nullable": True},
        "min_samples_split": {"type": "int", "low": 2, "high": 20},
        "min_samples_leaf": {"type": "int", "low": 1, "high": 10},
        "max_features": {"type": "categorical", "choices": ["sqrt", "log2", None]},
    },
    "ridge_regression": {
        "alpha": {"type": "float", "low": 1e-3, "high": 100.0, "log": True},
        "solver": {"type": "categorical", "choices": ["auto", "svd", "cholesky", "lsqr"]},
    },
    "lasso_regression": {
        "alpha": {"type": "float", "low": 1e-3, "high": 10.0, "log": True},
    },
    "elastic_net": {
        "alpha": {"type": "float", "low": 1e-3, "high": 10.0, "log": True},
        "l1_ratio": {"type": "float", "low": 0.0, "high": 1.0},
    },
    "logistic_regression": {
        "C": {"type": "float", "low": 1e-3, "high": 100.0, "log": True},
        "penalty": {"type": "categorical", "choices": ["l1", "l2"]},
        "solver": {"type": "categorical", "choices": ["liblinear", "saga"]},
    },
    "svm": {
        "C": {"type": "float", "low": 1e-2, "high": 100.0, "log": True},
        "kernel": {"type": "categorical", "choices": ["linear", "rbf", "poly"]},
        "gamma": {"type": "categorical", "choices": ["scale", "auto"]},
    },
    "knn": {
        "n_neighbors": {"type": "int", "low": 2, "high": 30},
        "weights": {"type": "categorical", "choices": ["uniform", "distance"]},
        "p": {"type": "categorical", "choices": [1, 2]},
    },
    "neural_network": {
        "hidden_layer_sizes": {
            "type": "categorical",
            "choices": [(50,), (100,), (100, 50), (100, 100)],
        },
        "alpha": {"type": "float", "low": 1e-5, "high": 1e-1, "log": True},
        "learning_rate_init": {"type": "float", "low": 1e-4, "high": 1e-1, "log": True},
    },
    # linear_regression has no meaningful hyperparameters to search — omitted
    # on purpose; the optimizer treats a missing/empty space as a no-op.
}


def get_space(model_type: str) -> Dict[str, Dict[str, Any]]:
    """Return the curated search space for a model type (empty if none defined)."""
    return HYPERPARAMETER_SPACES.get(model_type, {})
