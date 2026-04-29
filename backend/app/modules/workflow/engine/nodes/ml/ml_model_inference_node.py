"""
ML Model Inference node implementation using the BaseNode class.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

import numpy as np

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.dependencies.injector import injector
from app.modules.workflow.engine.base_node import BaseNode
from app.schemas.ml_model import MLModelBase
from app.services.ml_model_manager import download_pkl_file, get_ml_model_manager
from app.services.ml_models import MLModelsService

logger = logging.getLogger(__name__)

ML_MODELS_UPLOAD_DIR = str(DATA_VOLUME / "ml_models")

_BOOL_TRUE = frozenset({"true"})
_BOOL_FALSE = frozenset({"false"})


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

    stripped = val.strip()

    # Try to parse JSON strings (arrays, objects)
    if stripped.startswith(("[", "{")):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass  # Fall through to other conversions

    # Try to convert string values to appropriate types
    val_lower = stripped.lower()

    # Boolean conversion
    if val_lower in _BOOL_TRUE:
        return True
    if val_lower in _BOOL_FALSE:
        return False
    # Try float conversion
    if "." in stripped:
        try:
            return float(stripped)
        except ValueError:
            return val
    # Try integer conversion
    try:
        return int(stripped)
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
    return converted


def _build_input_array(
    normalized_inputs: Dict[str, List[Any]],
    feature_names: Sequence[str],
) -> np.ndarray:
    """Build a 2-D numpy array aligned to feature_names, filling missing features with 0.

    When feature_names is empty (model metadata doesn't specify column order),
    falls back to using all input columns in their dict-insertion order.
    """
    if not normalized_inputs:
        return np.empty((0, 0))

    # Fall back to input columns when model doesn't provide feature ordering
    if not feature_names:
        feature_names = list(normalized_inputs.keys())

    input_cols = set(normalized_inputs)
    columns = []
    batch_size = len(next(iter(normalized_inputs.values())))
    for feat in feature_names:
        if feat in input_cols:
            columns.append(normalized_inputs[feat])
        else:
            columns.append([0] * batch_size)
    return np.column_stack(columns) if columns else np.empty((batch_size, 0))


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
                    error_key=ErrorKey.MISSING_PARAMETER, error_detail="modelId is required for ML model inference"
                )

            # Convert model_id to UUID
            try:
                model_id = UUID(model_id_str)
            except (ValueError, AttributeError) as e:
                raise AppException(
                    error_key=ErrorKey.MISSING_PARAMETER, error_detail=f"Invalid modelId format: {model_id_str}"
                ) from e

            # Get ML model from database
            ml_service = injector.get(MLModelsService)
            ml_model = await ml_service.get_by_id(model_id)

            if not ml_model:
                raise AppException(
                    error_key=ErrorKey.ML_MODEL_NOT_FOUND, error_detail=f"ML model with ID {model_id} not found"
                )

            logger.info("Loading ML model %s (ID: %s)", ml_model.name, model_id)

            # Validate and ensure pkl file exists
            await self._ensure_pkl_file(ml_model, ml_service)

            # Get model from cache or load it (using the ML Model Manager)
            try:
                model_manager = get_ml_model_manager()
                model_response = await model_manager.get_model(
                    model_id=model_id,
                    pkl_file=ml_model.pkl_file,
                    pkl_file_id=ml_model.pkl_file_id,
                    updated_at=ml_model.updated_at,
                )
            except Exception as e:
                logger.error("Failed to load model %s: %s", model_id, e, exc_info=True)
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR,
                    error_detail=f"Could not load model: {e}. Ensure all dependencies are installed.",
                ) from e

            # Prepare features for inference
            # Convert string inputs to proper types (bool, float, int) and parse JSON arrays
            inference_inputs = convert_input_types(inference_inputs)

            # Normalize to batch format: convert single values to lists
            normalized_inputs: Dict[str, list] = {}
            for key, value in inference_inputs.items():
                normalized_inputs[key] = value if isinstance(value, list) else [value]

            # Check if model_response has a "version" key for v2.0 format vs legacy
            if "version" in model_response and model_response["version"] == "v2.0":
                model = model_response.get("model", {})
                metadata = model_response.get("metadata", {})
                feature_names: Sequence[str] = metadata.get("feature_columns", [])
            else:
                # legacy model response is the raw model object
                model = model_response.get("model", {})
                feature_names = model.feature_names_in_ if hasattr(model, "feature_names_in_") else []

            # Prepare input array for prediction (always batch format)
            # Fall back to input columns when model doesn't provide feature ordering
            if not feature_names:
                feature_names = list(normalized_inputs.keys())
            try:
                input_data = _build_input_array(normalized_inputs, feature_names)
                batch_size = input_data.shape[0]
                logger.debug(
                    "Inference input: batch_size=%d, features=%d, expected=%s",
                    batch_size, input_data.shape[1] if input_data.ndim == 2 else 0, list(feature_names),
                )
            except Exception as e:
                logger.error("Data preparation failed: %s", e, exc_info=True)
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"Data preparation failed: {e}"
                ) from e

            # Make prediction (always returns batch format)
            try:
                if not hasattr(model, "predict"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR, error_detail="Model does not have predict method"
                    )

                # Get class labels
                class_labels = getattr(model, "classes_", [0, 1])

                # Use predict_proba when available to avoid a redundant forward pass
                probabilities: Optional[np.ndarray] = None
                if hasattr(model, "predict_proba"):
                    try:
                        probabilities = model.predict_proba(input_data)
                        predictions = class_labels[np.argmax(probabilities, axis=1)]
                    except Exception:
                        predictions = model.predict(input_data)
                else:
                    predictions = model.predict(input_data)

                # Build response (always batch format)
                # Convert input_data to column-wise dictionary (columns ordered by feature_names)
                input_data_by_column = {
                    feature_names[i]: input_data[:, i].tolist()
                    for i in range(len(feature_names))
                }

                result: Dict[str, Any] = {
                    "status": "success",
                    "model_id": str(model_id),
                    "model_name": ml_model.name,
                    "model_type": ml_model.model_type.value
                    if hasattr(ml_model.model_type, "value")
                    else ml_model.model_type,
                    "target_variable": ml_model.target_variable,
                    "features_used": ml_model.features,
                    "batch_size": batch_size,
                    "input_data": input_data_by_column,
                    "prediction": [int(p) for p in predictions],
                    "prediction_label": ["Available" if p == 1 else "Not Available" for p in predictions],
                }

                # Add probabilities and confidence
                if probabilities is not None:
                    result["probabilities"] = [
                        {f"Class_{int(class_labels[i])}": float(prob) for i, prob in enumerate(probs)}
                        for probs in probabilities
                    ]
                    result["confidences"] = [float(max(probs)) for probs in probabilities]

                logger.info("Prediction complete: %d rows for model %s", batch_size, model_id)
                return result

            except AppException:
                raise
            except Exception as e:
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"Error during model prediction: {e}"
                ) from e

        except AppException:
            # Re-raise AppException as is
            raise
        except Exception as e:
            logger.error("Unexpected error in ML model inference: %s", e, exc_info=True)
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"ML model inference failed: {e}"
            ) from e

    async def _ensure_pkl_file(self, ml_model: Any, ml_service: MLModelsService) -> None:
        """
        Ensure the pkl file exists locally, downloading from file manager if needed.

        Args:
            ml_model: The ML model object
            ml_service: The ML models service instance

        Raises:
            AppException: If the PKL file is not found and cannot be downloaded
        """
        if ml_model.pkl_file and os.path.exists(ml_model.pkl_file):
            return

        # If pkl file id is provided, download the pkl file
        if ml_model.pkl_file_id:
            destination_path = os.path.join(ML_MODELS_UPLOAD_DIR, f"{ml_model.name}_{ml_model.id}.pkl")
            pkl_file_path = await download_pkl_file(ml_model.pkl_file_id, destination_path)
            # Update the ml_model with the new pkl file path
            await ml_service.update(ml_model.id, MLModelBase(pkl_file=str(pkl_file_path)))
            ml_model.pkl_file = str(pkl_file_path)
            return

        error_msg = f"PKL file not found for model {ml_model.name}"
        if ml_model.pkl_file:
            error_msg += f" at path: {ml_model.pkl_file}"
        raise AppException(error_key=ErrorKey.FILE_NOT_FOUND, error_detail=error_msg)
