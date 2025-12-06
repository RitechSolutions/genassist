"""
ML Model Inference node implementation using the BaseNode class.
"""

from typing import Dict, Any
import logging
import os
from uuid import UUID
import pandas as pd

from app.modules.workflow.engine.base_node import BaseNode
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.dependencies.injector import injector
from app.services.ml_models import MLModelsService
from app.services.ml_model_manager import get_ml_model_manager

logger = logging.getLogger(__name__)


def convert_input_types(inference_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert string values in inference inputs to their appropriate types.

    Args:
        inference_inputs: Raw inference inputs with string values

    Returns:
        Dictionary with properly typed values
    """
    converted = {}

    for key, value in inference_inputs.items():
        if not isinstance(value, str):
            # Keep non-string values as is
            converted[key] = value
            continue

        # Try to convert string values to appropriate types
        value_lower = value.lower().strip()

        # Boolean conversion
        if value_lower in ('true', 'false'):
            converted[key] = value_lower == 'true'
        # Try float conversion
        elif '.' in value:
            try:
                converted[key] = float(value)
            except ValueError:
                # Keep as string if conversion fails
                converted[key] = value
        # Try integer conversion
        else:
            try:
                converted[key] = int(value)
            except ValueError:
                # Keep as string if conversion fails
                converted[key] = value

    logger.debug(f"Converted input types: {converted}")
    return converted


def preprocess_features(feature_data: Dict[str, Any], feature_columns: list, expected_features: list) -> pd.DataFrame:
    """
    Preprocess feature data using the same steps as training.

    Args:
        feature_data: Feature data as dictionary
        feature_columns: List of feature column names

    Returns:
        pd.DataFrame: Preprocessed features
    """
    logger.debug("Preprocessing features...")

    # Convert dict to DataFrame
    df = pd.DataFrame([feature_data])

    # Select only the required feature columns
    X = df[feature_columns].copy()

    # Handle categorical variables by one-hot encoding
    categorical_columns = X.select_dtypes(include=['object']).columns
    if len(categorical_columns) > 0:
        logger.info(
            f"One-hot encoding categorical columns: {list(categorical_columns)}")
        X = pd.get_dummies(X, columns=categorical_columns, drop_first=True)

    # Handle boolean columns
    boolean_columns = X.select_dtypes(include=['bool']).columns
    if len(boolean_columns) > 0:
        logger.info(
            f"Converting boolean columns to int: {list(boolean_columns)}")
        X[boolean_columns] = X[boolean_columns].astype(int)

    logger.debug(f"Preprocessed feature shape: {X.shape}")
    missing_features = set(expected_features) - set(X.columns)

    if missing_features:
        print(
            f"Adding missing features with default values: {missing_features}")
        for feature in missing_features:
            X[feature] = 0

    # Reorder columns to match training data
    X = X[expected_features]
    return X


class MLModelInferenceNode(BaseNode):
    """ML Model Inference node that loads and runs predictions using stored ML models."""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an ML model inference node.

        Args:
            config: The resolved configuration for the node containing:
                - modelId: UUID of the ML model to use
                - inferenceInputs: Dictionary mapping feature names to values (subset of features)

        Returns:
            Dictionary with prediction results and metadata
        """
        try:
            # Extract configuration
            model_id_str = config.get("modelId")
            inference_inputs = config.get("inferenceInputs", {})

            if not model_id_str:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="modelId is required for ML model inference"
                )

            # Convert model_id to UUID
            try:
                model_id = UUID(model_id_str)
            except (ValueError, AttributeError) as e:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail=f"Invalid modelId format: {model_id_str}"
                ) from e

            # Get ML model from database
            ml_service = injector.get(MLModelsService)
            ml_model = await ml_service.get_by_id(model_id)

            if not ml_model:
                raise AppException(
                    error_key=ErrorKey.ML_MODEL_NOT_FOUND,
                    error_detail=f"ML model with ID {model_id} not found"
                )

            logger.info(f"Getting ML model: {ml_model.name} (ID: {model_id})")

            # Check if pkl file exists
            if not ml_model.pkl_file or not os.path.exists(ml_model.pkl_file):
                error_msg = f"PKL file not found for model {ml_model.name}"
                if ml_model.pkl_file:
                    error_msg += f" at path: {ml_model.pkl_file}"
                raise AppException(
                    error_key=ErrorKey.FILE_NOT_FOUND,
                    error_detail=error_msg
                )

            # Get model from cache or load it (using the ML Model Manager)
            try:
                model_manager = get_ml_model_manager()
                model = await model_manager.get_model(
                    model_id=model_id,
                    pkl_file=ml_model.pkl_file,
                    updated_at=ml_model.updated_at
                )
                logger.debug(f"Model {model_id} ready for inference")
            except Exception as e:
                logger.error(
                    f"Failed to load model {model_id}: {str(e)}", exc_info=True)
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Could not load model: {str(e)}. Ensure all dependencies are installed."
                ) from e

            # Prepare features for inference
            # inferenceInputs contains a subset of features with user-provided values
            # All other required features are filled with default values

            # Convert string inputs to proper types (bool, float, int)
            inference_inputs = convert_input_types(inference_inputs)

            # Preprocess features (handles categorical encoding, boolean conversion, etc.)
            try:
                X_processed = preprocess_features(
                    inference_inputs, inference_inputs.keys(), model.feature_names_in_)
                input_data = X_processed.values  # Convert DataFrame to numpy array
                logger.debug(f"Preprocessed input shape: {input_data.shape}")
            except Exception as e:
                logger.error(
                    f"Feature preprocessing failed: {str(e)}", exc_info=True)
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Feature preprocessing failed: {str(e)}"
                ) from e

            # Make prediction
            try:
                prediction = model.predict(input_data)[0]

                # Try to get prediction probabilities if available (for classifiers)
                probabilities = [0.0, 0.0]
                if hasattr(model, 'predict_proba'):
                    try:
                        probabilities = model.predict_proba(
                            input_data)[0]
                    except Exception as prob_error:
                        logger.warning(
                            f"Could not get prediction probabilities: {prob_error}")
                        
                if hasattr(model, 'predict_proba'):
                    class_labels = model.classes_
                else:
                    class_labels = [0, 1]

                # Build response
                result = {
                    "status": "success",
                    "model_id": str(model_id),
                    "model_name": ml_model.name,
                    "model_type": ml_model.model_type.value if hasattr(ml_model.model_type, 'value') else ml_model.model_type,
                    "target_variable": ml_model.target_variable,
                    "features_used": ml_model.features,
                    'prediction': int(prediction),
                    'prediction_label': 'Available' if prediction == 1 else 'Not Available',
                    'probabilities': {
                        f'Class_{int(class_labels[0])}': float(probabilities[0]),
                        f'Class_{int(class_labels[1])}': float(probabilities[1])
                    },
                    'confidence': float(max(probabilities))
                }

                # # Add probabilities if available
                # if probabilities is not None:
                #     result["probabilities"] = probabilities

                logger.info(f"Prediction successful: {prediction}")
                return result

            except Exception as e:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Error during model prediction: {str(e)}"
                ) from e

        except AppException:
            # Re-raise AppException as is
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in ML model inference: {str(e)}", exc_info=True)
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"ML model inference failed: {str(e)}"
            ) from e
