"""
ML Model Inference node implementation using the BaseNode class.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

import numpy as np
import pandas as pd

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.dependencies.injector import injector
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.nodes.ml.ml_utils import (
    COLUMN_TRANSFORM_STRATEGY_LABELS,
    apply_column_transform,
    column_transform_value_problem,
    normalize_feature_expression,
    ordinal_key,
)
from app.schemas.ml_model import FEATURE_DEFAULTS_PARAM, MLModelBase
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


def _convert_categorical_input(
    value: Any,
    known_values: Optional[set[Any]],
    normalize_key: bool,
) -> Any:
    if isinstance(value, list):
        return [
            _convert_categorical_input(item, known_values, normalize_key)
            for item in value
        ]
    if not isinstance(value, str):
        return value

    converted = convert_value(value)
    if isinstance(converted, list):
        return [
            _convert_categorical_input(item, known_values, normalize_key)
            for item in converted
        ]
    if isinstance(converted, dict) or known_values is None:
        return value if not isinstance(converted, dict) else converted
    if _category_key(value, normalize_key) in known_values:
        return value
    if _category_key(converted, normalize_key) in known_values:
        return converted
    return value


def convert_input_types(
    inference_inputs: Dict[str, Any],
    categorical_features: Optional[Sequence[str]] = None,
    categorical_values: Optional[Dict[str, set[Any]]] = None,
    normalized_categorical_features: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Convert string values in inference inputs to their appropriate types.
    Supports both single values and lists of values (for batch predictions).

    Args:
        inference_inputs: Raw inference inputs with string values
        categorical_features: Features whose fitted category types must be preserved
        categorical_values: Fitted category keys by feature
        normalized_categorical_features: Features matched through ordinal keys

    Returns:
        Dictionary with properly typed values
    """
    categorical_feature_set = set(categorical_features or [])
    categorical_values = categorical_values or {}
    normalized_feature_set = set(normalized_categorical_features or [])
    converted = {}
    for key, value in inference_inputs.items():
        if key in categorical_feature_set:
            converted[key] = _convert_categorical_input(
                value,
                categorical_values.get(key),
                key in normalized_feature_set,
            )
            continue
        # Handle list of values (batch input) - apply conversion to each element
        if isinstance(value, list):
            converted[key] = [convert_value(v) for v in value]
        else:
            # Handle single value
            converted[key] = convert_value(value)
    return converted


def _is_empty_input(value: Any) -> bool:
    """True when a feature was left unset in the node config."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return isinstance(value, list) and len(value) == 0


def _normalize_inference_inputs(inference_inputs: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Convert inference inputs to batch lists, skipping unset/empty values."""
    normalized: Dict[str, List[Any]] = {}
    for key, value in inference_inputs.items():
        if _is_empty_input(value):
            continue
        normalized[key] = value if isinstance(value, list) else [value]
    return normalized


def _infer_batch_size(normalized_inputs: Dict[str, List[Any]]) -> int:
    if not normalized_inputs:
        return 0
    return max(len(values) for values in normalized_inputs.values())


def _broadcast_column(values: List[Any], batch_size: int, feature_name: str) -> List[Any]:
    """Expand a single-value column to batch_size or validate an explicit batch column."""
    col_len = len(values)
    if col_len == batch_size:
        return values
    if col_len == 1:
        return values * batch_size
    raise AppException(
        error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
        error_detail=(
            f"Feature '{feature_name}' has {col_len} values but batch size is {batch_size}. "
            f"Provide one value (applied to every row) or exactly {batch_size} values."
        ),
    )


def _validate_categorical_inputs(
    normalized_inputs: Dict[str, List[Any]],
    categorical_columns: Sequence[str],
    categories: Sequence[np.ndarray],
) -> None:
    """Reject a caller-supplied categorical value the encoder wasn't trained on,
    instead of silently encoding it as the dropped baseline category (which is
    indistinguishable from a legitimate prediction for that category).

    Missing columns are handled by the feature-contract validation before this
    transform runs; this helper only validates supplied categorical values.
    """
    for col, known in zip(categorical_columns, categories):
        if col not in normalized_inputs:
            continue
        known_values = {_category_key(value) for value in known.tolist()}
        invalid_values = sorted(
            {
                str(value)
                for value in normalized_inputs[col]
                if _category_key(value) not in known_values
            }
        )
        if invalid_values:
            allowed = ", ".join(str(v) for v in known.tolist())
            raise AppException(
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=(
                    f"Invalid value(s) for feature '{col}': {', '.join(invalid_values)}. "
                    f"Please enter a correct value, otherwise this field will be ignored. "
                    f"Expected one of: {allowed}."
                ),
            )


