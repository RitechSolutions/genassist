"""
Shared model construction for the Train Model node.

Centralizes the default hyperparameters and unfitted-estimator construction
for every supported model type, so both the plain training path
(``TrainModelNode``) and the hyperparameter optimization path
(``hyperparameter_optimization.py``) build estimators the same way instead of
duplicating per-model constructor logic.
"""

import logging
from typing import Any, Dict

from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

logger = logging.getLogger(__name__)

# Try to import xgboost (optional dependency)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost is not installed. XGBoost models will not be available.")

# Try to import lightgbm (optional dependency)
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.warning("LightGBM is not installed. LightGBM models will not be available.")

# Try to import catboost (optional dependency)
try:
    from catboost import CatBoostClassifier, CatBoostRegressor
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False
    logger.warning("CatBoost is not installed. CatBoost models will not be available.")

# Model types that require an optional dependency, and the flag guarding each
OPTIONAL_MODEL_DEPENDENCIES = {
    "xgboost": ("XGBoost", lambda: XGBOOST_AVAILABLE),
    "lightgbm": ("LightGBM", lambda: LIGHTGBM_AVAILABLE),
    "catboost": ("CatBoost", lambda: CATBOOST_AVAILABLE),
}

VALID_MODEL_TYPES = [
    "xgboost",
    "lightgbm",
    "catboost",
    "random_forest",
    "extra_trees",
    "gradient_boosting",
    "decision_tree",
    "linear_regression",
    "ridge_regression",
    "lasso_regression",
    "elastic_net",
    "logistic_regression",
    "svm",
    "knn",
    "neural_network",
]

# Default constructor params per model type. Merged with (and overridden by)
# any user-supplied `modelParameters` before building an estimator.
MODEL_DEFAULT_PARAMS: Dict[str, Dict[str, Any]] = {
    "xgboost": {
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "random_state": 42,
    },
    "lightgbm": {
        "n_estimators": 100,
        "max_depth": -1,
        "learning_rate": 0.1,
        "random_state": 42,
    },
    "catboost": {
        "iterations": 100,
        "depth": 6,
        "learning_rate": 0.1,
        "random_state": 42,
        "verbose": False,
    },
    "random_forest": {
        "n_estimators": 100,
        "max_depth": None,
        "random_state": 42,
    },
    "extra_trees": {
        "n_estimators": 100,
        "max_depth": None,
        "random_state": 42,
    },
    "gradient_boosting": {
        "n_estimators": 100,
        "max_depth": 3,
        "learning_rate": 0.1,
        "random_state": 42,
    },
    "decision_tree": {
        "max_depth": None,
        "random_state": 42,
    },
    "linear_regression": {},
    "ridge_regression": {
        "alpha": 1.0,
        "random_state": 42,
    },
    "lasso_regression": {
        "alpha": 1.0,
        "random_state": 42,
    },
    "elastic_net": {
        "alpha": 1.0,
        "l1_ratio": 0.5,
        "random_state": 42,
    },
    "logistic_regression": {
        "max_iter": 1000,
        "random_state": 42,
    },
    "svm": {
        "kernel": "rbf",
        "C": 1.0,
    },
    "knn": {
        "n_neighbors": 5,
    },
    "neural_network": {
        "hidden_layer_sizes": (100,),
        "max_iter": 500,
        "random_state": 42,
        "early_stopping": True,
        "validation_fraction": 0.1,
    },
}


def check_optional_dependency(model_type: str) -> None:
    """Raise if model_type needs an optional library that isn't installed."""
    if model_type in OPTIONAL_MODEL_DEPENDENCIES:
        package_name, is_available = OPTIONAL_MODEL_DEPENDENCIES[model_type]
        if not is_available():
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"{package_name} is not installed. Please install it with: pip install {model_type}",
            )


def build_estimator(model_type: str, is_classification: bool, params: Dict[str, Any]):
    """
    Construct an unfitted estimator for the given model type.

    Args:
        model_type: One of VALID_MODEL_TYPES.
        is_classification: Whether to build the classifier or regressor variant
            (ignored for regression-only / classification-only model types).
        params: Full constructor kwargs (defaults already merged with overrides).

    Returns:
        An unfitted sklearn-compatible estimator instance.
    """
    if model_type == "xgboost":
        return xgb.XGBClassifier(**params) if is_classification else xgb.XGBRegressor(**params)
    elif model_type == "lightgbm":
        return lgb.LGBMClassifier(**params) if is_classification else lgb.LGBMRegressor(**params)
    elif model_type == "catboost":
        return CatBoostClassifier(**params) if is_classification else CatBoostRegressor(**params)
    elif model_type == "random_forest":
        return RandomForestClassifier(**params) if is_classification else RandomForestRegressor(**params)
    elif model_type == "extra_trees":
        return ExtraTreesClassifier(**params) if is_classification else ExtraTreesRegressor(**params)
    elif model_type == "gradient_boosting":
        return GradientBoostingClassifier(**params) if is_classification else GradientBoostingRegressor(**params)
    elif model_type == "decision_tree":
        return DecisionTreeClassifier(**params) if is_classification else DecisionTreeRegressor(**params)
    elif model_type == "linear_regression":
        return LinearRegression(**params)
    elif model_type == "ridge_regression":
        return Ridge(**params)
    elif model_type == "lasso_regression":
        return Lasso(**params)
    elif model_type == "elastic_net":
        return ElasticNet(**params)
    elif model_type == "logistic_regression":
        return LogisticRegression(**params)
    elif model_type == "svm":
        return SVC(**params) if is_classification else SVR(**params)
    elif model_type == "knn":
        return KNeighborsClassifier(**params) if is_classification else KNeighborsRegressor(**params)
    elif model_type == "neural_network":
        return MLPClassifier(**params) if is_classification else MLPRegressor(**params)
    else:
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=f"Unsupported model type: {model_type}",
        )
