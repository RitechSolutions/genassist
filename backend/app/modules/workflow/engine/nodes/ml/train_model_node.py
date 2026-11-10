"""
Train Model node implementation using the BaseNode class.

This node trains ML models on CSV data and saves them as .pkl files.
"""

import asyncio
import logging
import os
import pickle
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.preprocessing import (
    MaxAbsScaler,
    MinMaxScaler,
    OneHotEncoder,
    PolynomialFeatures,
    PowerTransformer,
    QuantileTransformer,
    RobustScaler,
    StandardScaler,
)

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.nodes.ml import hyperparameter_optimization as hpo_module
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml import model_registry
from app.modules.workflow.engine.nodes.ml import training_checks
from app.modules.workflow.engine.nodes.ml import training_data_storage
from app.modules.workflow.engine.nodes.ml import training_progress

logger = logging.getLogger(__name__)

# Feature engineering strategies no longer offered for new features: they
# duplicate scalingMethod (rescaling numeric columns, fit on the training
# split) and so scaled the same values twice. Still accepted and run for
# workflows saved with them, and replayed at inference for models trained
# with them.
_RETIRED_FE_STRATEGIES = ("normalize", "standardize")


def _rows_dropped_warning(verb: str, split_counts: Dict[str, int], detail: str) -> str:
    """
    User-facing warning for rows a training step left out, e.g.
    "Removed 5 training rows with outliers in 'x' (iqr)". split_counts maps a
    split name ("training", "validation") to its row count; zero counts are
    left out of the sentence.
    """
    parts = [f"{count} {split}" for split, count in split_counts.items() if count]
    rows = "row" if sum(split_counts.values()) == 1 else "rows"
    return f"{verb} {' and '.join(parts)} {rows} {detail}"


def _join_reason_counts(reason_counts: Dict[str, int]) -> str:
    """{"zero": 12, "missing": 7} -> "zero (12) or missing (7)"; zero counts left out."""
    parts = [f"{reason} ({count})" for reason, count in reason_counts.items() if count]
    if len(parts) < 2:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} or {parts[-1]}"


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
_OPTIONAL_MODEL_DEPENDENCIES = {
    "xgboost": ("XGBoost", lambda: XGBOOST_AVAILABLE),
    "lightgbm": ("LightGBM", lambda: LIGHTGBM_AVAILABLE),
    "catboost": ("CatBoost", lambda: CATBOOST_AVAILABLE),
}
# Scale-invariant: splits on raw feature values, unaffected by monotonic scaling.
# Covers all 15 registry model types (see ModelType in app/schemas/ml_model.py),
# not just the 5 trainable today, so this needs no changes when this node grows
# to support the rest.
TREE_BASED_MODEL_TYPES = frozenset({
    "decision_tree", "random_forest", "extra_trees", "gradient_boosting",
    "xgboost", "lightgbm", "catboost",
})