def _category_key(value: Any, normalize: bool = False) -> Any:
    if normalize:
        return ordinal_key(value)
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return ("bool", value)
    return value


def _is_missing_value(
    value: Any,
    known_categorical_values: Optional[set[Any]] = None,
    normalize_category_key: bool = False,
) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {"null", "nan", "none"}:
        return known_categorical_values is None or _category_key(
            value, normalize_category_key
        ) not in known_categorical_values
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _summarize_error(error: Exception) -> str:
    detail = str(error).strip()
    return detail.splitlines()[0][:200] if detail else type(error).__name__


def _feature_defaults(inference_params: Any) -> Dict[str, Any]:
    """Read deliberate per-model defaults from the model record."""
    if not inference_params:
        return {}
    if not isinstance(inference_params, dict):
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail="Model inference parameters must be an object.",
        )

    defaults = inference_params.get(FEATURE_DEFAULTS_PARAM) or {}
    if not isinstance(defaults, dict):
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=f"Model inference parameter '{FEATURE_DEFAULTS_PARAM}' must be an object.",
        )
    return defaults


def _prepare_inference_inputs(
    normalized_inputs: Dict[str, List[Any]],
    feature_names: Sequence[str],
    defaults: Optional[Dict[str, Any]] = None,
    allowed_extra_features: Optional[Sequence[str]] = None,
    categorical_features: Optional[Sequence[str]] = None,
    categorical_values: Optional[Dict[str, set[Any]]] = None,
    normalized_categorical_features: Optional[Sequence[str]] = None,
) -> tuple[Dict[str, List[Any]], List[str]]:
    """Validate the model's raw feature contract and apply only configured defaults."""
    expected_features = list(feature_names)
    if not expected_features:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                "This model artifact does not record its required feature set. "
                "Retrain the model with current metadata before running inference."
            ),
        )

    defaults = defaults or {}
    expected_set = set(expected_features)
    allowed_extra_set = {feature for feature in allowed_extra_features or [] if feature}
    categorical_feature_set = (
        None if categorical_features is None else set(categorical_features)
    )
    categorical_values = categorical_values or {}
    normalized_categorical_feature_set = set(normalized_categorical_features or [])

    unknown_defaults = [name for name in defaults if name not in expected_set]
    if unknown_defaults:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                f"Model default(s) configured for unknown feature(s): {', '.join(unknown_defaults)}. "
                f"Required model features: {', '.join(expected_features)}."
            ),
        )

    missing_value_masks = {
        name: [
            _is_missing_value(
                value,
                categorical_values.get(name),
                name in normalized_categorical_feature_set,
            )
            for value in normalized_inputs[name]
        ]
        for name in expected_features
        if name in normalized_inputs
    }
    missing_features = [name for name in expected_features if name not in normalized_inputs]
    features_with_missing_values = [
        name for name, missing_mask in missing_value_masks.items() if any(missing_mask)
    ]
    defaults_to_apply = {
        name
        for name in expected_features
        if name in defaults
        and (name in missing_features or name in features_with_missing_values)
    }
    prepared_defaults = {
        name: (
            value
            if categorical_feature_set is not None and name in categorical_feature_set
            else convert_value(value)
        )
        for name, value in defaults.items()
        if name in defaults_to_apply
    }

    invalid_defaults = [
        name
        for name, value in prepared_defaults.items()
        if isinstance(value, (dict, list))
        or _is_missing_value(
            value,
            categorical_values.get(name),
            name in normalized_categorical_feature_set,
        )
    ]
    if invalid_defaults:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                f"Model default(s) must be non-null scalar values for: {', '.join(invalid_defaults)}."
            ),
        )

    invalid_numeric_defaults = [
        name
        for name, value in prepared_defaults.items()
        if categorical_feature_set is not None
        and name not in categorical_feature_set
        and isinstance(value, str)
    ]
    if invalid_numeric_defaults:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                "Model default(s) for numeric feature(s) must be numbers or booleans: "
                f"{', '.join(invalid_numeric_defaults)}."
            ),
        )

    non_finite_defaults = [
        name
        for name, value in prepared_defaults.items()
        if isinstance(value, (float, np.floating)) and not np.isfinite(value)
    ]
    if non_finite_defaults:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                "Model default(s) must be finite numbers for: "
                f"{', '.join(non_finite_defaults)}."
            ),
        )

    invalid_categorical_defaults = [
        name
        for name, value in prepared_defaults.items()
        if name in categorical_values
        and _category_key(
            value, name in normalized_categorical_feature_set
        ) not in categorical_values[name]
    ]
    if invalid_categorical_defaults:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                "Invalid configured feature default(s): "
                f"{', '.join(invalid_categorical_defaults)}. Each categorical default must "
                "match a category fitted by the model."
            ),
        )

    unexpected_features = [
        name for name in normalized_inputs if name not in expected_set and name not in allowed_extra_set
    ]
    unfilled_features = [
        name
        for name in expected_features
        if (name in missing_features or name in features_with_missing_values) and name not in defaults
    ]

    problems = []
    if unfilled_features:
        problems.append(
            f"Missing value(s) for feature(s): {', '.join(unfilled_features)}."
        )
    if unexpected_features:
        problems.append(
            f"Unexpected feature(s): {', '.join(unexpected_features)}."
        )
    if unfilled_features:
        problems.append(
            f"Provide every value or configure '{FEATURE_DEFAULTS_PARAM}' in the model's inference parameters. "
            f"Required model features: {', '.join(expected_features)}."
        )
    if unexpected_features:
        accepted_features = expected_features + sorted(allowed_extra_set)
        problems.append(f"Accepted inference inputs: {', '.join(accepted_features)}.")
    if problems:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=" ".join(problems),
        )

    batch_size = _infer_batch_size(normalized_inputs) or 1
    prepared_inputs = dict(normalized_inputs)
    defaults_applied = []
    for name in expected_features:
        if name not in prepared_inputs:
            prepared_inputs[name] = [prepared_defaults[name]] * batch_size
            defaults_applied.append(name)
            continue

        values = _broadcast_column(prepared_inputs[name], batch_size, name)
        missing_mask = _broadcast_column(
            missing_value_masks[name], batch_size, name
        )
        if name in prepared_defaults and any(missing_mask):
            values = [
                prepared_defaults[name] if is_missing else value
                for value, is_missing in zip(values, missing_mask)
            ]
            defaults_applied.append(name)
        prepared_inputs[name] = values

    return prepared_inputs, defaults_applied


