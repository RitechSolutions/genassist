"""
Train Model node implementation using the BaseNode class.

This node trains ML models on CSV data and saves them as .pkl files.
"""

import logging
import os
import pickle
from typing import Any, Dict, Optional
from uuid import UUID

import pandas as pd
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
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.nodes.ml import hyperparameter_optimization as hpo_module
from app.modules.workflow.engine.nodes.ml import ml_utils

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
_OPTIONAL_MODEL_DEPENDENCIES = {
    "xgboost": ("XGBoost", lambda: XGBOOST_AVAILABLE),
    "lightgbm": ("LightGBM", lambda: LIGHTGBM_AVAILABLE),
    "catboost": ("CatBoost", lambda: CATBOOST_AVAILABLE),
}


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
                            "svm", "knn", "neural_network" (required)
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

            # Validate model type
            valid_model_types = [
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
            if model_type not in valid_model_types:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Invalid modelType: {model_type}. Must be one of: {', '.join(valid_model_types)}",
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

            # Determine if classification or regression based on target
            is_classification = self._is_classification_task(y, model_type)

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
                    X_train, X_val, y_train, y_val = train_test_split(
                        X, y, test_size=validation_split, random_state=42, stratify=y if is_classification else None
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

            # Handle categorical variables by one-hot encoding. Categories are
            # derived from the training split only; validation is reindexed to
            # the same columns, so a category only seen in validation is
            # dropped rather than leaking into the encoder's vocabulary.
            categorical_columns = X_train.select_dtypes(include=['object']).columns
            if len(categorical_columns) > 0:
                logger.info(f"One-hot encoding categorical columns: {list(categorical_columns)}")
                X_train = pd.get_dummies(X_train, columns=categorical_columns, drop_first=True)
                if X_val is not None:
                    X_val = pd.get_dummies(X_val, columns=categorical_columns, drop_first=True)
                    X_val = X_val.reindex(columns=X_train.columns, fill_value=0)

            # Handle boolean columns
            boolean_columns = X_train.select_dtypes(include=['bool']).columns
            if len(boolean_columns) > 0:
                logger.info(f"Converting boolean columns to int: {list(boolean_columns)}")
                X_train[boolean_columns] = X_train[boolean_columns].astype(int)
                if X_val is not None:
                    X_val[boolean_columns] = X_val[boolean_columns].astype(int)

            # Train the model — either a plain single fit with fixed params, or a
            # hyperparameter search over the curated space for this model type.
            search_metadata = None
            if hyperparameter_optimization != "none":
                optimization_result = hpo_module.optimize_hyperparameters(
                    model_type=model_type,
                    is_classification=is_classification,
                    X_train=X_train,
                    y_train=y_train,
                    method=hyperparameter_optimization,
                    user_params=model_parameters,
                    opt_config=optimization_config,
                    is_time_based=(split_method == "time_based"),
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
                    "metadata_schema_version": 1,
                    # Three core fields inference can rely on:
                    "feature_columns": feature_columns,
                    "target_column": target_column,
                    "model_type": model_type,
                    "model_parameters": model_parameters,
                    "hyperparameter_optimization": search_metadata,
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
            target_model_id = (self.state.initial_values or {}).get("model_id")
            ml_model_id, registration_error = await self._register_trained_model(
                name=name,
                model_type=model_type,
                feature_columns=feature_columns,
                target_column=target_column,
                local_pkl_path=model_artifact["model_file_path"],
                target_model_id=target_model_id,
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
                "metrics": metrics,
                "ml_model_id": ml_model_id,
                "model_parameters": model_parameters,
            }
            if search_metadata:
                result["hyperparameter_optimization"] = search_metadata
            if registration_error:
                result["registration_error"] = registration_error

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

    def _is_classification_task(self, y: pd.Series, model_type: str) -> bool:
        """
        Determine if this is a classification or regression task.

        Args:
            y: Target variable series
            model_type: Type of model

        Returns:
            True if classification, False if regression
        """
        return ml_utils.is_classification_task(y, model_type)

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
        target_model_id: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Upload the trained .pkl through the file manager and create/update the
        matching ``ml_models`` row, so an ML Model Inference node can find it
        immediately after training (via ``pkl_file_id``) instead of only a
        local path on disk that other containers/processes can't see.

        Args:
            target_model_id: When set (an ML Model Pipeline run targets a
                specific model), that model is updated directly. Otherwise
                falls back to looking the model up by ``name`` — which is
                usually just the node's generic display label ("Train
                Model") for ad-hoc/test-node runs with no pipeline context.

        Returns:
            Tuple of (ml_model_id or None, error message or None). Never
            raises — a registration failure shouldn't fail a training run
            that already produced a valid .pkl on disk.
        """
        try:
            from app.core.config.settings import file_storage_settings
            from app.dependencies.injector import injector
            from app.schemas.file import FileBase
            from app.schemas.ml_model import MLModelCreate, MLModelUpdate
            from app.services.app_settings import AppSettingsService
            from app.services.file_manager import FileManagerService
            from app.services.ml_models import MLModelsService

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

            ml_service = injector.get(MLModelsService)
            # Marker recorded in the description of any model this node registers, so a
            # later run can recognize "its own" row by name. Node IDs are unique per node
            # instance, unlike the (often generic, e.g. "Train Model") display name.
            node_marker = f"[train-model-node:{self.node_id}]"
            model_fields = {
                "description": (
                    f"Trained by workflow Train Model node (thread {self.state.thread_id}) "
                    f"{node_marker}"
                ),
                "model_type": model_type,
                "features": feature_columns,
                "target_variable": target_column,
                "pkl_file_id": str(uploaded_file.id),
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

            if existing:
                updated = await ml_service.update(existing.id, MLModelUpdate(**model_fields))
                return str(updated.id), None

            created = await ml_service.create(MLModelCreate(name=name, **model_fields))
            return str(created.id), None

        except Exception as e:
            logger.error(f"Failed to register trained model '{name}': {str(e)}", exc_info=True)
            return None, str(e)

