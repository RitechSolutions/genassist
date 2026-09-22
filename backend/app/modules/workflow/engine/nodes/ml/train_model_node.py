"""
Train Model node implementation using the BaseNode class.

This node trains ML models on CSV data and saves them as .pkl files.
"""

import logging
import pickle
from typing import Any, Dict, Optional

import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import (
    MaxAbsScaler,
    MinMaxScaler,
    OneHotEncoder,
    PolynomialFeatures,
    RobustScaler,
    StandardScaler,
)

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.nodes.ml import ml_utils

logger = logging.getLogger(__name__)

# Try to import xgboost (optional dependency)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost is not installed. XGBoost models will not be available.")

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
    - XGBoost (classification and regression)
    - Random Forest (classification and regression)
    - Linear Regression
    - Logistic Regression
    - Neural Network (MLPClassifier/MLPRegressor)
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a train model node.

        Args:
            config: The resolved configuration for the node containing:
                - name: Model name (required)
                - modelType: Type of model - "xgboost", "random_forest", "linear_regression",
                            "logistic_regression", "neural_network" (required)
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
                            the validation split) and then applied to both.
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
                            ("custom_expression", "bin_numeric", "normalize",
                            "standardize", or "polynomial"), plus strategy-specific
                            fields (expression / binColumn+numBins /
                            sourceColumns / polynomialColumns+polynomialDegree).
                            Bin edges and normalize/standardize statistics are fit
                            on the training split only and then applied to
                            validation, never the other way around.
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
                            Rows where baselineColumn is zero or missing are
                            dropped (an undefined ratio can't be used as a
                            training target).

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

            # Validate model type
            valid_model_types = ["xgboost", "random_forest", "linear_regression", "logistic_regression", "neural_network"]
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
                if strategy == "ordinal" and not item.get("ordinalMapping"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"categoricalEncoding entry for '{item.get('columnName')}' has strategy 'ordinal' but no ordinalMapping",
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
                "custom_expression", "bin_numeric", "normalize", "standardize", "polynomial",
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
                if strategy in ("normalize", "standardize") and not item.get("sourceColumns"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"featureEngineering entry '{item.get('newColumnName')}' has strategy '{strategy}' but no sourceColumns",
                    )
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

            # Check if XGBoost is available when needed
            if model_type == "xgboost" and not XGBOOST_AVAILABLE:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail="XGBoost is not installed. Please install it with: pip install xgboost",
                )

            logger.info(f"Training {model_type} model: {name}")

            # Load data from CSV file
            data, df = ml_utils.load_csv_file(file_url, self.state.thread_id)
            logger.info(f"Loaded {len(df)} rows from {file_url}")

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

            # Determine if classification or regression, honoring an explicit
            # user override before falling back to inference from the target.
            is_classification = self._is_classification_task(y, model_type, task_type)

            if target_transform is not None and is_classification:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail="targetTransform is only supported for regression tasks",
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

            # Handle outliers — bounds (IQR quartiles or z-score mean/std) are
            # computed from the training split only, then applied to both
            # splits. This must run before imputation/encoding/scaling below
            # since it can change which rows/values those steps see.
            if outlier_handling:
                X_train, y_train, X_val, y_val, baseline_train, baseline_val = self._handle_outliers(
                    X_train, y_train, X_val, y_val, outlier_handling, baseline_train, baseline_val
                )

            # Apply per-column missing-value overrides (drop_column/drop_rows/
            # impute_*). Fill values are computed from the training split
            # only, then applied to validation - see _handle_missing_values.
            if missing_value_handling:
                X_train, y_train, X_val, y_val, baseline_train, baseline_val = self._handle_missing_values(
                    X_train, y_train, X_val, y_val, missing_value_handling, baseline_train, baseline_val
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
            if has_missing:
                logger.warning("Found missing values in features. Filling with median for numeric and mode for categorical.")
                for col in X_train.columns:
                    if X_train[col].dtype in ['int64', 'float64']:
                        fill_value = X_train[col].median()
                    else:
                        mode_values = X_train[col].mode()
                        fill_value = mode_values[0] if not mode_values.empty else ''
                    X_train[col].fillna(fill_value, inplace=True)
                    if X_val is not None:
                        X_val[col].fillna(fill_value, inplace=True)

            # Apply the ratio target transform, if configured. Rows where the
            # baseline is zero or missing are dropped first - the ratio would
            # be undefined (division by zero) or NaN, neither usable as a
            # training target. y_val_actual keeps the real-unit validation
            # target so _evaluate_model can reconstruct predictions
            # (predicted_ratio * baseline) back to real units before scoring,
            # instead of reporting ratio-scale metrics.
            y_val_actual = None
            if target_transform is not None:
                train_keep = baseline_train.notna() & (baseline_train != 0)
                if not train_keep.all():
                    logger.warning(
                        f"Dropping {(~train_keep).sum()} training rows with a zero or missing "
                        f"'{baseline_column}' baseline (ratio target is undefined there)"
                    )
                    X_train, y_train, baseline_train = (
                        X_train[train_keep].reset_index(drop=True),
                        y_train[train_keep].reset_index(drop=True),
                        baseline_train[train_keep].reset_index(drop=True),
                    )
                if X_val is not None:
                    val_keep = baseline_val.notna() & (baseline_val != 0)
                    if not val_keep.all():
                        logger.warning(
                            f"Dropping {(~val_keep).sum()} validation rows with a zero or missing "
                            f"'{baseline_column}' baseline (ratio target is undefined there)"
                        )
                        X_val, y_val, baseline_val = (
                            X_val[val_keep].reset_index(drop=True),
                            y_val[val_keep].reset_index(drop=True),
                            baseline_val[val_keep].reset_index(drop=True),
                        )
                    y_val_actual = y_val.copy()
                    y_val = y_val / baseline_val
                y_train = y_train / baseline_train
                logger.info(f"Training on ratio target: {target_column} / {baseline_column}")

            # Create derived features - bin edges and normalize/standardize
            # statistics are fit on the training split only, then applied to
            # validation - see _engineer_features. Runs before the numeric
            # column capture below so new numeric features get scaled too.
            if feature_engineering:
                X_train, X_val = self._engineer_features(
                    X_train, X_val, feature_engineering
                )

            # Capture the numeric feature columns before one-hot encoding turns
            # categoricals into dummy columns, so scaling below only touches
            # genuinely-numeric original features.
            numeric_feature_columns = X_train.select_dtypes(include=['int64', 'float64']).columns.tolist()

            # Apply per-column encoding overrides (label/ordinal) and note which
            # columns asked for one-hot without dropping the first category.
            # Mappings are fit on the training split only, then applied to
            # validation - see _encode_categoricals.
            X_train, X_val, label_encodings, ordinal_encodings, one_hot_no_drop_columns = (
                self._encode_categoricals(X_train, X_val, categorical_encoding)
            )

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

            # Train the model
            model = await self._train_model(
                model_type=model_type,
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                is_classification=is_classification,
                model_parameters=model_parameters,
            )

            # Evaluate model if validation data is available. When a
            # targetTransform is configured, evaluate against the real-unit
            # target (y_val_actual) with predictions reconstructed via
            # baseline_val, so reported metrics are comparable to a model
            # trained directly on the real-unit target.
            metrics = {}
            if X_val is not None and y_val is not None:
                metrics = self._evaluate_model(
                    model, X_val,
                    y_val_actual if y_val_actual is not None else y_val,
                    is_classification,
                    reconstruct_baseline=baseline_val if target_transform is not None else None,
                )
                logger.info(f"Validation metrics: {metrics}")

            # Save model to .pkl file (model + metadata payload)
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
                    "scaling_method": resolved_scaling_method,
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
                    **({"target_transform": target_transform} if target_transform is not None else {}),
                },
            )

            # Prepare response
            result = {
                "success": True,
                "model_name": name,
                "model_type": model_type,
                "model_file_path": model_artifact["model_file_path"],
                "model_version": model_artifact["model_version"],
                "target_column": target_column,
                "feature_columns": feature_columns,
                "training_samples": len(X_train),
                "validation_samples": len(X_val) if X_val is not None else 0,
                "scaling_method": resolved_scaling_method,
                "metrics": metrics,
            }

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
                error_detail=f"Train model processing failed: {str(e)}",
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

        baseline_train/baseline_val (if given) back an optional targetTransform
        ratio target - kept row-aligned with X_train/X_val through any
        remove_outliers row drops, same as y_train/y_val.
        """
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
                train_mask = X_train[column].between(lower_bound, upper_bound)
                removed_train = (~train_mask).sum()
                X_train, y_train = X_train[train_mask].reset_index(drop=True), y_train[train_mask].reset_index(drop=True)
                if baseline_train is not None:
                    baseline_train = baseline_train[train_mask].reset_index(drop=True)
                if X_val is not None:
                    val_mask = X_val[column].between(lower_bound, upper_bound)
                    removed_val = (~val_mask).sum()
                    X_val, y_val = X_val[val_mask].reset_index(drop=True), y_val[val_mask].reset_index(drop=True)
                    if baseline_val is not None:
                        baseline_val = baseline_val[val_mask].reset_index(drop=True)
                else:
                    removed_val = 0
                logger.info(
                    f"Removed {removed_train} training and {removed_val} validation outlier rows "
                    f"from '{column}' using bounds [{lower_bound}, {upper_bound}] ({method})"
                )

        return X_train, y_train, X_val, y_val, baseline_train, baseline_val

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
            if strategy == "no_action" or column not in X_train.columns:
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
                mapping = item.get("ordinalMapping") or {}
                ordinal_encodings[column] = mapping
                X_train[column] = X_train[column].map(mapping)
                if X_val is not None:
                    X_val[column] = X_val[column].map(mapping)

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
        """
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
                fill_value = item.get("imputeValue", 0)
                X_train[column] = X_train[column].fillna(fill_value)
                if X_val is not None:
                    X_val[column] = X_val[column].fillna(fill_value)
            elif strategy in ("impute_mean", "impute_median", "impute_mode"):
                if strategy == "impute_mean":
                    fill_value = X_train[column].mean()
                elif strategy == "impute_median":
                    fill_value = X_train[column].median()
                else:
                    mode_values = X_train[column].mode()
                    fill_value = mode_values[0] if not mode_values.empty else None
                X_train[column] = X_train[column].fillna(fill_value)
                if X_val is not None:
                    X_val[column] = X_val[column].fillna(fill_value)

        return X_train, y_train, X_val, y_val, baseline_train, baseline_val

    def _engineer_features(self, X_train, X_val, feature_engineering):
        """
        Create derived features from existing columns.

        Bin edges (bin_numeric) and normalize/standardize statistics are
        computed from X_train only, then applied to X_val - never the other
        way around. custom_expression and polynomial don't fit anything from
        the data (a deterministic per-row formula and a fixed-degree feature
        map, respectively), so leakage isn't a concern for those, but they
        live here too so all feature configuration lives in one place.
        """
        for item in feature_engineering:
            strategy = item.get("strategy")
            new_col = item.get("newColumnName")

            if strategy == "custom_expression":
                expression = item.get("expression")
                # DataFrame.eval() only exposes column references and basic
                # arithmetic/comparison operators (via numexpr/Python parser)
                # - no access to builtins or arbitrary Python, unlike eval().
                try:
                    X_train[new_col] = X_train.eval(expression)
                    if X_val is not None:
                        X_val[new_col] = X_val.eval(expression)
                except Exception as e:
                    logger.warning(f"Skipping custom_expression for '{new_col}': {e}")

            elif strategy == "bin_numeric":
                bin_column = item.get("binColumn")
                num_bins = item.get("numBins")
                if bin_column not in X_train.columns or not pd.api.types.is_numeric_dtype(X_train[bin_column]):
                    logger.warning(f"Skipping bin_numeric for '{new_col}': column '{bin_column}' not found or not numeric")
                    continue
                _, bin_edges = pd.cut(X_train[bin_column], bins=num_bins, retbins=True, duplicates="drop")
                X_train[new_col] = pd.cut(
                    X_train[bin_column], bins=bin_edges, labels=False, include_lowest=True
                )
                if X_val is not None:
                    # Clip to the train-derived range first so a val value
                    # outside it still gets binned instead of becoming NaN.
                    clipped = X_val[bin_column].clip(lower=bin_edges[0], upper=bin_edges[-1])
                    X_val[new_col] = pd.cut(clipped, bins=bin_edges, labels=False, include_lowest=True)

            elif strategy in ("normalize", "standardize"):
                source_columns = [
                    c for c in (item.get("sourceColumns") or [])
                    if c in X_train.columns and pd.api.types.is_numeric_dtype(X_train[c])
                ]
                for col in source_columns:
                    out_col = new_col if len(source_columns) == 1 else f"{new_col}_{col}"
                    if strategy == "normalize":
                        min_val, max_val = X_train[col].min(), X_train[col].max()
                        if max_val == min_val:
                            continue
                        X_train[out_col] = (X_train[col] - min_val) / (max_val - min_val)
                        if X_val is not None:
                            X_val[out_col] = (X_val[col] - min_val) / (max_val - min_val)
                    else:
                        mean_val, std_val = X_train[col].mean(), X_train[col].std()
                        if std_val == 0:
                            continue
                        X_train[out_col] = (X_train[col] - mean_val) / std_val
                        if X_val is not None:
                            X_val[out_col] = (X_val[col] - mean_val) / std_val

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

        return X_train, X_val

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
        if model_type == "logistic_regression":
            return True
        if model_type == "linear_regression":
            return False

        # An explicit user selection takes priority over inference.
        if task_type == "classification":
            return True
        if task_type == "regression":
            return False

        # "auto": infer from target variable
        # If target is integer with few unique values, likely classification
        if y.dtype in ['int64', 'int32'] and y.nunique() <= 20:
            return True
        # If target is object/string, it's classification
        if y.dtype == 'object':
            return True

        # Default to regression for continuous numeric values
        return False

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

        if model_type == "xgboost":
            return self._train_xgboost(X_train, y_train, X_val, y_val, is_classification, model_parameters)
        elif model_type == "random_forest":
            return self._train_random_forest(X_train, y_train, is_classification, model_parameters)
        elif model_type == "linear_regression":
            return self._train_linear_regression(X_train, y_train, model_parameters)
        elif model_type == "logistic_regression":
            return self._train_logistic_regression(X_train, y_train, model_parameters)
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
            metrics = {
                "mse": float(mean_squared_error(y_val, y_pred)),
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