def _build_input_array(
    normalized_inputs: Dict[str, List[Any]],
    feature_names: Sequence[str],
) -> np.ndarray:
    """Build a 2-D array in model feature order without inventing values."""
    if not normalized_inputs:
        return np.empty((0, 0))

    batch_size = _infer_batch_size(normalized_inputs)
    missing_features = [name for name in feature_names if name not in normalized_inputs]
    if missing_features:
        raise ValueError(f"Missing prepared feature column(s): {', '.join(missing_features)}")

    columns = [
        _broadcast_column(normalized_inputs[feature_name], batch_size, feature_name)
        for feature_name in feature_names
    ]
    return np.column_stack(columns) if columns else np.empty((batch_size, 0))


def _one_hot_transform(
    normalized_inputs: Dict[str, List[Any]],
    columns: Sequence[str],
    encoder: Any,
) -> "tuple[np.ndarray, List[str]]":
    """Reapply a fitted OneHotEncoder to raw categorical inputs, validating
    against the categories it was fit on."""
    # Object dtype keeps categorical values compatible with the fitted encoder.
    cat_data = _build_input_array(normalized_inputs, columns).astype(object)
    _validate_categorical_inputs(normalized_inputs, columns, encoder.categories_)
    encoded = encoder.transform(cat_data)
    encoded_columns = encoder.get_feature_names_out(columns).tolist()
    return encoded, encoded_columns