class TrainModelNode(BaseNode):
    """
    Train Model node that trains ML models on CSV data.

    Supports:
    - XGBoost, LightGBM, CatBoost (gradient boosting; classification and regression)
    - Random Forest, Extra Trees, Gradient Boosting, Decision Tree (classification and regression)
    - Linear Regression, Ridge Regression, Lasso Regression, Elastic Net (regression)
    - Logistic Regression (classification)
    - Support Vector Machine, K-Nearest Neighbors (classification and regression)
    - Neural Network (MLPClassifier/MLPRegressor)
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a train model node.

        Args:
            config: The resolved configuration for the node containing:
                - name: Model name (required)
                - modelType: Type of model - "xgboost", "lightgbm", "catboost", "random_forest",
                            "extra_trees", "gradient_boosting", "decision_tree", "linear_regression",
                            "ridge_regression", "lasso_regression", "elastic_net", "logistic_regression",
                            "svm", "knn", or "neural_network" (required).
                - fileUrl: Path to CSV file with training data (required)
                - targetColumn: Name of the target column (required)
                - featureColumns: List of feature column names (required)
                - modelParameters: Dictionary of model-specific parameters (optional)
                - validationSplit: Fraction for validation split (default: 0.2)
                - splitMethod: "random" (default) or "time_based" — for time-based split,
                            the earliest (1 - validationSplit) fraction of rows (sorted by
                            dateColumn) is used for training and the latest fraction for
                            validation, with no shuffling.
                - dateColumn: Name of the date/timestamp column to sort by (required when
                            splitMethod is "time_based")
                - hyperparameterOptimization: "none" (default), "random_search", "grid_search",
                            or "bayesian_optimization" — searches a curated per-model-type space
                            (see hyperparameter_spaces.py) instead of a single fixed-params fit.
                            Any key already set in modelParameters is treated as fixed and
                            excluded from the search.
                - optimizationConfig: Optional dict of search overrides — scoring, cvFolds,
                            nIter (random search), nTrials (bayesian), timeoutSeconds (bayesian),
                            gridPoints (grid search resolution per param).
                - scalingMethod: Feature scaling for numeric feature columns - "none",
                            "standard", "minmax", "maxabs", "robust", or "auto" (default:
                            "auto"). "auto" picks "none" for tree-based model types and
                            otherwise "robust" or "standard" depending on outliers in the
                            training data.
                - taskType: "auto" (default), "classification", or "regression". "auto"
                            infers the task from the target column's dtype/cardinality.
                            An explicit value overrides that inference for model types
                            that support both (e.g. xgboost, random_forest,
                            neural_network); it's rejected if it conflicts with a model
                            type that only supports one task (linear_regression,
                            logistic_regression).
                - outlierHandling: Optional list of per-column outlier handling specs,
                            each a dict with: columnName (required), strategy
                            ("no_action" (default), "remove_outliers", or
                            "cap_outliers"), method ("iqr" (default) or "zscore"),
                            iqrMultiplier (default 1.5), zScoreThreshold (default 3).
                            Bounds are computed from the training split only (never
                            the validation split). "cap_outliers" clips both
                            splits to them; "remove_outliers" drops outlier rows
                            from the training split only, so validation metrics
                            are still computed on every validation row.
                - categoricalEncoding: Optional list of per-column categorical encoding
                            specs, each a dict with: columnName (required), strategy
                            ("no_action" (default), "one_hot", "label", or "ordinal"),
                            dropFirst (default False, only used by "one_hot"),
                            ordinalMapping (required by "ordinal": a dict mapping raw
                            values to numeric codes). Columns left at "no_action" fall
                            through to the default one-hot pass below. Fitted mappings
                            (categories, codes) come from the training split only and
                            are then applied to validation, never the other way around.
                - missingValueHandling: Optional list of per-column missing-value specs,
                            each a dict with: columnName (required), strategy
                            ("no_action" (default), "drop_column", "drop_rows",
                            "impute_constant", "impute_mean", "impute_median", or
                            "impute_mode"), imputeValue (used by "impute_constant").
                            Columns left at "no_action" fall through to the default
                            median/mode fill below. Impute fill values are computed
                            from the training split only and then applied to
                            validation, never the other way around.
                - featureEngineering: Optional list of derived-feature specs, each a
                            dict with: newColumnName (required), strategy
                            ("custom_expression", "bin_numeric", "polynomial",
                            "datetime_features", "log_transform",
                            "quantile_transform", "power_transform",
                            "math_transform", or "pca"), plus strategy-specific
                            fields (expression / binColumn+numBins+binStrategy
                            ("uniform" equal-width, default, or "quantile"
                            equal-frequency) /
                            polynomialColumns+polynomialDegree /
                            datetimeColumn+datetimeParts (year, month, day,
                            day_of_week, quarter, hour, is_weekend; hour only
                            when the values have a time of day) / sourceColumns,
                            with quantileOutputDistribution+nQuantiles,
                            powerMethod, mathFunction (sin, cos, sqrt, abs,
                            square, cbrt), pcaComponents+pcaStandardize, and
                            replaceSourceColumns). Bin edges, polynomial
                            features, quantiles, power-transform lambdas and PCA
                            components are fit on the training split only and
                            then applied to validation, never the other way
                            around. Missing values are always filled before
                            feature engineering runs. "normalize" and
                            "standardize" (with sourceColumns) are retired -
                            scalingMethod already rescales numeric features - but
                            still run for workflows saved with them, with a
                            warning in the result.
                - targetTransform: Optional dict for training on a ratio of the
                            target instead of its raw value - {"type": "ratio",
                            "baselineColumn": <column name>}. The model is fit on
                            targetColumn / baselineColumn instead of targetColumn
                            directly; predictions are multiplied back by
                            baselineColumn before computing validation metrics, so
                            reported RMSE/MAE/R2 stay in the target's real units.
                            baselineColumn is read from the source data like
                            targetColumn - it does not need to be one of
                            featureColumns. Only supported for regression tasks.
                            Rows where baselineColumn is zero, missing, not a
                            number or infinite are dropped from both splits (an
                            undefined ratio can't be used as a training target),
                            with a warning in the result; if that leaves no
                            training rows the run fails.

        Returns:
            Dictionary with training results and model file path
        """
        try:
            # Extract configuration
            name = config.get("name", "")
            model_type = config.get("modelType", "").lower()
            file_url = config.get("fileUrl")
            target_column = config.get("targetColumn", "")
            feature_columns = config.get("featureColumns", [])
            model_parameters = config.get("modelParameters", {})
            validation_split = config.get("validationSplit", 0.2)
            split_method = config.get("splitMethod", "random")
            date_column = config.get("dateColumn")
            hyperparameter_optimization = config.get("hyperparameterOptimization") or "none"
            optimization_config = config.get("optimizationConfig") or {}
            scaling_method = config.get("scalingMethod", "auto").lower()
            task_type = config.get("taskType", "auto").lower()
            outlier_handling = config.get("outlierHandling", []) or []
            categorical_encoding = config.get("categoricalEncoding", []) or []
            missing_value_handling = config.get("missingValueHandling", []) or []
            feature_engineering = config.get("featureEngineering", []) or []
            target_transform = config.get("targetTransform")

            # Validate required parameters
            if not name:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="name is required for train model node",
                )
            if not model_type:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="modelType is required for train model node",
                )
            if not file_url:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="fileUrl is required for train model node",
                )
            if not target_column:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="targetColumn is required for train model node",
                )
            if not feature_columns or len(feature_columns) == 0:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="featureColumns is required and must not be empty for train model node",
                )
            if split_method not in ("random", "time_based"):
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Invalid splitMethod: {split_method}. Must be 'random' or 'time_based'",
                )
            if split_method == "time_based" and not date_column:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="dateColumn is required when splitMethod is 'time_based'",
                )
            if hyperparameter_optimization not in hpo_module.VALID_METHODS:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=(
                        f"Invalid hyperparameterOptimization: {hyperparameter_optimization}. "
                        f"Must be one of: {', '.join(hpo_module.VALID_METHODS)}"
                    ),
                )
            validation_split = training_checks.check_validation_split(validation_split)
            training_checks.check_columns(target_column, feature_columns)
            optimization_config = training_checks.check_optimization_config(
                hyperparameter_optimization, optimization_config
            )

            # Validate model type
            valid_model_types = list(model_registry.VALID_MODEL_TYPES)
            if model_type not in valid_model_types:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Invalid modelType: {model_type}. Must be one of: {', '.join(valid_model_types)}",
                )

            valid_scaling_methods = ["none", "standard", "minmax", "maxabs", "robust", "auto"]
            if scaling_method not in valid_scaling_methods:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Invalid scalingMethod: {scaling_method}. Must be one of: {', '.join(valid_scaling_methods)}",
                )

            valid_task_types = ["auto", "classification", "regression"]
            if task_type not in valid_task_types:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Invalid taskType: {task_type}. Must be one of: {', '.join(valid_task_types)}",
                )
            if model_type == "linear_regression" and task_type == "classification":
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail="taskType 'classification' is incompatible with modelType 'linear_regression', which only supports regression",
                )
            if model_type == "logistic_regression" and task_type == "regression":
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail="taskType 'regression' is incompatible with modelType 'logistic_regression', which only supports classification",
                )

            valid_outlier_strategies = ["no_action", "remove_outliers", "cap_outliers"]
            valid_outlier_methods = ["iqr", "zscore"]
            for item in outlier_handling:
                if not isinstance(item, dict) or not item.get("columnName"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail="Each outlierHandling entry must be a dict with a 'columnName'",
                    )
                strategy = item.get("strategy", "no_action")
                if strategy not in valid_outlier_strategies:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Invalid outlierHandling strategy: {strategy}. Must be one of: {', '.join(valid_outlier_strategies)}",
                    )
                method = item.get("method", "iqr")
                if method not in valid_outlier_methods:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Invalid outlierHandling method: {method}. Must be one of: {', '.join(valid_outlier_methods)}",
                    )

            valid_encoding_strategies = ["no_action", "one_hot", "label", "ordinal"]
            for item in categorical_encoding:
                if not isinstance(item, dict) or not item.get("columnName"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail="Each categoricalEncoding entry must be a dict with a 'columnName'",
                    )
                strategy = item.get("strategy", "no_action")
                if strategy not in valid_encoding_strategies:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Invalid categoricalEncoding strategy: {strategy}. Must be one of: {', '.join(valid_encoding_strategies)}",
                    )
                if strategy == "ordinal":
                    mapping = item.get("ordinalMapping")
                    if not mapping or not isinstance(mapping, dict):
                        raise AppException(
                            error_key=ErrorKey.INTERNAL_ERROR,
                            error_detail=(
                                f"Ordinal encoding for column '{item.get('columnName')}' has no value order. "
                                "Open the Train Model node, and under Categorical Encoding set the order "
                                "of the column's values (e.g. Low < Medium < High)."
                            ),
                        )
                    bad_positions = [
                        k for k, v in mapping.items()
                        if isinstance(v, bool) or not isinstance(v, (int, float))
                    ]
                    if bad_positions:
                        raise AppException(
                            error_key=ErrorKey.INTERNAL_ERROR,
                            error_detail=(
                                f"Ordinal encoding for column '{item.get('columnName')}': every value needs a "
                                f"numeric position, but {bad_positions[:10]} do not."
                            ),
                        )

            valid_missing_value_strategies = [
                "no_action", "drop_column", "drop_rows",
                "impute_constant", "impute_mean", "impute_median", "impute_mode",
            ]
            for item in missing_value_handling:
                if not isinstance(item, dict) or not item.get("columnName"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail="Each missingValueHandling entry must be a dict with a 'columnName'",
                    )
                strategy = item.get("strategy", "no_action")
                if strategy not in valid_missing_value_strategies:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Invalid missingValueHandling strategy: {strategy}. Must be one of: {', '.join(valid_missing_value_strategies)}",
                    )

            valid_fe_strategies = [
                "custom_expression", "bin_numeric", "polynomial", "datetime_features",
                *ml_utils.COLUMN_TRANSFORM_STRATEGY_LABELS,
                *_RETIRED_FE_STRATEGIES,
            ]
            for item in feature_engineering:
                if not isinstance(item, dict) or not item.get("newColumnName"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail="Each featureEngineering entry must be a dict with a 'newColumnName'",
                    )
                strategy = item.get("strategy")
                if strategy not in valid_fe_strategies:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Invalid featureEngineering strategy: {strategy}. Must be one of: {', '.join(valid_fe_strategies)}",
                    )
                if strategy == "custom_expression" and not item.get("expression"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"featureEngineering entry '{item.get('newColumnName')}' has strategy 'custom_expression' but no expression",
                    )
                if strategy == "bin_numeric" and (not item.get("binColumn") or not item.get("numBins")):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"featureEngineering entry '{item.get('newColumnName')}' has strategy 'bin_numeric' but is missing binColumn or numBins",
                    )
                if strategy == "bin_numeric" and item.get("binStrategy", "uniform") not in ("uniform", "quantile"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"featureEngineering entry '{item.get('newColumnName')}' has invalid binStrategy: {item.get('binStrategy')}. Must be one of: uniform, quantile",
                    )
                if strategy in ("normalize", "standardize") and not item.get("sourceColumns"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"featureEngineering entry '{item.get('newColumnName')}' has strategy '{strategy}' but no sourceColumns",
                    )
                if strategy in ml_utils.COLUMN_TRANSFORM_STRATEGY_LABELS:
                    self._validate_column_transform_config(item)
                if strategy == "datetime_features":
                    self._validate_datetime_features_config(item)
                if strategy == "polynomial" and (not item.get("polynomialColumns") or not item.get("polynomialDegree")):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"featureEngineering entry '{item.get('newColumnName')}' has strategy 'polynomial' but is missing polynomialColumns or polynomialDegree",
                    )

            if target_transform is not None:
                if not isinstance(target_transform, dict):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail="targetTransform must be a dict",
                    )
                if target_transform.get("type") != "ratio":
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail="Invalid targetTransform type. Must be 'ratio'",
                    )
                if not target_transform.get("baselineColumn"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail="targetTransform requires a baselineColumn",
                    )

            # Refuse an oversized search before loading any data. The API
            # checks this too before queueing a job; this covers every other
            # caller (pipelines, the execute API).
            search_plan = hpo_module.check_search_size(
                model_type, model_parameters, hyperparameter_optimization, optimization_config
            )

            # Check if an optional ML library dependency is installed when needed
            if model_type in _OPTIONAL_MODEL_DEPENDENCIES:
                package_name, is_available = _OPTIONAL_MODEL_DEPENDENCIES[model_type]
                if not is_available():
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"{package_name} is not installed. Please install it with: pip install {model_type}",
                    )

            logger.info(f"Training {model_type} model: {name}")

            # Load data from CSV file
            training_progress.report("loading_data", "Loading training data", 5)
            df = await training_data_storage.load_training_csv(file_url, self.state.thread_id)
            # Column types saved by an upstream Preprocessing node (nullable
            # Int64/boolean, string, category, datetime) are converted to the
            # plain dtypes the steps below select on - see
            # normalize_dtypes_for_training.
            df = ml_utils.normalize_dtypes_for_training(df)
            logger.info(f"Loaded {len(df)} rows from {file_url}")
            training_progress.report("preparing", f"Preparing {len(df):,} rows", 15)

            # Validate columns exist
            all_columns = list(df.columns)
            missing_columns = []

            if target_column not in all_columns:
                missing_columns.append(target_column)

            for col in feature_columns:
                if col not in all_columns:
                    missing_columns.append(col)

            if split_method == "time_based" and date_column not in all_columns:
                missing_columns.append(date_column)

            baseline_column = target_transform.get("baselineColumn") if target_transform else None
            if baseline_column and baseline_column not in all_columns:
                missing_columns.append(baseline_column)

            if missing_columns:
                logger.error(f"Columns not found in data: {missing_columns}. Available columns: {all_columns}")
                return {
                    "success": False,
                    "error": f"Columns not found in data: {missing_columns}. Available columns: {all_columns}",
                }
                # raise AppException(
                #     error_key=ErrorKey.INTERNAL_ERROR,
                #     error_detail=f"Columns not found in data: {missing_columns}. Available columns: {all_columns}",
                # )

            # For a time-based split, sort chronologically first so a positional
            # split later puts the earliest rows in train and latest in validation.
            if split_method == "time_based":
                parsed_dates = pd.to_datetime(df[date_column], errors="coerce")
                if parsed_dates.isna().all():
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Could not parse any values in dateColumn '{date_column}' as dates.",
                    )
                df = (
                    df.assign(_sort_date_=parsed_dates)
                    .sort_values("_sort_date_", na_position="last")
                    .drop(columns=["_sort_date_"])
                    .reset_index(drop=True)
                )
                logger.info(f"Sorted {len(df)} rows chronologically by '{date_column}' for time-based split")

            # Prepare features and target
            X = df[feature_columns].copy()
            y = df[target_column].copy()

            # baseline_series backs an optional targetTransform (ratio target) -
            # read from the source data like the target itself, kept in lockstep
            # with X/y through null-filtering and the split below, but never
            # added to X unless the caller also lists it in featureColumns.
            baseline_series = df[baseline_column].copy() if baseline_column else None

            if y.isnull().any():
                logger.warning("Found missing values in target. Dropping rows with missing target values.")
                mask = ~y.isnull()
                X = X[mask]
                y = y[mask]
                if baseline_series is not None:
                    baseline_series = baseline_series[mask]

            # Numbers stored as text ('12.5') are read as numbers - LightGBM
            # and the ratio transform need them, and Task Type "auto" should
            # judge them as numbers, not as one class per distinct text value.
            # An explicit "classification" keeps the values as they are.
            if task_type != "classification":
                y = training_checks.numeric_target(y)

            # Determine if classification or regression, honoring an explicit
            # user override before falling back to inference from the target.
            is_classification = self._is_classification_task(y, model_type, task_type)

            if target_transform is not None and is_classification:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail="targetTransform is only supported for regression tasks",
                )

            training_checks.check_training_data(
                X, y, target_column, is_classification, training_checks.model_label(model_type),
                missing_value_strategies={
                    item.get("columnName"): item.get("strategy")
                    for item in missing_value_handling
                    if isinstance(item, dict)
                },
            )

            # Split BEFORE fitting any preprocessing (imputation medians/modes,
            # one-hot categories) — fitting those on the full dataset would leak
            # validation-row statistics into training, which for a time-based
            # split defeats the entire point (keeping "future" rows out of
            # training rather than just out of the raw feature matrix).
            baseline_train = None
            baseline_val = None
            if validation_split > 0 and validation_split < 1:
                if split_method == "time_based":
                    split_idx = int(len(X) * (1 - validation_split))
                    X_train, X_val = X.iloc[:split_idx].copy(), X.iloc[split_idx:].copy()
                    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
                    if baseline_series is not None:
                        baseline_train = baseline_series.iloc[:split_idx]
                        baseline_val = baseline_series.iloc[split_idx:]
                    logger.info(
                        f"Time-based split on '{date_column}': {len(X_train)} training samples "
                        f"(earliest), {len(X_val)} validation samples (latest)"
                    )
                else:
                    split_arrays = (X, y, baseline_series) if baseline_series is not None else (X, y)
                    try:
                        split_result = train_test_split(
                            *split_arrays, test_size=validation_split, random_state=42,
                            stratify=y if is_classification else None,
                        )
                    except ValueError as split_error:
                        # Stratification needs every class to have at least 2
                        # members. A classification taskType override can be
                        # applied to a target that isn't actually low-cardinality
                        # (e.g. a near-continuous column), which the "auto"
                        # heuristic would never have called classification in
                        # the first place - fall back to an unstratified split
                        # rather than failing the whole training run.
                        if not is_classification:
                            raise
                        logger.warning(
                            f"Stratified split failed ({split_error}); falling back to a "
                            "non-stratified split for this classification target."
                        )
                        split_result = train_test_split(
                            *split_arrays, test_size=validation_split, random_state=42, stratify=None
                        )
                    if baseline_series is not None:
                        X_train, X_val, y_train, y_val, baseline_train, baseline_val = split_result
                    else:
                        X_train, X_val, y_train, y_val = split_result
                    logger.info(f"Split data: {len(X_train)} training samples, {len(X_val)} validation samples")
            else:
                X_train, y_train = X.copy(), y
                X_val, y_val = None, None
                baseline_train = baseline_series
                baseline_val = None
                logger.info(f"Using all {len(X_train)} samples for training (no validation split)")

            # Rows a training step leaves out (outlier removal, unusable
            # ratio-target baselines) - told to the user in the result's
            # "warnings" rather than only logged.
            dropped_row_warnings: List[str] = []

            # Handle outliers — bounds (IQR quartiles or z-score mean/std) are
            # computed from the training split only. Capping applies them to
            # both splits; removal drops training rows only. This must run
            # before imputation/encoding/scaling below since it can change
            # which rows/values those steps see.
            if outlier_handling:
                X_train, y_train, X_val, y_val, baseline_train, baseline_val, outlier_warnings = (
                    self._handle_outliers(
                        X_train, y_train, X_val, y_val, outlier_handling, baseline_train, baseline_val
                    )
                )
                dropped_row_warnings.extend(outlier_warnings)

            # Apply per-column missing-value overrides (drop_column/drop_rows/
            # impute_*). Fill values are computed from the training split
            # only, then applied to validation - see _handle_missing_values.
            # Captured so validation and inference can reuse the exact values
            # fitted from the training split.
            missing_value_fills: Dict[str, Any] = {}
            if missing_value_handling:
                X_train, y_train, X_val, y_val, baseline_train, baseline_val, missing_value_fills = (
                    self._handle_missing_values(
                        X_train, y_train, X_val, y_val, missing_value_handling, baseline_train, baseline_val
                    )
                )

            # Fall through to a default fill for whatever missing values are
            # still left (columns with no explicit override, or explicitly
            # "no_action"). Fit on the training split only, then applied to
            # validation so nothing about the validation distribution leaks
            # into how training data is filled. Checked per-column against
            # both splits: X_train having no NaNs doesn't mean X_val doesn't
            # (e.g. a time-based split can put all the missing rows in the
            # "future" validation portion).
            has_missing = X_train.isnull().any().any() or (
                X_val is not None and X_val.isnull().any().any()
            )
            # Told to the user in the result's "warnings": with no Missing
            # Value Handling configured, this fill used to be silent.
            auto_fill_warnings: List[str] = []
            if has_missing:
                logger.warning("Found missing values in features. Filling with median for numeric and mode for categorical.")
                for col in X_train.columns:
                    # Already has a persisted fill from an explicit per-column
                    # override above - don't recompute/overwrite it here.
                    if col in missing_value_fills:
                        continue
                    missing_count = int(X_train[col].isna().sum()) + (
                        int(X_val[col].isna().sum()) if X_val is not None else 0
                    )
                    if not missing_count:
                        continue
                    if X_train[col].dtype in ['int64', 'float64']:
                        fill_value = X_train[col].median()
                        fill_kind = "median"
                    else:
                        mode_values = X_train[col].mode()
                        fill_value = mode_values[0] if not mode_values.empty else ''
                        fill_kind = "most frequent value"
                    X_train[col].fillna(fill_value, inplace=True)
                    if X_val is not None:
                        X_val[col].fillna(fill_value, inplace=True)
                    missing_value_fills[col] = fill_value
                    auto_fill_warnings.append(
                        f"Column '{col}': {missing_count} empty value(s) filled automatically with the "
                        f"{fill_kind} ({training_checks.format_value(fill_value)}) of the training data. Set Missing Value Handling "
                        "for this column to choose how instead."
                    )

            # A "drop_column" missing-value strategy above removes the column
            # from X_train entirely, but feature_columns (saved to metadata
            # and used by inference to know what raw inputs to collect) was
            # captured up front from config and never reflected that. Without
            # this, inference asks for - and tries to feed the model - a
            # column it was never actually trained on, so every prediction
            # fails on a column-count mismatch.
            feature_columns = [c for c in feature_columns if c in X_train.columns]

            # Apply the ratio target transform, if configured. Rows whose
            # baseline is zero, missing, not a number or infinite are dropped
            # first from both splits - the ratio would be undefined there, and
            # none of those is usable as a training target. y_val_actual keeps
            # the real-unit validation target so _evaluate_model can
            # reconstruct predictions (predicted_ratio * baseline) back to real
            # units before scoring, instead of reporting ratio-scale metrics.
            y_val_actual = None
            if target_transform is not None:
                baseline_train, train_keep, train_reasons = self._check_ratio_baseline(baseline_train)
                if len(train_keep) and not train_keep.any():
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=(
                            f"Every training row has a zero, missing, non-numeric or infinite "
                            f"'{baseline_column}' baseline, so no ratio target can be computed. "
                            "Choose a different baseline column or fix its values."
                        ),
                    )
                if not train_keep.all():
                    X_train, y_train, baseline_train = (
                        X_train[train_keep].reset_index(drop=True),
                        y_train[train_keep].reset_index(drop=True),
                        baseline_train[train_keep].reset_index(drop=True),
                    )
                dropped_by_split = {"training": int((~train_keep).sum()), "validation": 0}
                reason_totals = dict(train_reasons)
                if X_val is not None:
                    baseline_val, val_keep, val_reasons = self._check_ratio_baseline(baseline_val)
                    if len(val_keep) and not val_keep.any():
                        raise AppException(
                            error_key=ErrorKey.INTERNAL_ERROR,
                            error_detail=(
                                f"Every validation row has a zero, missing, non-numeric or infinite "
                                f"'{baseline_column}' baseline, so the model can't be scored. "
                                "Fix the baseline values, change the validation split, or choose a "
                                "different baseline column."
                            ),
                        )
                    if not val_keep.all():
                        X_val, y_val, baseline_val = (
                            X_val[val_keep].reset_index(drop=True),
                            y_val[val_keep].reset_index(drop=True),
                            baseline_val[val_keep].reset_index(drop=True),
                        )
                    dropped_by_split["validation"] = int((~val_keep).sum())
                    reason_totals = {r: reason_totals[r] + val_reasons[r] for r in reason_totals}
                    y_val_actual = y_val.copy()
                    y_val = y_val / baseline_val
                if any(dropped_by_split.values()):
                    dropped_row_warnings.append(
                        _rows_dropped_warning(
                            "Dropped",
                            dropped_by_split,
                            f"whose '{baseline_column}' baseline is "
                            f"{_join_reason_counts(reason_totals)}; a ratio target can't be computed there.",
                        )
                    )
                y_train = y_train / baseline_train
                logger.info(f"Training on ratio target: {target_column} / {baseline_column}")

            # Every classifier is fit on class codes 0..n-1, not the raw
            # labels: XGBoost rejects anything else ("Invalid classes
            # inferred") and MLPClassifier's early stopping fails on text
            # ("ufunc 'isnan' not supported"). Codes come from the classes
            # left in the training split after the split, outlier removal and
            # drop_rows, so they never skip a number; a class seen only in
            # validation can't be scored (and XGBoost/LightGBM/CatBoost reject
            # it in their eval set), so those validation rows are left out
            # with a warning. The labels are saved with the model so
            # inference returns them instead of the codes.
            target_classes: Optional[List[Any]] = None
            fit_parameters = model_parameters
            if is_classification:
                training_checks.check_training_classes(y_train, target_column)
                y_train, y_val, target_classes = training_checks.encode_target_classes(y_train, y_val)
                if y_val is not None and (y_val < 0).any():
                    unseen = y_val < 0
                    auto_fill_warnings.append(
                        f"{int(unseen.sum())} validation row(s) have a '{target_column}' class that "
                        "is not in the training rows, so they were left out of the validation "
                        "metrics."
                    )
                    X_val, y_val = X_val[~unseen], y_val[~unseen]
                    if len(y_val) == 0:
                        X_val, y_val = None, None
                # class_weight keyed by the user's labels must follow the codes.
                fit_parameters = training_checks.remap_class_weight(model_parameters, target_classes)

            # Apply per-column encoding overrides (label/ordinal) and note which
            # columns asked for one-hot without dropping the first category.
            # Mappings are fit on the training split only, then applied to
            # validation - see _encode_categoricals. Runs BEFORE feature
            # engineering so a derived feature can use the encoded numbers
            # (e.g. size * price with size ordinal-encoded to 0/1/2); before,
            # those steps saw the raw text and were skipped. One-hot still
            # runs after, below, since it replaces the source column.
            X_train, X_val, label_encodings, ordinal_encodings, one_hot_no_drop_columns = (
                self._encode_categoricals(X_train, X_val, categorical_encoding)
            )
            mapped_columns = set(label_encodings) | set(ordinal_encodings)

            # Create derived features - bin edges and normalize/standardize
            # statistics are fit on the training split only, then applied to
            # validation - see _engineer_features. Runs before the numeric
            # column capture below so new numeric features get scaled too.
            feature_engineering_steps: List[Dict[str, Any]] = []
            if feature_engineering:
                X_train, X_val, feature_engineering_steps = self._engineer_features(
                    X_train, X_val, feature_engineering, label_encodings, ordinal_encodings
                )

            # Capture the numeric feature columns before one-hot encoding turns
            # categoricals into dummy columns, so scaling below only touches
            # genuinely-numeric original features. Label/ordinal codes are
            # numeric now but were never scaled, so keep them out.
            numeric_feature_columns = [
                c for c in X_train.select_dtypes(include=['int64', 'float64']).columns
                if c not in mapped_columns
            ]

            # One-hot encode whatever categorical columns are left - columns with
            # no explicit categoricalEncoding override, plus ones explicitly set
            # to "one_hot" - using a fitted OneHotEncoder (not pd.get_dummies) and
            # save the encoder(s) and the raw column names they apply to in model
            # metadata. Without this, the saved feature_columns list stays at the
            # original (pre-encoding) names while the model is actually fit on
            # the expanded dummy columns, which breaks inference for any model
            # trained with categorical features. Both encoders below are fit on
            # the training split only; unseen categories at inference/validation
            # map to all-zeros (handle_unknown="ignore") rather than leaking into
            # their vocabulary. Columns configured with dropFirst=False are
            # encoded separately since a single OneHotEncoder can't drop the
            # first category for some columns and keep it for others.
            remaining_categorical_columns = X_train.select_dtypes(include=['object']).columns.tolist()
            no_drop_columns = [c for c in remaining_categorical_columns if c in one_hot_no_drop_columns]
            categorical_columns = [c for c in remaining_categorical_columns if c not in one_hot_no_drop_columns]

            encoder = None
            if categorical_columns:
                logger.info(f"One-hot encoding categorical columns: {categorical_columns}")
                X_train, X_val, encoder = self._fit_one_hot(X_train, X_val, categorical_columns, drop="first")

            encoder_no_drop = None
            if no_drop_columns:
                logger.info(f"One-hot encoding (no drop) categorical columns: {no_drop_columns}")
                X_train, X_val, encoder_no_drop = self._fit_one_hot(X_train, X_val, no_drop_columns, drop=None)

            # Handle boolean columns
            boolean_columns = X_train.select_dtypes(include=['bool']).columns
            if len(boolean_columns) > 0:
                logger.info(f"Converting boolean columns to int: {list(boolean_columns)}")
                X_train[boolean_columns] = X_train[boolean_columns].astype(int)
                if X_val is not None:
                    X_val[boolean_columns] = X_val[boolean_columns].astype(int)

            # Scale numeric features. As with imputation and one-hot encoding
            # above, the scaler is fit on the training split only and applied
            # (not re-fit) to validation, so no validation-distribution
            # statistics leak into training.
            resolved_scaling_method = "none"
            scaler = None
            if numeric_feature_columns:
                resolved_scaling_method = (
                    self._resolve_auto_scaling_method(model_type, X_train, numeric_feature_columns)
                    if scaling_method == "auto" else scaling_method
                )
                if resolved_scaling_method != "none":
                    scaler = self._fit_scaler(resolved_scaling_method)
                    X_train[numeric_feature_columns] = scaler.fit_transform(X_train[numeric_feature_columns])
                    if X_val is not None:
                        X_val[numeric_feature_columns] = scaler.transform(X_val[numeric_feature_columns])
            logger.info(f"Scaling method: requested='{scaling_method}', resolved='{resolved_scaling_method}'")

            # The exact column order the model is actually fit on. label/ordinal
            # encoding above modifies a column's values in place (its position
            # in X_train never changes), but one-hot encoding drops its source
            # columns and appends the new dummy columns at the end - so the
            # final order can differ substantially from feature_columns (the
            # original, pre-encoding order). Persisting the real order lets
            # inference rebuild the exact column layout the model expects,
            # instead of re-deriving a (possibly different) order on its own.
            model_input_columns = list(X_train.columns)

            # Train the model — either a plain single fit with fixed params, or a
            # hyperparameter search over the curated space for this model type.
            # Both run in a worker thread so a long fit never blocks the event
            # loop, and use at most ML_TRAINING_MAX_CORES cores.
            search_metadata = None
            if hyperparameter_optimization != "none":
                # Checks that need the task and the training split (e.g. a
                # scoring metric of the wrong kind), even when there is nothing
                # left to tune.
                training_checks.check_search_against_data(
                    optimization_config, is_classification, len(X_train),
                    is_time_based=(split_method == "time_based"),
                    model_type=model_type, model_parameters=model_parameters,
                )
            if search_plan is not None:
                training_progress.report(
                    "training",
                    f"Training {search_plan['fits']:,} models "
                    f"({search_plan['candidates']:,} parameter combinations x {search_plan['cv_folds']} folds) "
                    f"on {hpo_module.training_cores()} cores",
                    30,
                )
                optimization_result = await asyncio.to_thread(
                    self._run_with_core_limit,
                    hpo_module.optimize_hyperparameters,
                    model_type=model_type,
                    is_classification=is_classification,
                    X_train=X_train,
                    y_train=y_train,
                    method=hyperparameter_optimization,
                    user_params=fit_parameters,
                    opt_config=optimization_config,
                    is_time_based=(split_method == "time_based"),
                    on_trial=lambda done, total: training_progress.report(
                        "training", f"Bayesian optimization: trial {done} of {total}", 30 + 50 * done // max(total, 1)
                    ),
                )
            else:
                optimization_result = None

            if optimization_result is not None:
                model = optimization_result["model"]
                # Record what the search actually used, so it's visible in the
                # saved model metadata/result instead of only implied by defaults.
                model_parameters = {**model_parameters, **optimization_result["best_params"]}
                search_metadata = {**optimization_result["search_metadata"], "best_params": optimization_result["best_params"]}
            else:
                if hyperparameter_optimization != "none":
                    logger.info(
                        f"No tunable hyperparameters available for '{model_type}' "
                        f"(space empty or fully fixed by modelParameters); training with fixed params instead."
                    )
                training_progress.report("training", f"Training the {model_type} model", 30)
                model = await self._train_model(
                    model_type=model_type,
                    X_train=X_train,
                    y_train=y_train,
                    X_val=X_val,
                    y_val=y_val,
                    is_classification=is_classification,
                    model_parameters=fit_parameters,
                )

            # Evaluate model if validation data is available. When a
            # targetTransform is configured, evaluate against the real-unit
            # target (y_val_actual) with predictions reconstructed via
            # baseline_val, so reported metrics are comparable to a model
            # trained directly on the real-unit target.
            metrics = {}
            if X_val is not None and y_val is not None:
                training_progress.report("evaluating", "Evaluating on the validation split", 85)
                metrics = self._evaluate_model(
                    model, X_val,
                    y_val_actual if y_val_actual is not None else y_val,
                    is_classification,
                    reconstruct_baseline=baseline_val if target_transform is not None else None,
                )
                logger.info(f"Validation metrics: {metrics}")

            # Save model to .pkl file (model + metadata payload)
            training_progress.report("saving", "Saving the model", 92)
            model_artifact = await self._save_model(
                model=model,
                name=name,
                thread_id=self.state.thread_id,
                metadata={
                    # Marker used to distinguish "new payload PKL" vs legacy "raw model PKL"
                    "metadata_schema_version": 2,
                    # Three core fields inference can rely on:
                    "feature_columns": feature_columns,
                    "target_column": target_column,
                    "model_type": model_type,
                    "model_parameters": model_parameters,
                    "hyperparameter_optimization": search_metadata,
                    "scaling_method": resolved_scaling_method,
                    "model_input_columns": model_input_columns,
                    **(
                        {"feature_engineering_steps": feature_engineering_steps}
                        if feature_engineering_steps else {}
                    ),
                    **(
                        {"scaler": scaler, "scaled_columns": numeric_feature_columns}
                        if scaler is not None else {}
                    ),
                    **(
                        {"encoder": encoder, "categorical_columns": categorical_columns}
                        if encoder is not None else {}
                    ),
                    **(
                        {"encoder_no_drop": encoder_no_drop, "categorical_columns_no_drop": no_drop_columns}
                        if encoder_no_drop is not None else {}
                    ),
                    **({"label_encodings": label_encodings} if label_encodings else {}),
                    **({"ordinal_encodings": ordinal_encodings} if ordinal_encodings else {}),
                    # Tells inference to feed label/ordinal-encoded values (not
                    # raw text) into the feature-engineering replay. Absent on
                    # models trained before encoding moved ahead of feature
                    # engineering, which keep replaying from raw inputs.
                    "encoding_before_feature_engineering": True,
                    **({"missing_value_fills": missing_value_fills} if missing_value_fills else {}),
                    **({"target_transform": target_transform} if target_transform is not None else {}),
                    # Labels in class-code order: inference maps the model's
                    # 0..n-1 predictions back to these.
                    **({"target_classes": target_classes} if target_classes is not None else {}),
                },
            )

            # Register (create or update) the ml_models row so the ML Model
            # Inference node has a usable pkl_file_id right after training —
            # without this, the pkl only exists on local disk and is never
            # reachable by an inference node (file_not_found).
            # When run as part of an ML Model Pipeline, the pipeline already
            # targets a specific model (run.model_id, threaded through as
            # initial_values["model_id"]) — update that model directly instead
            # of looking one up by the node's own display name, which is
            # usually just the generic "Train Model" label and would silently
            # register the pkl against the wrong (or a stray new) model row.
            categorical_feature_contracts = {
                name: {
                    "values": ml_utils.sanitize_for_json(list(mapping)),
                    "normalize_keys": False,
                }
                for name, mapping in label_encodings.items()
            }
            categorical_feature_contracts.update(
                {
                    name: {
                        "values": ml_utils.sanitize_for_json(list(mapping)),
                        "normalize_keys": True,
                    }
                    for name, mapping in ordinal_encodings.items()
                }
            )
            if encoder is not None:
                categorical_feature_contracts.update(
                    {
                        name: {
                            "values": ml_utils.sanitize_for_json(values.tolist()),
                            "normalize_keys": False,
                        }
                        for name, values in zip(categorical_columns, encoder.categories_)
                    }
                )
            if encoder_no_drop is not None:
                categorical_feature_contracts.update(
                    {
                        name: {
                            "values": ml_utils.sanitize_for_json(values.tolist()),
                            "normalize_keys": False,
                        }
                        for name, values in zip(no_drop_columns, encoder_no_drop.categories_)
                    }
                )
            target_model_id = (self.state.initial_values or {}).get("model_id")
            ml_model_id, pkl_file_id, registration_error, registration_warnings = (
                await self._register_trained_model(
                    name=name,
                    model_type=model_type,
                    feature_columns=feature_columns,
                    target_column=target_column,
                    local_pkl_path=model_artifact["model_file_path"],
                    training_metrics=metrics,
                    target_model_id=target_model_id,
                    target_transform=target_transform,
                    categorical_feature_contracts=categorical_feature_contracts,
                )
            )
            if missing_value_fills:
                auto_fill_warnings.append(
                    "Training-time missing-value fills were stored in the model artifact. They "
                    "are applied at inference only when 'Fill missing inputs with training values' "
                    "is turned on for the model; otherwise a missing input fails the run unless "
                    "the model has a Feature Default for it."
                )

            # Retired strategies still run (so saved workflows and their models
            # keep behaving the same), but the user is told to move off them.
            training_warnings = [
                (
                    f"Feature engineering '{item.get('newColumnName')}' uses the retired "
                    f"'{item.get('strategy')}' strategy. Scaling Method already rescales "
                    "numeric features (fit on the training split only), so this scales the "
                    "same values twice - switch the feature to another strategy or remove it."
                )
                for item in feature_engineering
                if item.get("strategy") in _RETIRED_FE_STRATEGIES
            ]
            training_warnings = (
                dropped_row_warnings + auto_fill_warnings + training_warnings + registration_warnings
            )
            for warning in training_warnings:
                logger.warning(warning)

            # Prepare response
            result = {
                "success": True,
                "model_name": name,
                "model_type": model_type,
                "model_file_path": ml_utils.data_volume_reference(
                    model_artifact["model_file_path"], base=""
                ),
                "model_version": model_artifact["model_version"],
                "target_column": target_column,
                "feature_columns": feature_columns,
                "training_samples": len(X_train),
                "validation_samples": len(X_val) if X_val is not None else 0,
                "scaling_method": resolved_scaling_method,
                "metrics": metrics,
                "ml_model_id": ml_model_id,
                "pkl_file_id": pkl_file_id,
                "model_parameters": model_parameters,
                **(
                    {"missing_value_fills": ml_utils.sanitize_for_json(missing_value_fills)}
                    if missing_value_fills
                    else {}
                ),
                **({"target_transform": target_transform} if target_transform is not None else {}),
                **(
                    {"target_classes": ml_utils.sanitize_for_json(target_classes)}
                    if target_classes is not None else {}
                ),
            }
            if search_metadata:
                result["hyperparameter_optimization"] = search_metadata
            if registration_error:
                result["registration_error"] = registration_error
            if training_warnings:
                result["warnings"] = training_warnings

            logger.info(f"Model training completed successfully: {model_artifact['model_file_path']}")
            return result

        except AppException:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in train model node: {str(e)}", exc_info=True
            )
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=(
                    "Training failed: "
                    + training_checks.describe_training_error(
                        e, training_checks.model_label(str(config.get("modelType") or "").lower())
                    )
                ),
            ) from e

    def _handle_outliers(
        self, X_train, y_train, X_val, y_val, outlier_handling,
        baseline_train=None, baseline_val=None,
    ):
        """
        Cap or remove outliers in numeric feature columns.

        Bounds (IQR quartiles or z-score mean/std) are computed from X_train
        only, then applied to both X_train and X_val — never the other way
        around — so a validation row can never influence where a bound is
        drawn for the training data it's supposed to evaluate.

        "cap_outliers" clips both splits to the bounds. "remove_outliers" drops
        outlier rows from the training split only: the validation split keeps
        every row, so metrics are scored on the data the model will really see
        rather than on a set made easier by removing its hardest rows.

        baseline_train (if given) backs an optional targetTransform ratio
        target - kept row-aligned with X_train through any remove_outliers row
        drops, same as y_train.

        Returns the splits plus a list of user-facing warnings, one per column
        that had training rows removed.
        """
        warnings: List[str] = []
        for item in outlier_handling:
            column = item.get("columnName")
            strategy = item.get("strategy", "no_action")
            if strategy == "no_action" or column not in X_train.columns:
                continue
            if X_train[column].dtype not in ["int64", "float64"]:
                logger.warning(f"Skipping outlier handling for non-numeric column '{column}'")
                continue

            method = item.get("method", "iqr")
            if method == "iqr":
                q1 = X_train[column].quantile(0.25)
                q3 = X_train[column].quantile(0.75)
                iqr = q3 - q1
                multiplier = item.get("iqrMultiplier", 1.5)
                lower_bound = q1 - multiplier * iqr
                upper_bound = q3 + multiplier * iqr
            else:
                mean = X_train[column].mean()
                std = X_train[column].std()
                threshold = item.get("zScoreThreshold", 3)
                lower_bound = mean - threshold * std
                upper_bound = mean + threshold * std

            if strategy == "cap_outliers":
                X_train[column] = X_train[column].clip(lower_bound, upper_bound)
                if X_val is not None:
                    X_val[column] = X_val[column].clip(lower_bound, upper_bound)
            elif strategy == "remove_outliers":
                # Rows with an empty value in the column can't be checked
                # against the bounds and are removed too, as before - but
                # reported separately, since they aren't outliers.
                train_mask = X_train[column].between(lower_bound, upper_bound)
                empty_train = int(X_train[column].isna().sum())
                removed_train = int((~train_mask).sum()) - empty_train
                X_train, y_train = X_train[train_mask].reset_index(drop=True), y_train[train_mask].reset_index(drop=True)
                if baseline_train is not None:
                    baseline_train = baseline_train[train_mask].reset_index(drop=True)
                logger.info(
                    f"Removed {removed_train} training outlier rows from '{column}' using bounds "
                    f"[{lower_bound}, {upper_bound}] ({method}); validation rows are kept"
                )
                if removed_train:
                    warnings.append(
                        _rows_dropped_warning(
                            "Removed", {"training": removed_train}, f"with outliers in '{column}' ({method})"
                        )
                    )
                if empty_train:
                    warnings.append(
                        _rows_dropped_warning(
                            "Removed",
                            {"training": empty_train},
                            f"with an empty '{column}'; Remove outliers can't check them against the bounds",
                        )
                    )

        return X_train, y_train, X_val, y_val, baseline_train, baseline_val, warnings

    @staticmethod
    def _check_ratio_baseline(baseline: pd.Series):
        """
        Classify a ratio-target baseline split. Returns (numeric baseline,
        keep mask, counts per reason) - a row is kept only when its baseline
        is a finite, non-zero number. Reasons, each row counted once:
        "missing" (empty or blank text), "not a number" (text that doesn't
        parse, or true/false), "infinite" (+/-inf) and "zero". Same rules as
        the inference node's _validated_ratio_baseline_values, so a row
        training accepts is one inference accepts too.
        """
        blank = baseline.map(lambda v: isinstance(v, str) and not v.strip()).astype(bool)
        is_bool = baseline.map(lambda v: isinstance(v, (bool, np.bool_))).astype(bool)
        numeric = pd.to_numeric(baseline.where(~blank & ~is_bool), errors="coerce").astype(float)
        missing = baseline.isna() | blank
        not_a_number = numeric.isna() & ~missing
        infinite = np.isinf(numeric)
        zero = numeric == 0
        keep = np.isfinite(numeric) & (numeric != 0)
        reasons = {
            "zero": int(zero.sum()),
            "missing": int(missing.sum()),
            "not a number": int(not_a_number.sum()),
            "infinite": int(infinite.sum()),
        }
        return numeric, keep, reasons

    def _encode_categoricals(self, X_train, X_val, categorical_encoding):
        """
        Apply per-column categorical encoding overrides before the default
        one-hot pass that follows this call.

        - "label": category -> integer code, fit on X_train's categories only;
          an unseen category in X_val maps to -1 rather than leaking a
          validation-only category into the training vocabulary.
        - "ordinal": a fixed, caller-supplied mapping - safe to apply to both
          splits directly since nothing is fit from the data.
        - "one_hot": left as an object column here; it's one-hot encoded by
          the default pass below (grouped by its dropFirst setting) so the
          fitted encoder can be persisted in model metadata for inference.

        Returns the (possibly mutated) X_train/X_val, the fitted label/ordinal
        mappings (for model metadata), and the set of columns that asked for
        one-hot encoding without dropping the first category.
        """
        label_encodings: Dict[str, Dict[Any, int]] = {}
        ordinal_encodings: Dict[str, Dict[Any, Any]] = {}
        one_hot_no_drop_columns = set()

        for item in categorical_encoding:
            column = item.get("columnName")
            strategy = item.get("strategy", "no_action")
            if strategy == "no_action":
                continue
            if column not in X_train.columns:
                logger.warning(
                    f"Skipping {strategy} encoding for '{column}': it is not one of the feature "
                    "columns (or was dropped earlier)"
                )
                continue

            if strategy == "one_hot":
                if not item.get("dropFirst", False):
                    one_hot_no_drop_columns.add(column)
                continue

            if strategy == "label":
                categories = X_train[column].astype("category").cat.categories
                mapping = {category: code for code, category in enumerate(categories)}
                label_encodings[column] = mapping
                X_train[column] = X_train[column].map(mapping).astype(int)
                if X_val is not None:
                    X_val[column] = X_val[column].map(mapping).fillna(-1).astype(int)

            elif strategy == "ordinal":
                # Keys come from JSON (always strings) while values may be
                # numbers or text with stray spaces - normalize both sides the
                # same way so e.g. 2 and "2", or " High" and "High", match.
                mapping = {
                    ml_utils.ordinal_key(k): v
                    for k, v in (item.get("ordinalMapping") or {}).items()
                }
                splits = [("training", X_train)] + ([("validation", X_val)] if X_val is not None else [])
                encoded = {}
                for split_name, split in splits:
                    keys = split[column].map(ml_utils.ordinal_key)
                    unmapped = sorted({k for k in keys.dropna().unique() if k not in mapping})
                    if unmapped:
                        # Never silently turn a value into "missing": an
                        # unmapped value means the configured order is
                        # incomplete, and training on NaNs would hide that.
                        raise AppException(
                            error_key=ErrorKey.INTERNAL_ERROR,
                            error_detail=(
                                f"Ordinal encoding for column '{column}': {len(unmapped)} value(s) in the "
                                f"{split_name} data have no position in the configured order: "
                                f"{unmapped[:10]}{' ...' if len(unmapped) > 10 else ''}. "
                                f"Configured order: {list(mapping)}. Add the missing values to the "
                                "order in the Train Model node."
                            ),
                        )
                    encoded[split_name] = keys.map(mapping).astype("float64")
                ordinal_encodings[column] = mapping
                X_train[column] = encoded["training"]
                if X_val is not None:
                    X_val[column] = encoded["validation"]
                logger.info(f"Ordinal-encoded '{column}' using order {mapping}")

        return X_train, X_val, label_encodings, ordinal_encodings, one_hot_no_drop_columns

    def _fit_one_hot(self, X_train, X_val, columns, drop):
        """Fit a OneHotEncoder on X_train[columns] only and apply it to both splits."""
        encoder = OneHotEncoder(drop=drop, handle_unknown="ignore", sparse_output=False)
        encoded_train = encoder.fit_transform(X_train[columns])
        encoded_columns = encoder.get_feature_names_out(columns).tolist()
        X_train = pd.concat(
            [
                X_train.drop(columns=columns).reset_index(drop=True),
                pd.DataFrame(encoded_train, columns=encoded_columns),
            ],
            axis=1,
        )
        if X_val is not None:
            encoded_val = encoder.transform(X_val[columns])
            X_val = pd.concat(
                [
                    X_val.drop(columns=columns).reset_index(drop=True),
                    pd.DataFrame(encoded_val, columns=encoded_columns),
                ],
                axis=1,
            )
        return X_train, X_val, encoder

    def _handle_missing_values(
        self, X_train, y_train, X_val, y_val, missing_value_handling,
        baseline_train=None, baseline_val=None,
    ):
        """
        Apply per-column missing-value overrides.

        Fill values (mean/median/mode) are computed from X_train only, then
        applied to X_val - never the other way around - so a validation row
        can never influence how a missing training value gets filled.

        baseline_train/baseline_val (if given) back an optional targetTransform
        ratio target - kept row-aligned with X_train/X_val through any
        drop_rows row drops, same as y_train/y_val.

        Returns the (possibly mutated) splits plus a per-column fill dict
        (constant/mean/median/mode value actually used), for model metadata -
        inference reapplies the same fill instead of defaulting to 0.
        """
        fills: Dict[str, Any] = {}
        for item in missing_value_handling:
            column = item.get("columnName")
            strategy = item.get("strategy", "no_action")
            if strategy == "no_action" or column not in X_train.columns:
                continue

            if strategy == "drop_column":
                X_train = X_train.drop(columns=[column])
                if X_val is not None and column in X_val.columns:
                    X_val = X_val.drop(columns=[column])
            elif strategy == "drop_rows":
                train_mask = X_train[column].notna()
                X_train, y_train = (
                    X_train[train_mask].reset_index(drop=True),
                    y_train[train_mask].reset_index(drop=True),
                )
                if baseline_train is not None:
                    baseline_train = baseline_train[train_mask].reset_index(drop=True)
                if X_val is not None:
                    val_mask = X_val[column].notna()
                    X_val, y_val = (
                        X_val[val_mask].reset_index(drop=True),
                        y_val[val_mask].reset_index(drop=True),
                    )
                    if baseline_val is not None:
                        baseline_val = baseline_val[val_mask].reset_index(drop=True)
            elif strategy == "impute_constant":
                fill_value = self._coerce_fill_value(X_train[column], item.get("imputeValue", 0))
                X_train[column] = self._fill_missing(X_train[column], fill_value)
                if X_val is not None:
                    X_val[column] = self._fill_missing(X_val[column], fill_value)
                fills[column] = fill_value
            elif strategy in ("impute_mean", "impute_median", "impute_mode"):
                if strategy == "impute_mean":
                    fill_value = X_train[column].mean()
                elif strategy == "impute_median":
                    fill_value = X_train[column].median()
                else:
                    mode_values = X_train[column].mode()
                    fill_value = mode_values[0] if not mode_values.empty else None
                X_train[column] = self._fill_missing(X_train[column], fill_value)
                if X_val is not None:
                    X_val[column] = self._fill_missing(X_val[column], fill_value)
                fills[column] = fill_value

        return X_train, y_train, X_val, y_val, baseline_train, baseline_val, fills

    @staticmethod
    def _coerce_fill_value(series: pd.Series, fill_value: Any) -> Any:
        """Match a constant fill value to its column's type.

        The value comes from a text box, so a numeric column often gets "0"
        or "2.5" as a string - filling with that would turn the column into
        mixed text/numbers (object), dropping it out of scaling and outlier
        handling and sending it to one-hot encoding instead.
        """
        if isinstance(fill_value, str) and pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            try:
                number = float(fill_value.strip())
            except ValueError:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=(
                        f"Missing-value fill '{fill_value}' for numeric column '{series.name}' "
                        "is not a number"
                    ),
                )
            return int(number) if number.is_integer() and pd.api.types.is_integer_dtype(series) else number
        return fill_value

    @staticmethod
    def _fill_missing(series: pd.Series, fill_value: Any) -> pd.Series:
        """fillna without pandas' "Downcasting object dtype arrays" FutureWarning.

        On an object column, fillna silently downcasts the result (e.g. to
        int) and warns that this will stop in a future version. Opting in to
        the future behavior and inferring the dtype explicitly gives the same
        result today without the warning, and keeps working after pandas
        changes the default.
        """
        try:
            with pd.option_context("future.no_silent_downcasting", True):
                filled = series.fillna(fill_value)
        except (KeyError, AttributeError):
            # pandas < 2.2 has no such option (and doesn't warn either).
            filled = series.fillna(fill_value)
        return filled.infer_objects()

    def _engineer_features(
        self, X_train, X_val, feature_engineering, label_encodings=None, ordinal_encodings=None
    ):
        """
        Create derived features from existing columns.

        Bin edges (bin_numeric), polynomial features and (retired)
        normalize/standardize statistics are computed from X_train only, then
        applied to X_val - never the other way around. custom_expression and polynomial don't fit anything from
        the data (a deterministic per-row formula and a fixed-degree feature
        map, respectively), so leakage isn't a concern for those, but they
        live here too so all feature configuration lives in one place.

        Also returns a list of replay steps - everything inference needs to
        recompute these same derived columns from a raw input row (the fitted
        bin edges / mean+std / PolynomialFeatures transformer, not just the
        config), since without it inference has no way to reconstruct columns
        the model was actually trained on.

        label_encodings/ordinal_encodings are the mappings already applied to
        those columns - a Custom Expression comparing one to text has the text
        translated to its code (see translate_category_literals).
        """
        steps: List[Dict[str, Any]] = []

        for item in feature_engineering:
            strategy = item.get("strategy")
            new_col = item.get("newColumnName")

            if strategy == "custom_expression":
                expression = item.get("expression")
                # DataFrame.eval() only exposes column references and basic
                # arithmetic/comparison operators (via numexpr/Python parser)
                # - no access to builtins or arbitrary Python, unlike eval().
                # Columns are referenced by name; the older df["col"] form is
                # rewritten to that first (see normalize_feature_expression).
                eval_expression = ml_utils.normalize_feature_expression(expression)
                try:
                    # Label/ordinal columns hold codes by now, so size == "High"
                    # would be False on every row - compare against the code.
                    eval_expression = ml_utils.translate_category_literals(
                        eval_expression, label_encodings or {}, ordinal_encodings or {}
                    )
                except ValueError as e:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Feature engineering '{new_col}': the expression `{expression}` {e}.",
                    ) from e
                try:
                    X_train[new_col] = X_train.eval(eval_expression)
                    if X_val is not None:
                        X_val[new_col] = X_val.eval(eval_expression)
                except Exception as e:
                    # Fail instead of skipping: a skipped feature used to
                    # train a "successful" model silently missing a column
                    # the user configured.
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=(
                            f"Feature engineering '{new_col}': the expression `{expression}` could not "
                            f"be evaluated ({e}). Reference columns by name, e.g. price * quantity "
                            "(use `backticks` for a name with spaces, e.g. `unit price` * quantity)."
                        ),
                    ) from e
                steps.append({
                    "strategy": "custom_expression",
                    "new_col": new_col,
                    "expression": eval_expression,
                })

            elif strategy == "bin_numeric":
                bin_column = item.get("binColumn")
                num_bins = item.get("numBins")
                bin_strategy = item.get("binStrategy", "uniform")
                if bin_column not in X_train.columns or not pd.api.types.is_numeric_dtype(X_train[bin_column]):
                    logger.warning(f"Skipping bin_numeric for '{new_col}': column '{bin_column}' not found or not numeric")
                    continue
                if bin_strategy == "quantile":
                    # Equal-frequency edges from train percentiles. Heavily
                    # repeated values (e.g. many zeros) collapse duplicate
                    # edges, leaving fewer bins than requested.
                    _, bin_edges = pd.qcut(X_train[bin_column], q=num_bins, retbins=True, duplicates="drop")
                    if len(bin_edges) < 2:
                        logger.warning(f"Skipping bin_numeric for '{new_col}': column '{bin_column}' has too few distinct values for quantile bins")
                        continue
                else:
                    _, bin_edges = pd.cut(X_train[bin_column], bins=num_bins, retbins=True, duplicates="drop")
                X_train[new_col] = pd.cut(
                    X_train[bin_column], bins=bin_edges, labels=False, include_lowest=True
                )
                if X_val is not None:
                    # Clip to the train-derived range first so a val value
                    # outside it still gets binned instead of becoming NaN.
                    clipped = X_val[bin_column].clip(lower=bin_edges[0], upper=bin_edges[-1])
                    X_val[new_col] = pd.cut(clipped, bins=bin_edges, labels=False, include_lowest=True)
                steps.append({
                    "strategy": "bin_numeric",
                    "new_col": new_col,
                    "bin_column": bin_column,
                    "bin_strategy": bin_strategy,
                    "bin_edges": list(bin_edges),
                })

            elif strategy in ("normalize", "standardize"):
                source_columns = [
                    c for c in (item.get("sourceColumns") or [])
                    if c in X_train.columns and pd.api.types.is_numeric_dtype(X_train[c])
                ]
                column_stats: Dict[str, Dict[str, float]] = {}
                for col in source_columns:
                    out_col = new_col if len(source_columns) == 1 else f"{new_col}_{col}"
                    if strategy == "normalize":
                        min_val, max_val = X_train[col].min(), X_train[col].max()
                        if max_val == min_val:
                            continue
                        X_train[out_col] = (X_train[col] - min_val) / (max_val - min_val)
                        if X_val is not None:
                            X_val[out_col] = (X_val[col] - min_val) / (max_val - min_val)
                        column_stats[col] = {"out_col": out_col, "min": float(min_val), "max": float(max_val)}
                    else:
                        mean_val, std_val = X_train[col].mean(), X_train[col].std()
                        if std_val == 0:
                            continue
                        X_train[out_col] = (X_train[col] - mean_val) / std_val
                        if X_val is not None:
                            X_val[out_col] = (X_val[col] - mean_val) / std_val
                        column_stats[col] = {"out_col": out_col, "mean": float(mean_val), "std": float(std_val)}
                if column_stats:
                    steps.append({
                        "strategy": strategy,
                        "new_col": new_col,
                        "column_stats": column_stats,
                    })

            elif strategy == "polynomial":
                poly_columns = [
                    c for c in (item.get("polynomialColumns") or [])
                    if c in X_train.columns and pd.api.types.is_numeric_dtype(X_train[c])
                ]
                if not poly_columns:
                    logger.warning(f"Skipping polynomial for '{new_col}': no valid numeric polynomialColumns")
                    continue
                degree = item.get("polynomialDegree", 2)
                poly = PolynomialFeatures(degree=degree, include_bias=False)
                train_poly = poly.fit_transform(X_train[poly_columns])
                poly_names = poly.get_feature_names_out(poly_columns).tolist()
                # Skip the first len(poly_columns) outputs - those are just the
                # original columns echoed back by PolynomialFeatures, already
                # present in X_train/X_val.
                new_names = [f"{new_col}_{n}" for n in poly_names[len(poly_columns):]]
                new_train_cols = pd.DataFrame(
                    train_poly[:, len(poly_columns):], columns=new_names, index=X_train.index
                )
                X_train = pd.concat([X_train, new_train_cols], axis=1)
                if X_val is not None:
                    val_poly = poly.transform(X_val[poly_columns])
                    new_val_cols = pd.DataFrame(
                        val_poly[:, len(poly_columns):], columns=new_names, index=X_val.index
                    )
                    X_val = pd.concat([X_val, new_val_cols], axis=1)
                steps.append({
                    "strategy": "polynomial",
                    "new_col": new_col,
                    "poly_columns": poly_columns,
                    "poly": poly,
                    "new_names": new_names,
                })

            elif strategy in ml_utils.COLUMN_TRANSFORM_STRATEGY_LABELS:
                X_train, X_val, step = self._apply_column_transform(X_train, X_val, item)
                steps.append(step)

            elif strategy == "datetime_features":
                X_train, X_val, step = self._apply_datetime_features(X_train, X_val, item, label_encodings, ordinal_encodings)
                steps.append(step)

        return X_train, X_val, steps

    @staticmethod
    def _validate_datetime_features_config(item: Dict[str, Any]) -> None:
        """Config checks for Date-Time Features, before any data is loaded."""
        name = item.get("newColumnName")

        def fail(problem: str) -> None:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Feature engineering '{name}' (Date-Time Features): {problem}",
            )

        if not item.get("datetimeColumn"):
            fail("choose the date/time column")
        parts = item.get("datetimeParts")
        if parts is not None:
            if not isinstance(parts, list) or not parts:
                fail("choose at least one part (e.g. year, month)")
            unknown = [p for p in parts if p not in ml_utils.DATETIME_PARTS]
            if unknown:
                fail(f"unknown part(s) {unknown} - choose from {', '.join(ml_utils.DATETIME_PARTS)}")

    def _apply_datetime_features(self, X_train, X_val, item, label_encodings=None, ordinal_encodings=None):
        """Date-Time Features: calendar parts of one date/time column.

        Nothing is fitted - each part is read from the row's own date - so
        there's no leakage. The parts chosen (all by default) become numeric
        columns <newColumnName>_<part>; "hour" is left out when no training
        value has a time of day. The date/time column itself is removed from
        what the model trains on (one-hot encoding raw timestamps would make a
        column per distinct value), but it is still collected as a raw input
        at inference, where the same parts are recomputed.
        """
        column = item.get("datetimeColumn")
        new_col = item.get("newColumnName")

        def fail(problem: str) -> None:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Feature engineering '{new_col}' (Date-Time Features): {problem}",
            )

        if column not in X_train.columns:
            fail(f"column '{column}' not found - it must be one of the feature columns")
        if column in (label_encodings or {}) or column in (ordinal_encodings or {}):
            fail(f"column '{column}' has a label or ordinal Categorical Encoding - remove it to use its dates")
        if pd.api.types.is_numeric_dtype(X_train[column]) or pd.api.types.is_bool_dtype(X_train[column]):
            fail(f"column '{column}' holds numbers, not dates or times (e.g. 2024-03-15 or 2024-03-15 14:30)")

        splits = {"training": X_train, "validation": X_val}
        # One day/month order for the whole column (both splits), saved with
        # the step so prediction reads values like 01/02/2024 the same way.
        all_values = pd.concat([split[column] for split in splits.values() if split is not None])
        date_order = ml_utils.numeric_date_order(all_values)
        if date_order["order"] == "mixed":
            fail(
                f"'{column}' mixes day-first and month-first dates, e.g. "
                f"{date_order['day_first_example']!r} (day first) and "
                f"{date_order['month_first_example']!r} (month first) - write them all one way, "
                f"ideally as YYYY-MM-DD"
            )
        if date_order["order"] == "ambiguous":
            fail(
                f"the dates in '{column}' (e.g. 01/02/2024) could be day-first or month-first, and no value "
                f"shows which - write them as YYYY-MM-DD, or include a date with a day over 12"
            )
        day_first = date_order["order"] == "day_first"
        parsed = {
            name: ml_utils.parse_datetime_values(split[column], day_first=day_first).set_axis(split.index)
            for name, split in splits.items() if split is not None
        }
        for name, values in parsed.items():
            unreadable = values.isna()
            if unreadable.any():
                example = splits[name][column][unreadable].iloc[0]
                fail(
                    f"{int(unreadable.sum())} value(s) of '{column}' in the {name} data could not be read "
                    f"as a date/time, e.g. {example!r}"
                )

        parts = list(dict.fromkeys(item.get("datetimeParts") or ml_utils.DATETIME_PARTS))
        if "hour" in parts and not ml_utils.has_time_of_day(parsed["training"]):
            logger.info(f"Date-Time Features '{new_col}': '{column}' has no time of day, so no hour feature")
            parts.remove("hour")
        if not parts:
            fail(f"only the hour was chosen, but the values of '{column}' have no time of day")

        output_columns = [f"{new_col}_{part}" for part in parts]
        kept_columns = [c for c in X_train.columns if c != column]
        clashes = [c for c in output_columns if c in kept_columns]
        if clashes:
            fail(f"output column(s) {clashes} already exist - choose another New Column Name")

        def with_parts(split, dates):
            new = pd.DataFrame(
                {out: ml_utils.datetime_part_values(dates, part) for out, part in zip(output_columns, parts)},
                index=split.index,
            )
            return pd.concat([split[kept_columns], new], axis=1)

        X_train = with_parts(X_train, parsed["training"])
        if X_val is not None:
            X_val = with_parts(X_val, parsed["validation"])

        return X_train, X_val, {
            "strategy": "datetime_features",
            "new_col": new_col,
            "column": column,
            "parts": parts,
            "output_columns": output_columns,
            "day_first": day_first,
        }

    @staticmethod
    def _validate_column_transform_config(item: Dict[str, Any]) -> None:
        """Config checks for log/quantile/power/math/PCA features, before any data is loaded."""
        strategy = item.get("strategy")
        label = ml_utils.COLUMN_TRANSFORM_STRATEGY_LABELS[strategy]
        name = item.get("newColumnName")

        def fail(problem: str) -> None:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Feature engineering '{name}' ({label}): {problem}",
            )

        columns = item.get("sourceColumns") or []
        if not columns:
            fail("choose at least one column")
        if strategy == "pca":
            if len(set(columns)) < 2:
                fail("choose at least 2 columns to combine")
            components = item.get("pcaComponents", 2)
            is_count = isinstance(components, int) and not isinstance(components, bool)
            is_share = isinstance(components, float) and 0 < components < 1
            if not (is_count and components >= 1) and not is_share:
                fail(
                    "number of components must be a whole number of 1 or more, or a share of "
                    f"variance to keep between 0 and 1 (e.g. 0.95) - got {components!r}"
                )
            if is_count and components > len(set(columns)):
                fail(f"asks for {components} components from only {len(set(columns))} columns")
        if strategy == "math_transform" and item.get("mathFunction") not in ml_utils.MATH_FUNCTIONS:
            fail(
                f"function must be one of {', '.join(ml_utils.MATH_FUNCTIONS)} - got {item.get('mathFunction')!r}"
            )
        if strategy == "power_transform" and item.get("powerMethod", "yeo-johnson") not in ("yeo-johnson", "box-cox"):
            fail(f"method must be 'yeo-johnson' or 'box-cox' - got {item.get('powerMethod')!r}")
        if strategy == "quantile_transform":
            if item.get("quantileOutputDistribution", "uniform") not in ("uniform", "normal"):
                fail(
                    "output distribution must be 'uniform' or 'normal' - "
                    f"got {item.get('quantileOutputDistribution')!r}"
                )
            n_quantiles = item.get("nQuantiles", 1000)
            if not isinstance(n_quantiles, int) or isinstance(n_quantiles, bool) or n_quantiles < 2:
                fail(f"number of quantiles must be a whole number of 2 or more - got {n_quantiles!r}")

    def _apply_column_transform(self, X_train, X_val, item):
        """Log Transform, Quantile Transformer, Power Transformer, Math
        Function (sin, cos, sqrt, ...) or PCA on numeric source columns.

        Anything fitted (quantiles, power lambdas, PCA components and the
        optional pre-PCA scaling) is fit on X_train only and applied to
        X_val. Missing values were already filled before feature
        engineering; empty or infinite values here can only come from an
        earlier feature step (e.g. a division by zero), and fail clearly
        instead of erroring inside scikit-learn.

        Output: one new column per source (named newColumnName for a single
        source, newColumnName_<source> for several), or newColumnName_1..k
        for PCA. replaceSourceColumns (default: on for PCA, off otherwise)
        removes the source columns from what the model is trained on - they
        are still collected as raw inputs at inference, since the transform
        needs them.
        """
        strategy = item["strategy"]
        label = ml_utils.COLUMN_TRANSFORM_STRATEGY_LABELS[strategy]
        new_col = item.get("newColumnName")
        columns = list(dict.fromkeys(item.get("sourceColumns") or []))
        power_method = item.get("powerMethod", "yeo-johnson")
        math_function = item.get("mathFunction") if strategy == "math_transform" else None

        def fail(problem: str) -> None:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Feature engineering '{new_col}' ({label}): {problem}",
            )

        not_found = [c for c in columns if c not in X_train.columns]
        if not_found:
            fail(
                f"column(s) {not_found} not found - they must be feature columns, or created by "
                "an earlier feature engineering step"
            )
        not_numeric = [
            c for c in columns
            if not pd.api.types.is_numeric_dtype(X_train[c]) or pd.api.types.is_bool_dtype(X_train[c])
        ]
        if not_numeric:
            fail(f"needs numeric columns, but {not_numeric} are not numeric")

        splits = {"training": X_train, "validation": X_val}
        matrices = {
            name: split[columns].astype(float).to_numpy()
            for name, split in splits.items() if split is not None
        }
        for name, values in matrices.items():
            problem = ml_utils.column_transform_value_problem(strategy, values, columns, power_method, math_function)
            if problem:
                if problem.startswith("empty or infinite"):
                    problem = (
                        f"{problem} in the {name} data. Missing values are filled before feature "
                        "engineering, so these come from an earlier feature engineering step "
                        "(e.g. a division by zero)"
                    )
                else:
                    problem = f"{problem} (in the {name} data)"
                fail(problem)

        train_values = matrices["training"]
        transformer = None
        extra: Dict[str, Any] = {}
        if strategy == "quantile_transform":
            transformer = QuantileTransformer(
                n_quantiles=min(item.get("nQuantiles", 1000), len(train_values)),
                output_distribution=item.get("quantileOutputDistribution", "uniform"),
                random_state=0,
            ).fit(train_values)
        elif strategy == "power_transform":
            # standardize=False: Scaling Method already standardizes numeric
            # features afterwards; doing it here too would scale twice.
            transformer = PowerTransformer(method=power_method, standardize=False).fit(train_values)
        elif strategy == "pca":
            components = item.get("pcaComponents", 2)
            if isinstance(components, int) and components > min(len(columns), len(train_values)):
                fail(f"asks for {components} components, but there are only {len(train_values)} training rows")
            pipeline_steps = [("scale", StandardScaler())] if item.get("pcaStandardize", True) else []
            pipeline_steps.append(("pca", PCA(n_components=components, random_state=0)))
            transformer = Pipeline(pipeline_steps).fit(train_values)
            extra["explained_variance_ratio"] = [
                float(v) for v in transformer.named_steps["pca"].explained_variance_ratio_
            ]

        transformed = {
            name: ml_utils.apply_column_transform(strategy, transformer, values, math_function)
            for name, values in matrices.items()
        }
        if strategy == "math_transform":
            for name, values in transformed.items():
                problem = ml_utils.column_transform_output_problem(values, columns)
                if problem:
                    fail(f"{problem} (in the {name} data)")
        if strategy == "pca":
            output_columns = [f"{new_col}_{i + 1}" for i in range(transformed["training"].shape[1])]
        elif len(columns) == 1:
            output_columns = [new_col]
        else:
            output_columns = [f"{new_col}_{c}" for c in columns]

        replace = bool(item.get("replaceSourceColumns", strategy == "pca"))
        kept_columns = [c for c in X_train.columns if not (replace and c in columns)]
        clashes = [c for c in output_columns if c in kept_columns]
        if clashes:
            fail(f"output column(s) {clashes} already exist - choose another New Column Name")

        def with_outputs(split, values):
            base = split[kept_columns]
            new = pd.DataFrame(values, columns=output_columns, index=split.index)
            return pd.concat([base, new], axis=1)

        X_train = with_outputs(X_train, transformed["training"])
        if X_val is not None:
            X_val = with_outputs(X_val, transformed["validation"])

        return X_train, X_val, {
            "strategy": strategy,
            "new_col": new_col,
            "columns": columns,
            "output_columns": output_columns,
            "transformer": transformer,
            "power_method": power_method if strategy == "power_transform" else None,
            "math_function": math_function,
            "replace_source_columns": replace,
            **extra,
        }

    def _is_classification_task(self, y: pd.Series, model_type: str, task_type: str = "auto") -> bool:
        """
        Determine if this is a classification or regression task.

        Args:
            y: Target variable series
            model_type: Type of model
            task_type: User-selected override - "auto", "classification", or
                       "regression". Ignored for model types that only support
                       one task (validated against those before this is called).

        Returns:
            True if classification, False if regression
        """
        # Some models are inherently classification or regression, regardless
        # of task_type (a conflicting override is rejected earlier in process()).
        if model_type in ml_utils._CLASSIFICATION_ONLY_MODEL_TYPES:
            return True
        # Ridge/Lasso/Elastic Net are regressors too: treating them as
        # classification would fit a regressor on class codes and fail at
        # inference on its decimal predictions.
        if model_type in ml_utils._REGRESSION_ONLY_MODEL_TYPES:
            return False

        # An explicit user selection takes priority over inference.
        if task_type == "classification":
            return True
        if task_type == "regression":
            return False

        # "auto": infer from the target variable
        return ml_utils.is_classification_task(y, model_type)

    def _fit_scaler(self, method: str):
        """Return a fresh, unfitted scaler instance for the given method."""
        return {
            "standard": StandardScaler(),
            "minmax": MinMaxScaler(),
            "maxabs": MaxAbsScaler(),
            "robust": RobustScaler(),
        }[method]

    def _resolve_auto_scaling_method(
        self, model_type: str, X_train: pd.DataFrame, numeric_columns: list
    ) -> str:
        """
        Resolve "auto" feature scaling to a concrete method based on model type
        and the training data's outlier profile.

        Tree-based models are scale-invariant, so scaling is skipped for them.
        Other (distance- or gradient-sensitive) models get Robust scaling when
        the training data has significant outliers, otherwise Standard.
        """
        if model_type in TREE_BASED_MODEL_TYPES:
            return "none"
        return "robust" if self._has_significant_outliers(X_train, numeric_columns) else "standard"

    def _has_significant_outliers(
        self, X_train: pd.DataFrame, numeric_columns: list, threshold: float = 0.05
    ) -> bool:
        """
        True when more than `threshold` fraction of numeric feature values fall
        outside the IQR fence [Q1 - 1.5*IQR, Q3 + 1.5*IQR].
        """
        numeric_df = X_train[numeric_columns]
        q1 = numeric_df.quantile(0.25)
        q3 = numeric_df.quantile(0.75)
        iqr = q3 - q1
        is_outlier = (numeric_df < q1 - 1.5 * iqr) | (numeric_df > q3 + 1.5 * iqr)
        return bool(is_outlier.to_numpy().mean() > threshold) if is_outlier.size else False

    async def _train_model(
        self,
        model_type: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """
        Train a model based on the model type.

        Args:
            model_type: Type of model to train
            X_train: Training features
            y_train: Training target
            X_val: Optional validation features
            y_val: Optional validation target
            is_classification: Whether this is a classification task
            model_parameters: Model-specific parameters

        Returns:
            Trained model
        """
        logger.info(f"Training {model_type} model (classification={is_classification})")
        model_parameters = model_registry.cap_estimator_threads(
            model_type, model_parameters, hpo_module.training_cores()
        )
        return await asyncio.to_thread(
            self._run_with_core_limit,
            self._fit_model,
            model_type,
            X_train,
            y_train,
            X_val,
            y_val,
            is_classification,
            model_parameters,
        )

    @staticmethod
    def _run_with_core_limit(fit, *args, **kwargs):
        """Run fit (in a worker thread) as a tracked fit, under the native thread limit.

        The native (BLAS, OpenMP) limit is process-wide, so it is only set in
        a background training job, which has its worker process to itself.
        Elsewhere (the API process) the estimator thread caps and the
        cross-validation worker caps still apply.
        """
        with training_progress.fitting():
            if not training_progress.in_training_job():
                return fit(*args, **kwargs)
            with hpo_module.native_thread_limit():
                return fit(*args, **kwargs)

    def _fit_model(
        self,
        model_type: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Fit one model with fixed parameters (runs in a worker thread)."""
        if model_type == "xgboost":
            return self._train_xgboost(X_train, y_train, X_val, y_val, is_classification, model_parameters)
        elif model_type == "lightgbm":
            return self._train_lightgbm(X_train, y_train, X_val, y_val, is_classification, model_parameters)
        elif model_type == "catboost":
            return self._train_catboost(X_train, y_train, X_val, y_val, is_classification, model_parameters)
        elif model_type == "random_forest":
            return self._train_random_forest(X_train, y_train, is_classification, model_parameters)
        elif model_type == "extra_trees":
            return self._train_extra_trees(X_train, y_train, is_classification, model_parameters)
        elif model_type == "gradient_boosting":
            return self._train_gradient_boosting(X_train, y_train, is_classification, model_parameters)
        elif model_type == "decision_tree":
            return self._train_decision_tree(X_train, y_train, is_classification, model_parameters)
        elif model_type == "linear_regression":
            return self._train_linear_regression(X_train, y_train, model_parameters)
        elif model_type == "ridge_regression":
            return self._train_ridge_regression(X_train, y_train, model_parameters)
        elif model_type == "lasso_regression":
            return self._train_lasso_regression(X_train, y_train, model_parameters)
        elif model_type == "elastic_net":
            return self._train_elastic_net(X_train, y_train, model_parameters)
        elif model_type == "logistic_regression":
            return self._train_logistic_regression(X_train, y_train, model_parameters)
        elif model_type == "svm":
            return self._train_svm(X_train, y_train, is_classification, model_parameters)
        elif model_type == "knn":
            return self._train_knn(X_train, y_train, is_classification, model_parameters)
        elif model_type == "neural_network":
            return self._train_neural_network(X_train, y_train, is_classification, model_parameters)
        else:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Unsupported model type: {model_type}",
            )

    def _train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train an XGBoost model."""
        default_params = {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = xgb.XGBClassifier(**params)
        else:
            model = xgb.XGBRegressor(**params)

        if X_val is not None and y_val is not None:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        else:
            model.fit(X_train, y_train)

        return model

    def _train_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train a LightGBM model."""
        default_params = {
            "n_estimators": 100,
            "max_depth": -1,
            "learning_rate": 0.1,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = lgb.LGBMClassifier(**params)
        else:
            model = lgb.LGBMRegressor(**params)

        if X_val is not None and y_val is not None:
            model.fit(X_train, y_train, eval_set=[(X_val, y_val)])
        else:
            model.fit(X_train, y_train)

        return model

    def _train_catboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train a CatBoost model."""
        default_params = {
            "iterations": 100,
            "depth": 6,
            "learning_rate": 0.1,
            "random_state": 42,
            "verbose": False,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = CatBoostClassifier(**params)
        else:
            model = CatBoostRegressor(**params)

        if X_val is not None and y_val is not None:
            model.fit(X_train, y_train, eval_set=(X_val, y_val))
        else:
            model.fit(X_train, y_train)

        return model

    def _train_random_forest(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train a Random Forest model."""
        default_params = {
            "n_estimators": 100,
            "max_depth": None,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = RandomForestClassifier(**params)
        else:
            model = RandomForestRegressor(**params)

        model.fit(X_train, y_train)
        return model

    def _train_extra_trees(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train an Extra Trees model."""
        default_params = {
            "n_estimators": 100,
            "max_depth": None,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = ExtraTreesClassifier(**params)
        else:
            model = ExtraTreesRegressor(**params)

        model.fit(X_train, y_train)
        return model

    def _train_gradient_boosting(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train a (sklearn) Gradient Boosting model."""
        default_params = {
            "n_estimators": 100,
            "max_depth": 3,
            "learning_rate": 0.1,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = GradientBoostingClassifier(**params)
        else:
            model = GradientBoostingRegressor(**params)

        model.fit(X_train, y_train)
        return model

    def _train_decision_tree(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train a Decision Tree model."""
        default_params = {
            "max_depth": None,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = DecisionTreeClassifier(**params)
        else:
            model = DecisionTreeRegressor(**params)

        model.fit(X_train, y_train)
        return model

    def _train_linear_regression(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model_parameters: Dict[str, Any],
    ):
        """Train a Linear Regression model."""
        params = {**model_parameters}
        model = LinearRegression(**params)
        model.fit(X_train, y_train)
        return model

    def _train_ridge_regression(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model_parameters: Dict[str, Any],
    ):
        """Train a Ridge Regression model."""
        default_params = {
            "alpha": 1.0,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}
        model = Ridge(**params)
        model.fit(X_train, y_train)
        return model

    def _train_lasso_regression(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model_parameters: Dict[str, Any],
    ):
        """Train a Lasso Regression model."""
        default_params = {
            "alpha": 1.0,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}
        model = Lasso(**params)
        model.fit(X_train, y_train)
        return model

    def _train_elastic_net(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model_parameters: Dict[str, Any],
    ):
        """Train an Elastic Net model."""
        default_params = {
            "alpha": 1.0,
            "l1_ratio": 0.5,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}
        model = ElasticNet(**params)
        model.fit(X_train, y_train)
        return model

    def _train_svm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train a Support Vector Machine model."""
        default_params = {
            "kernel": "rbf",
            "C": 1.0,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = SVC(**params)
        else:
            model = SVR(**params)

        model.fit(X_train, y_train)
        return model

    def _train_knn(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train a K-Nearest Neighbors model."""
        default_params = {
            "n_neighbors": 5,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = KNeighborsClassifier(**params)
        else:
            model = KNeighborsRegressor(**params)

        model.fit(X_train, y_train)
        return model

    def _train_logistic_regression(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model_parameters: Dict[str, Any],
    ):
        """Train a Logistic Regression model."""
        default_params = {
            "max_iter": 1000,
            "random_state": 42,
        }
        params = {**default_params, **model_parameters}
        model = LogisticRegression(**params)
        model.fit(X_train, y_train)
        return model

    def _train_neural_network(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        is_classification: bool,
        model_parameters: Dict[str, Any],
    ):
        """Train a Neural Network (MLP) model."""
        default_params = {
            "hidden_layer_sizes": (100,),
            "max_iter": 500,
            "random_state": 42,
            "early_stopping": True,
            "validation_fraction": 0.1,
        }
        params = {**default_params, **model_parameters}

        if is_classification:
            model = MLPClassifier(**params)
        else:
            model = MLPRegressor(**params)

        model.fit(X_train, y_train)
        return model

    def _evaluate_model(
        self, model, X_val: pd.DataFrame, y_val: pd.Series, is_classification: bool,
        reconstruct_baseline: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate model performance on validation data.

        Args:
            model: Trained model
            X_val: Validation features
            y_val: Validation target. When reconstruct_baseline is given, this
                        must be the real-unit target (not the ratio the model
                        was actually fit on).
            is_classification: Whether this is a classification task
            reconstruct_baseline: If the model was fit on a ratio target
                        (targetTransform), the per-row baseline to multiply
                        predictions by before scoring, so metrics land in the
                        target's real units instead of ratio units.

        Returns:
            Dictionary with evaluation metrics
        """
        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            mean_absolute_error,
            mean_squared_error,
            precision_score,
            r2_score,
            recall_score,
        )

        y_pred = model.predict(X_val)
        if reconstruct_baseline is not None:
            y_pred = y_pred * reconstruct_baseline.values

        if is_classification:
            metrics = {
                "accuracy": float(accuracy_score(y_val, y_pred)),
                "precision": float(precision_score(y_val, y_pred, average='weighted', zero_division=0)),
                "recall": float(recall_score(y_val, y_pred, average='weighted', zero_division=0)),
                "f1_score": float(f1_score(y_val, y_pred, average='weighted', zero_division=0)),
            }
        else:
            mse = float(mean_squared_error(y_val, y_pred))
            metrics = {
                "mse": mse,
                "rmse": mse ** 0.5,
                "mae": float(mean_absolute_error(y_val, y_pred)),
                "r2_score": float(r2_score(y_val, y_pred)),
            }

        return metrics

    async def _save_model(
        self, model: Any, name: str, thread_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save trained model to a .pkl file.

        Args:
            model: Trained model object
            name: Model name
            thread_id: Thread ID for directory organization

        Returns:
            Dictionary with:
                - model_file_path: Path to saved .pkl file
                - model_version: Generated version identifier for this artifact
        """
        try:
            # Create models directory within the project's data volume
            models_dir = DATA_VOLUME / "ml_models" / thread_id
            models_dir.mkdir(parents=True, exist_ok=True)
            model_version = "v2.0"

            # Generate unique filename
            safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
            filename = f"{safe_name}_{model_version}.pkl"
            file_path = models_dir / filename

            # Save model + metadata using pickle
            payload = {"model": model, "metadata": metadata, "version": model_version}
            with open(file_path, "wb") as f:

                pickle.dump(payload, f)

            logger.info(f"Saved model to: {file_path}")
            return {"model_file_path": str(file_path), "model_version": model_version}

        except Exception as e:
            logger.error(f"Error saving model: {str(e)}", exc_info=True)
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Failed to save model: {str(e)}",
            ) from e

    async def _register_trained_model(
        self,
        name: str,
        model_type: str,
        feature_columns: list,
        target_column: str,
        local_pkl_path: str,
        training_metrics: Optional[Dict[str, Any]] = None,
        target_model_id: Optional[str] = None,
        target_transform: Optional[dict] = None,
        categorical_feature_contracts: Optional[Dict[str, Any]] = None,
    ) -> tuple[Optional[str], Optional[str], Optional[str], List[str]]:
        """
        Upload the trained .pkl through the file manager and create/update the
        matching ``ml_models`` row, so an ML Model Inference node can find it
        immediately after training (via ``pkl_file_id``) instead of only a
        local path on disk that other containers/processes can't see.

        Args:
            local_pkl_path: Local path to the freshly fit model to upload.
            training_metrics: Validation metrics calculated for this training
                run. The new file replaces the model's, so ``None`` and an empty
                dictionary both record that it has no validation metrics.
            target_model_id: When set (an ML Model Pipeline run targets a
                specific model), that model is updated directly. Otherwise
                falls back to looking the model up by ``name`` — which is
                usually just the node's generic display label ("Train
                Model") for ad-hoc/test-node runs with no pipeline context.

        Returns:
            Tuple of (ml_model_id, pkl_file_id, error message, warnings). Never
            raises — a registration failure shouldn't fail a training run
            that already produced a valid .pkl on disk. When upload succeeds,
            pkl_file_id is retained even if updating the registry fails.
        """
        resolved_pkl_file_id = None
        try:
            from app.schemas.ml_model import MLModelCreate, MLModelUpdate
            from app.dependencies.injector import injector
            from app.services.ml_models import (
                MLModelsService,
                STALE_CATEGORICAL_DEFAULT_WARNING_PREFIX,
                merge_model_inference_params,
                stale_categorical_defaults,
            )
            from app.core.config.settings import file_storage_settings
            from app.schemas.file import FileBase
            from app.services.app_settings import AppSettingsService
            from app.services.file_manager import FileManagerService
            from app.services.ml_model_artifacts import ModelArtifactContract

            fm = injector.get(FileManagerService)
            app_cfg = await injector.get(AppSettingsService).get_by_type_and_name(
                "FileManagerSettings", "File Manager Settings"
            )
            provider = await fm.initialize(
                base_url=(file_storage_settings.APP_URL or "http://localhost:8000").rstrip("/"),
                base_path=str(DATA_VOLUME),
                app_settings=app_cfg,
            )

            file_name = os.path.basename(local_pkl_path)
            file_base = FileBase(
                name=file_name,
                storage_path=provider.get_base_path(),
                path="ml_models",
                storage_provider=provider.name,
                file_extension="pkl",
            )
            uploaded_file = await fm.create_file_from_local_path(
                local_pkl_path,
                file_base=file_base,
                original_filename=file_name,
                mime_type="application/octet-stream",
                delete_source=False,
            )
            resolved_pkl_file_id = str(uploaded_file.id)

            ml_service = injector.get(MLModelsService)
            # Marker recorded in the description of any model this node registers, so a
            # later run can recognize "its own" row by name. Node IDs are unique per node
            # instance, unlike the (often generic, e.g. "Train Model") display name.
            node_marker = f"[train-model-node:{self.node_id}]"
            description = (
                f"Trained by workflow Train Model node (thread {self.state.thread_id}) "
                f"{node_marker}"
            )
            model_fields = {
                "description": description,
                "model_type": model_type,
                "features": feature_columns,
                "target_variable": target_column,
                "pkl_file_id": resolved_pkl_file_id,
                # The uploaded file is now the source of truth; a stale local
                # path from a previous run shouldn't be preferred over it.
                "pkl_file": None,
            }

            existing = None
            if target_model_id:
                try:
                    existing = await ml_service.get_by_id(UUID(target_model_id))
                except (AppException, ValueError) as e:
                    logger.warning(
                        f"Pipeline target model {target_model_id} not found ({str(e)}); "
                        f"falling back to lookup by name '{name}'"
                    )
            if existing is None:
                # Only reuse a name match if this exact node registered it previously —
                # display names default to the generic "Train Model" label, so two
                # unrelated node instances can otherwise collide and silently overwrite
                # each other's registered model.
                by_name = await ml_service.get_by_name(name)
                if by_name and node_marker in (by_name.description or ""):
                    existing = by_name

            model_fields["inference_params"] = merge_model_inference_params(
                getattr(existing, "inference_params", None),
                feature_columns,
                target_transform.get("baselineColumn") if target_transform else None,
            )
            stale_defaults = stale_categorical_defaults(
                model_fields["inference_params"], categorical_feature_contracts
            )
            registration_warnings = []
            if stale_defaults:
                registration_warnings.append(
                    f"{STALE_CATEGORICAL_DEFAULT_WARNING_PREFIX}: "
                    f"{', '.join(stale_defaults)}. Update or remove these defaults before "
                    "relying on them during inference."
                )

            # These are the feature_columns/target_column this node wrote into the
            # artifact metadata, so registration need not download and re-read it.
            artifact_contract = ModelArtifactContract(
                features=tuple(feature_columns),
                target_variable=target_column,
                feature_count=len(feature_columns),
            )
            if existing:
                updated = await ml_service.update(
                    existing.id,
                    MLModelUpdate(**model_fields),
                    artifact_contract=artifact_contract,
                    training_metrics=training_metrics,
                )
                return str(updated.id), resolved_pkl_file_id, None, registration_warnings

            created = await ml_service.create(
                MLModelCreate(name=name, **model_fields),
                artifact_contract=artifact_contract,
                training_metrics=training_metrics,
            )
            return str(created.id), resolved_pkl_file_id, None, registration_warnings

        except Exception as e:
            logger.error(f"Failed to register trained model '{name}': {str(e)}", exc_info=True)
            # An OSError's message names the file it failed on, which is a
            # server path; the output only gets the reason (TDS-24).
            if isinstance(e, OSError):
                reason = e.strerror or type(e).__name__
                return None, resolved_pkl_file_id, f"Could not store the model file: {reason}", []
            return None, resolved_pkl_file_id, str(e), []
