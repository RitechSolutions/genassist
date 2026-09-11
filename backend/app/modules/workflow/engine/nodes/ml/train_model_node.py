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
from sklearn.preprocessing import MaxAbsScaler, MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler

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

            if y.isnull().any():
                logger.warning("Found missing values in target. Dropping rows with missing target values.")
                mask = ~y.isnull()
                X = X[mask]
                y = y[mask]

            # Determine if classification or regression, honoring an explicit
            # user override before falling back to inference from the target.
            is_classification = self._is_classification_task(y, model_type, task_type)

            # Split BEFORE fitting any preprocessing (imputation medians/modes,
            # one-hot categories) — fitting those on the full dataset would leak
            # validation-row statistics into training, which for a time-based
            # split defeats the entire point (keeping "future" rows out of
            # training rather than just out of the raw feature matrix).
            if validation_split > 0 and validation_split < 1:
                if split_method == "time_based":
                    split_idx = int(len(X) * (1 - validation_split))
                    X_train, X_val = X.iloc[:split_idx].copy(), X.iloc[split_idx:].copy()
                    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
                    logger.info(
                        f"Time-based split on '{date_column}': {len(X_train)} training samples "
                        f"(earliest), {len(X_val)} validation samples (latest)"
                    )
                else:
                    try:
                        X_train, X_val, y_train, y_val = train_test_split(
                            X, y, test_size=validation_split, random_state=42,
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
                        X_train, X_val, y_train, y_val = train_test_split(
                            X, y, test_size=validation_split, random_state=42, stratify=None
                        )
                    logger.info(f"Split data: {len(X_train)} training samples, {len(X_val)} validation samples")
            else:
                X_train, y_train = X.copy(), y
                X_val, y_val = None, None
                logger.info(f"Using all {len(X_train)} samples for training (no validation split)")

            # Handle missing values — fit fill values on the training split only,
            # then apply those same values to validation so nothing about the
            # validation distribution leaks into how training data is filled.
            # Checked per-column against both splits: X_train having no NaNs
            # doesn't mean X_val doesn't (e.g. a time-based split can put all
            # the missing rows in the "future" validation portion).
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

            # Capture the numeric feature columns before one-hot encoding turns
            # categoricals into dummy columns, so scaling below only touches
            # genuinely-numeric original features.
            numeric_feature_columns = X_train.select_dtypes(include=['int64', 'float64']).columns.tolist()

            # One-hot encode categorical variables with a fitted OneHotEncoder
            # (not pd.get_dummies) and save both the encoder and the raw column
            # names it applies to in the model metadata. Without this, the
            # saved feature_columns list stays at the original (pre-encoding)
            # names while the model is actually fit on the expanded dummy
            # columns, which breaks inference for any model trained with
            # categorical features (metadata.feature_columns wouldn't line up
            # with what model.predict() expects). The encoder is fit on the
            # training split only; unseen categories at inference/validation
            # map to all-zeros (handle_unknown="ignore") rather than leaking
            # into its vocabulary.
            categorical_columns = X_train.select_dtypes(include=['object']).columns.tolist()
            encoder = None
            if categorical_columns:
                logger.info(f"One-hot encoding categorical columns: {categorical_columns}")
                encoder = OneHotEncoder(drop="first", handle_unknown="ignore", sparse_output=False)
                encoded_train = encoder.fit_transform(X_train[categorical_columns])
                encoded_columns = encoder.get_feature_names_out(categorical_columns).tolist()
                X_train = pd.concat(
                    [
                        X_train.drop(columns=categorical_columns).reset_index(drop=True),
                        pd.DataFrame(encoded_train, columns=encoded_columns),
                    ],
                    axis=1,
                )
                if X_val is not None:
                    encoded_val = encoder.transform(X_val[categorical_columns])
                    X_val = pd.concat(
                        [
                            X_val.drop(columns=categorical_columns).reset_index(drop=True),
                            pd.DataFrame(encoded_val, columns=encoded_columns),
                        ],
                        axis=1,
                    )

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

            # Evaluate model if validation data is available
            metrics = {}
            if X_val is not None and y_val is not None:
                metrics = self._evaluate_model(model, X_val, y_val, is_classification)
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

    def _evaluate_model(self, model, X_val: pd.DataFrame, y_val: pd.Series, is_classification: bool) -> Dict[str, Any]:
        """
        Evaluate model performance on validation data.

        Args:
            model: Trained model
            X_val: Validation features
            y_val: Validation target
            is_classification: Whether this is a classification task

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