def _mapped_transform(
    normalized_inputs: Dict[str, List[Any]],
    columns: Sequence[str],
    mappings: Dict[str, Dict[Any, Any]],
    batch_size: int,
    unseen_value: float,
    normalize_keys: bool = False,
) -> np.ndarray:
    """Reapply a fitted label/ordinal value -> code mapping to raw inputs.

    A value the mapping wasn't fit on (or has no entry for) falls back to
    unseen_value, mirroring how the same case is handled at training time
    (see TrainModelNode._encode_categoricals).

    normalize_keys (ordinal mappings): match values with ordinal_key, as
    training does, so e.g. an input of 2 finds the JSON key "2" and " High"
    finds "High". Applied to the stored keys too, so models trained before
    ordinal_key existed still match.
    """
    if not columns:
        return np.empty((batch_size, 0))
    raw = _build_input_array(normalized_inputs, columns).astype(object)
    out = np.empty(raw.shape, dtype=float)
    for i, col in enumerate(columns):
        mapping = mappings.get(col, {})
        if normalize_keys:
            mapping = {ordinal_key(k): v for k, v in mapping.items()}
            out[:, i] = [mapping.get(ordinal_key(v), unseen_value) for v in raw[:, i]]
        else:
            mapping = {_category_key(k): v for k, v in mapping.items()}
            out[:, i] = [
                mapping.get(_category_key(v), unseen_value) for v in raw[:, i]
            ]
    return out


def _json_safe_scalar(value: Any) -> Any:
    """Convert NumPy scalars to JSON-safe Python scalar values."""
    if isinstance(value, np.generic):
        value = value.item()

    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool, type(None))):
        return value

    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
    return value


def _replay_feature_engineering(
    normalized_inputs: Dict[str, List[Any]],
    steps: List[Dict[str, Any]],
    batch_size: int,
) -> Dict[str, np.ndarray]:
    """Recompute engineered feature columns from raw caller-supplied inputs,
    using the exact fitted parameters (bin edges, mean/std, fitted
    PolynomialFeatures transformer) captured at training time - see
    TrainModelNode._engineer_features, which returns these same steps.

    Steps run in the same order they were trained in. A later step can
    reference an earlier step's new column (e.g. a polynomial feature built
    from a normalized one), same as at training time, so each computed
    column is folded into `available` for subsequent steps to read.
    """
    computed: Dict[str, np.ndarray] = {}
    available = dict(normalized_inputs)

    for step in steps:
        strategy = step.get("strategy")
        new_col = step.get("new_col")

        try:
            if strategy == "custom_expression":
                expression = step.get("expression")
                df = pd.DataFrame({
                    col: _build_input_array(available, [col])[:, 0]
                    for col in available
                })
                result = np.asarray(df.eval(normalize_feature_expression(expression)))
                computed[new_col] = result
                available[new_col] = result.tolist()

            elif strategy == "bin_numeric":
                bin_column = step.get("bin_column")
                bin_edges = step.get("bin_edges") or []
                if bin_column not in available or len(bin_edges) < 2:
                    continue
                raw = _build_input_array(available, [bin_column]).astype(float)[:, 0]
                clipped = np.clip(raw, bin_edges[0], bin_edges[-1])
                binned = pd.cut(
                    pd.Series(clipped), bins=bin_edges, labels=False, include_lowest=True
                ).to_numpy()
                computed[new_col] = binned
                available[new_col] = binned.tolist()

            elif strategy in ("normalize", "standardize"):
                # Retired for new features (see train_model_node), but models
                # trained with them still need them replayed.
                for col, stats in (step.get("column_stats") or {}).items():
                    if col not in available:
                        continue
                    raw = _build_input_array(available, [col]).astype(float)[:, 0]
                    out_col = stats["out_col"]
                    if strategy == "normalize":
                        result = (raw - stats["min"]) / (stats["max"] - stats["min"])
                    else:
                        result = (raw - stats["mean"]) / stats["std"]
                    computed[out_col] = result
                    available[out_col] = result.tolist()

            elif strategy == "polynomial":
                poly_columns = step.get("poly_columns") or []
                poly = step.get("poly")
                new_names = step.get("new_names") or []
                if not poly_columns or poly is None or any(c not in available for c in poly_columns):
                    continue
                raw = _build_input_array(available, poly_columns).astype(float)
                poly_out = poly.transform(raw)
                new_values = poly_out[:, len(poly_columns):]
                for i, name in enumerate(new_names):
                    computed[name] = new_values[:, i]
                    available[name] = new_values[:, i].tolist()

            elif strategy in COLUMN_TRANSFORM_STRATEGY_LABELS:
                label = COLUMN_TRANSFORM_STRATEGY_LABELS[strategy]
                columns = step.get("columns") or []
                absent = [c for c in columns if c not in available]
                if absent:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=(
                            f"Feature '{new_col}' ({label}) needs input column(s) {absent}, "
                            "which were not provided"
                        ),
                    )
                try:
                    raw = _build_input_array(available, columns).astype(float)
                except (TypeError, ValueError) as e:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Feature '{new_col}' ({label}) needs numeric inputs for {columns}: {e}",
                    ) from e
                problem = column_transform_value_problem(strategy, raw, columns, step.get("power_method"))
                if problem:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=f"Feature '{new_col}' ({label}) can't use these inputs: {problem}",
                    )
                out = apply_column_transform(strategy, step.get("transformer"), raw)
                for i, name in enumerate(step.get("output_columns") or []):
                    computed[name] = out[:, i]
                    available[name] = out[:, i].tolist()
        except AppException:
            raise
        except Exception as e:
            logger.warning(
                "Failed to replay feature-engineering step '%s' (%s) at inference: %s",
                new_col, strategy, e,
            )

    return computed


