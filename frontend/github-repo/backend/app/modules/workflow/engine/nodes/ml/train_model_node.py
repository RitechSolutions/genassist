"""
Train Model node implementation using the BaseNode class.

This node trains ML models on CSV data and saves them as .pkl files.
"""

from typing import Dict, Any, Optional
import logging
import pickle
import uuid
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.neural_network import MLPClassifier, MLPRegressor

from app.modules.workflow.engine.base_node import BaseNode
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.nodes.ml import ml_utils

logger = logging.getLogger(__name__)

# Try to import xgboost (optional dependency)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost is not installed. XGBoost models will not be available.")


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

            # Validate model type
            valid_model_types = ["xgboost", "random_forest", "linear_regression", "logistic_regression", "neural_network"]
            if model_type not in valid_model_types:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Invalid modelType: {model_type}. Must be one of: {', '.join(valid_model_types)}",
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
            
            if missing_columns:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Columns not found in data: {missing_columns}. Available columns: {all_columns}",
                )

            # Prepare features and target
            X = df[feature_columns].copy()
            y = df[target_column].copy()

            # Handle missing values
            if X.isnull().any().any():
                logger.warning("Found missing values in features. Filling with median for numeric and mode for categorical.")
                for col in X.columns:
                    if X[col].dtype in ['int64', 'float64']:
                        X[col].fillna(X[col].median(), inplace=True)
                    else:
                        X[col].fillna(X[col].mode()[0] if not X[col].mode().empty else '', inplace=True)

            if y.isnull().any():
                logger.warning("Found missing values in target. Dropping rows with missing target values.")
                mask = ~y.isnull()
                X = X[mask]
                y = y[mask]

            # Handle categorical variables by one-hot encoding
            categorical_columns = X.select_dtypes(include=['object']).columns
            if len(categorical_columns) > 0:
                logger.info(f"One-hot encoding categorical columns: {list(categorical_columns)}")
                X = pd.get_dummies(X, columns=categorical_columns, drop_first=True)

            # Handle boolean columns
            boolean_columns = X.select_dtypes(include=['bool']).columns
            if len(boolean_columns) > 0:
                logger.info(f"Converting boolean columns to int: {list(boolean_columns)}")
                X[boolean_columns] = X[boolean_columns].astype(int)

            # Determine if classification or regression based on target
            is_classification = self._is_classification_task(y, model_type)

            # Split data for validation
            if validation_split > 0 and validation_split < 1:
                X_train, X_val, y_train, y_val = train_test_split(
                    X, y, test_size=validation_split, random_state=42, stratify=y if is_classification else None
                )
                logger.info(f"Split data: {len(X_train)} training samples, {len(X_val)} validation samples")
            else:
                X_train, y_train = X, y
                X_val, y_val = None, None
                logger.info(f"Using all {len(X_train)} samples for training (no validation split)")

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

            # Save model to .pkl file
            pkl_file_path = await self._save_model(model, name, self.state.thread_id)

            # Prepare response
            result = {
                "success": True,
                "model_name": name,
                "model_type": model_type,
                "model_file_path": pkl_file_path,
                "target_column": target_column,
                "feature_columns": feature_columns,
                "training_samples": len(X_train),
                "validation_samples": len(X_val) if X_val is not None else 0,
                "metrics": metrics,
            }

            logger.info(f"Model training completed successfully: {pkl_file_path}")
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
        # Some models are inherently classification or regression
        if model_type == "logistic_regression":
            return True
        if model_type == "linear_regression":
            return False

        # For others, infer from target variable
        # If target is integer with few unique values, likely classification
        if y.dtype in ['int64', 'int32'] and y.nunique() <= 20:
            return True
        # If target is object/string, it's classification
        if y.dtype == 'object':
            return True

        # Default to regression for continuous numeric values
        return False

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
            accuracy_score, precision_score, recall_score, f1_score,
            mean_squared_error, mean_absolute_error, r2_score
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

    async def _save_model(self, model: Any, name: str, thread_id: str) -> str:
        """
        Save trained model to a .pkl file.

        Args:
            model: Trained model object
            name: Model name
            thread_id: Thread ID for directory organization

        Returns:
            Path to saved .pkl file
        """
        try:
            # Create models directory within the project's data volume
            models_dir = DATA_VOLUME / "ml_models" / thread_id
            models_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename
            unique_id = str(uuid.uuid4())
            safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)
            filename = f"{safe_name}_{unique_id}.pkl"
            file_path = models_dir / filename

            # Save model using pickle
            with open(file_path, "wb") as f:
                pickle.dump(model, f)

            logger.info(f"Saved model to: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Error saving model: {str(e)}", exc_info=True)
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Failed to save model: {str(e)}",
            ) from e

