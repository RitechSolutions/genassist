"""
ML Model Inference node implementation using the BaseNode class.
"""

from typing import Dict, Any
import logging
import os
import json
from uuid import UUID
import pandas as pd

from app.modules.workflow.engine.base_node import BaseNode
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.dependencies.injector import injector
from app.services.ml_models import MLModelsService
from app.services.ml_model_manager import get_ml_model_manager

logger = logging.getLogger(__name__)


def convert_value(val: Any) -> Any:
    """
    Convert a single value to its appropriate type.
    
    Args:
        val: Value to convert (can be any type)
    
    Returns:
        Converted value with appropriate type
    """
    # If not a string, keep as-is
    if not isinstance(val, str):
        return val
    
    # Try to parse JSON strings (arrays, objects)
    if val.strip().startswith('[') or val.strip().startswith('{'):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            pass  # Fall through to other conversions
    
    # Try to convert string values to appropriate types
    val_lower = val.lower().strip()
    
    # Boolean conversion
    if val_lower in ('true', 'false'):
        return val_lower == 'true'
    # Try float conversion
    elif '.' in val:
        try:
            return float(val)
        except ValueError:
            return val
    # Try integer conversion
    else:
        try:
            return int(val)
        except ValueError:
            return val


def convert_input_types(inference_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert string values in inference inputs to their appropriate types.
    Supports both single values and lists of values (for batch predictions).

    Args:
        inference_inputs: Raw inference inputs with string values

    Returns:
        Dictionary with properly typed values
    """
    converted = {}
    
    for key, value in inference_inputs.items():
        # Handle list of values (batch input) - apply conversion to each element
        if isinstance(value, list):
            converted[key] = [convert_value(v) for v in value]
        else:
            # Handle single value
            converted[key] = convert_value(value)

    logger.debug(f"Converted input types: {converted}")
    return converted


class MLModelInferenceNode(BaseNode):
    """ML Model Inference node that loads and runs predictions using stored ML models."""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an ML model inference node.
        Always returns batch format (even for single predictions).

        Args:
            config: The resolved configuration for the node containing:
                - modelId: UUID of the ML model to use
                - inferenceInputs: Dictionary mapping feature names to values
                  
                  Single value (treated as batch of 1):
                    {"feature1": value1, "feature2": value2}
                  
                  Batch values:
                    {"feature1": [val1, val2], "feature2": [val3, val4]}

        Returns:
            Dictionary with prediction results in batch format:
                {
                    "prediction": [1, 0, ...],
                    "prediction_label": ["Available", "Not Available", ...],
                    "probabilities": [{...}, {...}, ...],
                    "batch_size": N,
                    ...
                }
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
                logger.info(f"Model {model_id} ready for inference")
            except Exception as e:
                logger.error(
                    f"Failed to load model {model_id}: {str(e)}", exc_info=True)
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Could not load model: {str(e)}. Ensure all dependencies are installed."
                ) from e

            # Prepare features for inference
            # Convert string inputs to proper types (bool, float, int) and parse JSON arrays
            inference_inputs = convert_input_types(inference_inputs)
            logger.debug(f"Converted inference inputs: {inference_inputs}")
            
            # Normalize to batch format: convert single values to lists
            normalized_inputs = {}
            for key, value in inference_inputs.items():
                if isinstance(value, list):
                    normalized_inputs[key] = value
                else:
                    # Wrap single value in list to treat as batch of 1
                    normalized_inputs[key] = [value]
            
            # Prepare DataFrame for prediction (always batch format)
            try:
                # Create DataFrame directly from dict of lists
                df = pd.DataFrame(normalized_inputs)
                batch_size = len(df)
                logger.info(f"Batch size: {batch_size} rows")
                logger.info(f"Input columns: {list(df.columns)}")
                logger.info(f"Expected features from model: {list(model.feature_names_in_)}")
                
                # Add missing features with default values (0)
                missing_features = set(model.feature_names_in_) - set(df.columns)
                if missing_features:
                    logger.info(f"Adding missing features with default values: {missing_features}")
                    for feature in missing_features:
                        df[feature] = 0

                # Select only expected features in the correct order
                X = df[model.feature_names_in_]
                input_data = X.values  # Convert DataFrame to numpy array
                
                logger.info(f"Final input shape: {input_data.shape}")
                logger.info(f"Input data before prediction:\n{input_data}")
                
            except Exception as e:
                logger.error(f"Data preparation failed: {str(e)}", exc_info=True)
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Data preparation failed: {str(e)}"
                ) from e

            # Make prediction (always returns batch format)
            try:
                predictions = model.predict(input_data)
                
                # Get class labels
                if hasattr(model, 'classes_'):
                    class_labels = model.classes_
                else:
                    class_labels = [0, 1]

                # Try to get prediction probabilities if available (for classifiers)
                probabilities = None
                if hasattr(model, 'predict_proba'):
                    try:
                        probabilities = model.predict_proba(input_data)
                    except Exception as prob_error:
                        logger.warning(
                            f"Could not get prediction probabilities: {prob_error}")

                # Build response (always batch format)
                # Convert input_data to column-wise dictionary
                input_data_by_column = {}
                for i, feature_name in enumerate(model.feature_names_in_):
                    input_data_by_column[feature_name] = input_data[:, i].tolist()
                
                result = {
                    "status": "success",
                    "model_id": str(model_id),
                    "model_name": ml_model.name,
                    "model_type": ml_model.model_type.value if hasattr(ml_model.model_type, 'value') else ml_model.model_type,
                    "target_variable": ml_model.target_variable,
                    "features_used": ml_model.features,
                    "batch_size": batch_size,
                    "input_data": input_data_by_column,  # Dictionary organized by column
                    "prediction": [int(p) for p in predictions],
                    "prediction_label": ['Available' if p == 1 else 'Not Available' for p in predictions]
                }
                
                # Add probabilities and confidence
                if probabilities is not None:
                    result["probabilities"] = [
                        {f'Class_{int(class_labels[i])}': float(prob) for i, prob in enumerate(probs)}
                        for probs in probabilities
                    ]
                    result["confidences"] = [float(max(probs)) for probs in probabilities]
                
                logger.info(f"Prediction successful: {batch_size} predictions")
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