def _label_for_prediction(value: Any) -> str:
    """Map a model prediction to an availability label."""
    if value is None:
        return "Not Available"
    if isinstance(value, (bool, np.bool_)):
        return "Available" if value else "Not Available"
    if isinstance(value, (int, float, np.integer, np.floating)):
        return "Available" if float(value) != 0 else "Not Available"
    if isinstance(value, str):
        return "Available" if value.strip() else "Not Available"
    return "Available" if value else "Not Available"


def _build_prediction_outputs(
    predictions: Sequence[Any], class_labels: Optional[Sequence[Any]]
) -> tuple[List[Any], List[Any], List[Dict[str, Any]]]:
    """Build flat and structured prediction outputs from one shared label rule."""
    prediction_values = [_json_safe_scalar(prediction) for prediction in predictions]
    prediction_labels = list(prediction_values) if class_labels is not None else [None] * len(prediction_values)
    prediction_entries = [
        {"result": prediction, "label": label}
        for prediction, label in zip(prediction_values, prediction_labels, strict=True)
    ]
    return prediction_values, prediction_labels, prediction_entries


def _build_probability_outputs(
    probabilities: np.ndarray, class_labels: Sequence[Any]
) -> tuple[List[Dict[str, Any]], List[Any]]:
    """Build probability dictionaries without assuming numeric class labels."""
    json_class_labels = [_json_safe_scalar(class_label) for class_label in class_labels]
    probability_outputs = [
        {f"Class_{json_class_labels[index]}": _json_safe_scalar(probability) for index, probability in enumerate(row)}
        for row in probabilities
    ]
    confidences = [_json_safe_scalar(max(row)) for row in probabilities]
    return probability_outputs, confidences


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
                    "prediction": [1, 0, ...],  # flat list (backward compatible)
                    "prediction_label": ["approved", "denied", ...],
                    "prediction_details": [{"result": "approved", "label": "approved"}, ...],
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

            # Check if model_response has a "version" key for v2.0 format vs legacy
            metadata: Dict[str, Any] = {}
            inference_warnings: List[str] = []
            if "version" in model_response and model_response["version"] == "v2.0":
                model = model_response.get("model", {})
                metadata = model_response.get("metadata", {})
                feature_names: Sequence[str] = metadata.get("feature_columns", [])
            else:
                # legacy model response is the raw model object
                model = model_response.get("model", {})
                recorded_feature_names = getattr(model, "feature_names_in_", None)
                if recorded_feature_names is not None and len(recorded_feature_names) > 0:
                    feature_names = list(recorded_feature_names)
                else:
                    registered_feature_names = list(getattr(ml_model, "features", None) or [])
                    recorded_feature_count = getattr(model, "n_features_in_", None)
                    if registered_feature_names and recorded_feature_count == len(
                        registered_feature_names
                    ):
                        feature_names = registered_feature_names
                        warning = (
                            "The model artifact does not record feature names, so inference used the "
                            "registry feature order. Verify that the registry order matches training."
                        )
                        inference_warnings.append(warning)
                        logger.warning("Model %s: %s", model_id, warning)
                    elif recorded_feature_count is None:
                        raise AppException(
                            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                            error_detail=(
                                "This model artifact does not record its required feature set. "
                                "This uploaded or legacy model records neither feature names nor a "
                                f"feature count, while the registry lists {len(registered_feature_names)} "
                                "feature(s). Upload an artifact that records its feature contract or "
                                "replace it with a compatible model."
                            ),
                        )
                    else:
                        raise AppException(
                            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                            error_detail=(
                                "This model artifact does not record its required feature set. "
                                f"This uploaded or legacy model expects {recorded_feature_count} feature(s), "
                                f"but the registry lists {len(registered_feature_names)}. Correct the model's "
                                "registered feature list or upload a compatible artifact."
                            ),
                        )

            # Prepare input array for prediction (always batch format)
            defaults_applied: List[str] = []
            try:
                inference_params = getattr(ml_model, "inference_params", None) or {}
                target_transform = metadata.get("target_transform")
                categorical_columns: List[str] = metadata.get("categorical_columns") or []
                categorical_columns_no_drop: List[str] = metadata.get("categorical_columns_no_drop") or []
                label_encodings: Dict[str, Dict[Any, int]] = metadata.get("label_encodings") or {}
                ordinal_encodings: Dict[str, Dict[Any, Any]] = metadata.get("ordinal_encodings") or {}
                encoder = metadata.get("encoder")
                encoder_no_drop = metadata.get("encoder_no_drop")
                categorical_features = (
                    categorical_columns
                    + categorical_columns_no_drop
                    + list(label_encodings)
                    + list(ordinal_encodings)
                )
                categorical_values: Dict[str, set[Any]] = {
                    name: {_category_key(value) for value in mapping}
                    for name, mapping in label_encodings.items()
                }
                categorical_values.update(
                    {
                        name: {_category_key(value, normalize=True) for value in mapping}
                        for name, mapping in ordinal_encodings.items()
                    }
                )
                if encoder is not None:
                    categorical_values.update(
                        {
                            name: {_category_key(value) for value in values.tolist()}
                            for name, values in zip(categorical_columns, encoder.categories_)
                        }
                    )
                if encoder_no_drop is not None:
                    categorical_values.update(
                        {
                            name: {_category_key(value) for value in values.tolist()}
                            for name, values in zip(
                                categorical_columns_no_drop,
                                encoder_no_drop.categories_,
                            )
                        }
                    )
                inference_inputs = convert_input_types(
                    inference_inputs,
                    categorical_features=categorical_features if metadata else None,
                    categorical_values=categorical_values if metadata else None,
                    normalized_categorical_features=list(ordinal_encodings),
                )
                normalized_inputs = _normalize_inference_inputs(inference_inputs)
                allowed_extra_features = {
                    inference_params.get("ratioBaselineColumn")
                    if isinstance(inference_params, dict)
                    else None,
                    target_transform.get("baselineColumn") if target_transform else None,
                }
                normalized_inputs, defaults_applied = _prepare_inference_inputs(
                    normalized_inputs,
                    feature_names,
                    defaults=_feature_defaults(inference_params),
                    allowed_extra_features=allowed_extra_features,
                    categorical_features=categorical_features if metadata else None,
                    categorical_values=categorical_values if metadata else None,
                    normalized_categorical_features=list(ordinal_encodings),
                )

                # Validated raw values aligned to feature_names, including any
                # deliberate per-model defaults applied above. Used below to
                # build the model-ready matrix and the echoed "input_data".
                raw_input_data = _build_input_array(normalized_inputs, feature_names)
                batch_size = raw_input_data.shape[0]
                logger.debug(
                    "Inference input: batch_size=%d, features=%d, expected=%s",
                    batch_size, raw_input_data.shape[1] if raw_input_data.ndim == 2 else 0, list(feature_names),
                )

                # Reapply the same categorical encoding fitted at training time
                # (if any) so the matrix handed to the model has the exact
                # columns it was trained on, instead of the raw (pre-encoding)
                # feature names. No-op for models with no categorical features
                # or legacy models that predate this metadata.
                label_columns = list(label_encodings.keys())
                ordinal_columns = list(ordinal_encodings.keys())

                encoded_feature_columns = (
                    categorical_columns + categorical_columns_no_drop + label_columns + ordinal_columns
                )

                # Build every output column by name first, then assemble the
                # final matrix in the exact order the model was actually fit
                # on (persisted as model_input_columns - see TrainModelNode).
                # A fixed "all numeric, then all label, then all ordinal,
                # then one-hot" grouping silently moves label/ordinal columns
                # away from wherever they actually sat in the training column
                # order whenever any numeric column came after them in the
                # original feature list - this builds by name and lets the
                # persisted order (not a hardcoded grouping) decide position.
                column_arrays: Dict[str, np.ndarray] = {}

                if encoded_feature_columns:
                    numeric_order = [f for f in feature_names if f not in encoded_feature_columns]
                    numeric_data = (
                        _build_input_array(normalized_inputs, numeric_order).astype(float)
                        if numeric_order else np.empty((batch_size, 0))
                    )
                    for i, col in enumerate(numeric_order):
                        column_arrays[col] = numeric_data[:, i]

                    legacy_order = list(numeric_order)

                    if label_columns:
                        label_data = _mapped_transform(
                            normalized_inputs, label_columns, label_encodings, batch_size, unseen_value=-1
                        )
                        for i, col in enumerate(label_columns):
                            column_arrays[col] = label_data[:, i]
                        legacy_order += label_columns

                    if ordinal_columns:
                        ordinal_data = _mapped_transform(
                            normalized_inputs, ordinal_columns, ordinal_encodings, batch_size,
                            unseen_value=np.nan, normalize_keys=True,
                        )
                        for i, col in enumerate(ordinal_columns):
                            column_arrays[col] = ordinal_data[:, i]
                        legacy_order += ordinal_columns

                    if encoder is not None and categorical_columns:
                        encoded, encoded_columns = _one_hot_transform(normalized_inputs, categorical_columns, encoder)
                        for i, col in enumerate(encoded_columns):
                            column_arrays[col] = encoded[:, i]
                        legacy_order += encoded_columns

                    if encoder_no_drop is not None and categorical_columns_no_drop:
                        encoded_nd, encoded_nd_columns = _one_hot_transform(
                            normalized_inputs, categorical_columns_no_drop, encoder_no_drop
                        )
                        for i, col in enumerate(encoded_nd_columns):
                            column_arrays[col] = encoded_nd[:, i]
                        legacy_order += encoded_nd_columns
                else:
                    for i, col in enumerate(feature_names):
                        column_arrays[col] = raw_input_data[:, i]
                    legacy_order = list(feature_names)

                # Recompute any engineered features (bin_numeric, normalize,
                # standardize, polynomial, custom_expression) from the raw
                # inputs, using the exact fitted parameters captured at
                # training time (TrainModelNode._engineer_features). No-op
                # for models with no feature engineering or legacy models
                # that predate this metadata.
                feature_engineering_steps = metadata.get("feature_engineering_steps") or []
                if feature_engineering_steps:
                    engineered = _replay_feature_engineering(normalized_inputs, feature_engineering_steps, batch_size)
                    column_arrays.update(engineered)
                    legacy_order += [c for c in engineered if c not in legacy_order]

                # The real training-time column order, when available, always
                # wins over the grouped fallback above.
                model_input_columns = metadata.get("model_input_columns")
                model_feature_names = list(model_input_columns) if model_input_columns else legacy_order

                missing_columns = [c for c in model_feature_names if c not in column_arrays]
                if missing_columns:
                    error = ValueError(
                        f"Could not reconstruct column(s) {missing_columns} that the model "
                        "was trained on - the saved model metadata may be incomplete or from "
                        "an incompatible older version."
                    )
                    raise AppException(error_key=ErrorKey.INTERNAL_ERROR, error_detail=str(error))

                input_data = np.column_stack([column_arrays[c] for c in model_feature_names])

                # Reapply the scaler fitted at training time (if any) so scaled
                # features match what the model was trained on. No-op for
                # models trained with scalingMethod "none" or legacy models
                # that predate this metadata.
                scaler = metadata.get("scaler")
                scaled_columns = metadata.get("scaled_columns") or []
                if scaler is not None and scaled_columns:
                    scaled_indices = [
                        model_feature_names.index(c) for c in scaled_columns if c in model_feature_names
                    ]
                    if scaled_indices:
                        input_data = input_data.astype(float)
                        input_data[:, scaled_indices] = scaler.transform(input_data[:, scaled_indices])
            except AppException:
                raise
            except Exception as e:
                logger.error("Data preparation failed: %s", e, exc_info=True)
                if defaults_applied:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=(
                            "Data preparation failed after configured feature default(s) were applied "
                            f"for: {', '.join(defaults_applied)}. "
                            f"Cause: {_summarize_error(e)}"
                        ),
                    ) from e
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"Data preparation failed: {e}"
                ) from e

            # Make prediction (always returns batch format)
            try:
                if not hasattr(model, "predict"):
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR, error_detail="Model does not have predict method"
                    )

                # Get model-derived class labels. Regressors do not expose classes_.
                class_labels = getattr(model, "classes_", None)

                # Use predict_proba when available to avoid a redundant forward pass
                probabilities: Optional[np.ndarray] = None
                if hasattr(model, "predict_proba") and class_labels is not None:
                    try:
                        probabilities = model.predict_proba(input_data)
                        predictions = np.asarray(class_labels)[np.argmax(probabilities, axis=1)]
                    except Exception:
                        probabilities = None
                        predictions = model.predict(input_data)
                else:
                    predictions = model.predict(input_data)

                # Reconstruct real-unit predictions for a model trained on a
                # ratio target (target / baselineColumn - see TrainModelNode's
                # targetTransform). Without this, predictions come back as the
                # raw ratio (e.g. 0.73) instead of the real-unit value the
                # caller expects (e.g. 54750). No-op for models with no
                # targetTransform or legacy models that predate this metadata.
                if target_transform is not None:
                    baseline_column = target_transform.get("baselineColumn")
                    if baseline_column not in normalized_inputs:
                        raise AppException(
                            error_key=ErrorKey.MISSING_PARAMETER,
                            error_detail=(
                                f"This model was trained on a ratio target "
                                f"('{ml_model.target_variable}' / '{baseline_column}'); "
                                f"'{baseline_column}' must be supplied as an inference input so "
                                "predictions can be converted back to real units."
                            ),
                        )
                    baseline_values = _build_input_array(
                        normalized_inputs, [baseline_column]
                    ).astype(float)[:, 0]
                    predictions = predictions * baseline_values

                # Build response (always batch format)
                # Convert the raw (pre-encoding) input to a column-wise dictionary
                # (columns ordered by feature_names) so the echoed input reflects
                # what the caller actually submitted, not the expanded matrix
                # handed to the model.
                input_data_by_column = {
                    feature_names[i]: raw_input_data[:, i].tolist()
                    for i in range(len(feature_names))
                }

                prediction_values, prediction_labels, prediction_entries = _build_prediction_outputs(
                    predictions, class_labels
                )

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
                    "defaults_applied": defaults_applied,
                    # Backward-compatible flat output keys, preserving model value types.
                    "prediction": prediction_values,
                    "prediction_label": prediction_labels,
                    # New structured entries for drag-and-drop variable binding, e.g.
                    # {{source.prediction_details[0].result}}. Additive — does not replace
                    # the flat `prediction` field above.
                    "prediction_details": prediction_entries,
                }

                # Add probabilities and confidence
                if probabilities is not None:
                    probability_outputs, confidences = _build_probability_outputs(probabilities, class_labels)
                    result["probabilities"] = probability_outputs
                    result["confidences"] = confidences
                if inference_warnings:
                    result["warnings"] = inference_warnings

                logger.info("Prediction complete: %d rows for model %s", batch_size, model_id)
                return result

            except AppException:
                raise
            except Exception as e:
                logger.error("Error during model prediction: %s", e, exc_info=True)
                if defaults_applied:
                    raise AppException(
                        error_key=ErrorKey.INTERNAL_ERROR,
                        error_detail=(
                            "Prediction failed after configured feature default(s) were applied for: "
                            f"{', '.join(defaults_applied)}. "
                            f"Cause: {_summarize_error(e)}"
                        ),
                    ) from e
                raise AppException(
                    error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"Error during model prediction: {e}"
                ) from e

        except AppException:
            # Re-raise AppException as is
            raise
        except Exception as e:
            logger.error("Unexpected error in ML model inference: %s", e, exc_info=True)
            raise AppException(error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"ML model inference failed: {e}") from e

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
