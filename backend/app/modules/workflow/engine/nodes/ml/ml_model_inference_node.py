"""
ML Model Inference node implementation using the BaseNode class.
"""

import json
import logging
import re
from numbers import Number
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

import numpy as np
import pandas as pd

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.ml_model_feature_contract import (
    _match_registered_feature_names,
    _model_feature_count,
    _normalize_estimator_feature_names,
    _resolve_artifact_metadata,
    _resolve_estimator_feature_names,
)
from app.dependencies.injector import injector
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.nodes.ml.ml_utils import (
    COLUMN_TRANSFORM_STRATEGY_LABELS,
    apply_column_transform,
    column_transform_value_problem,
    column_transform_value_problem_code,
    normalize_feature_expression,
    ordinal_key,
)
from app.schemas.ml_model import FEATURE_DEFAULTS_PARAM
from app.services.ml_model_manager import get_ml_model_manager, local_model_file
from app.services.ml_models import MLModelsService

logger = logging.getLogger(__name__)

_BOOL_TRUE = frozenset({"true"})
_BOOL_FALSE = frozenset({"false"})
_INT_PATTERN = re.compile(r"[+-]?[0-9]+")
_FLOAT_PATTERN = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)


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
    # One rule for numbers: plain integers become int, other decimal or
    # scientific notation becomes float. Python's own int()/float() would
    # also accept "1_000", "inf" and "nan", which are not valid inputs, so
    # those stay text and are rejected where a number is required.
    if _INT_PATTERN.fullmatch(stripped):
        try:
            return int(stripped)
        except ValueError:
            return val
    if _FLOAT_PATTERN.fullmatch(stripped):
        converted = float(stripped)
        return converted if np.isfinite(converted) else val
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
            raise AppException(
                error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                error_detail=(
                    f"Invalid value(s) for feature '{_format_error_value(col)}': "
                    f"{_format_value_list(invalid_values)}. The request was rejected "
                    "because one or more values are not configured for this model."
                ),
            )


def _validate_ordinal_inputs(
    normalized_inputs: Dict[str, List[Any]],
    ordinal_columns: Sequence[str],
    ordinal_encodings: Dict[str, Dict[Any, Any]],
) -> None:
    """Reject an ordinal value that has no position in the fitted order.

    Training refuses such values rather than turning them into missing
    (TrainModelNode._encode_categoricals), so inference does the same instead
    of encoding them as NaN - which most models reject with a vague error and
    XGBoost/LightGBM/HistGradientBoosting silently treat as missing. Values
    are matched with ordinal_key, exactly as training matches them; missing
    values stay missing, as they do in training.
    """
    for col in ordinal_columns:
        if col not in normalized_inputs:
            continue
        mapping = ordinal_encodings.get(col) or {}
        known_keys = {ordinal_key(k) for k in mapping}
        invalid_value_rows: Dict[str, List[int]] = {}
        for row, value in enumerate(normalized_inputs[col], start=1):
            key = ordinal_key(value)
            if key is None or key in known_keys:
                continue
            invalid_value_rows.setdefault(str(value), []).append(row)
        if invalid_value_rows:
            raise AppException(
                error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                error_detail=(
                    f"Invalid value(s) for ordinal feature '{_format_error_value(col)}': "
                    f"{_format_value_rows(invalid_value_rows)}. The request was rejected because "
                    "one or more values have no configured ordinal position."
                ),
            )


_MAX_LISTED_VALUES = 5
_MAX_DISPLAY_VALUE_LENGTH = 40


def _format_error_value(value: Any) -> str:
    """Bound an input value before including it in a client-safe error."""
    text = str(value)
    if len(text) <= _MAX_DISPLAY_VALUE_LENGTH:
        return text
    return f"{text[: _MAX_DISPLAY_VALUE_LENGTH - 1]}…"


def _format_value_list(values: Sequence[Any], limit: int = _MAX_LISTED_VALUES) -> str:
    """Join bounded caller values without exceeding the client detail budget."""
    items = [_format_error_value(value) for value in values]
    if len(items) <= limit:
        return ", ".join(items)
    return f"{', '.join(items[:limit])} … {len(items) - limit} more"


def _format_value_rows(
    value_rows: Dict[str, List[int]], limit: int = _MAX_LISTED_VALUES
) -> str:
    """Pair each bounded invalid value with its affected input rows."""
    entries = list(value_rows.items())
    formatted = []
    for value, rows in entries[:limit]:
        row_label = "row" if len(rows) == 1 else "rows"
        formatted.append(
            f"{_format_error_value(value)} ({row_label} {_format_value_list(rows)})"
        )
    if len(entries) > limit:
        formatted.append(f"… {len(entries) - limit} more values")
    return "; ".join(formatted)


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


def _is_unresolved_upstream_value(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() == "null"


def _summarize_error(error: Exception) -> str:
    detail = str(error).strip()
    return detail.splitlines()[0][:200] if detail else type(error).__name__


def _feature_defaults(
    inference_params: Any,
    legacy_defaults: Any = None,
) -> Dict[str, Any]:
    """Combine historical training fills with configured per-feature defaults."""
    if inference_params and not isinstance(inference_params, dict):
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail="Model inference parameters must be an object.",
        )

    configured_defaults = (
        inference_params.get(FEATURE_DEFAULTS_PARAM)
        if isinstance(inference_params, dict)
        else None
    ) or {}
    if not isinstance(configured_defaults, dict):
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=f"Model inference parameter '{FEATURE_DEFAULTS_PARAM}' must be an object.",
        )

    training_fills = legacy_defaults or {}
    if not isinstance(training_fills, dict):
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail="Model artifact training fills must be an object.",
        )

    return {**training_fills, **configured_defaults}


def _prepare_inference_inputs(
    normalized_inputs: Dict[str, List[Any]],
    feature_names: Sequence[str],
    defaults: Optional[Dict[str, Any]] = None,
    allowed_extra_features: Optional[Sequence[str]] = None,
    categorical_features: Optional[Sequence[str]] = None,
    categorical_values: Optional[Dict[str, set[Any]]] = None,
    normalized_categorical_features: Optional[Sequence[str]] = None,
    default_feature_names: Optional[Sequence[str]] = None,
    inference_warnings: Optional[List[str]] = None,
) -> tuple[Dict[str, List[Any]], List[str]]:
    """Validate required inputs, apply defaults, and ignore stale extra inputs."""
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

    default_feature_set = (
        expected_set
        if default_feature_names is None
        else set(default_feature_names)
    )
    unknown_defaults = [name for name in defaults if name not in default_feature_set]
    if unknown_defaults:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                f"Model default(s) configured for unknown feature(s): {', '.join(unknown_defaults)}. "
                f"Registered model features: {', '.join(default_feature_names or expected_features)}."
            ),
        )

    unused_defaults = [name for name in defaults if name not in expected_set]
    if unused_defaults and inference_warnings is not None:
        inference_warnings.append(
            "Ignored feature default(s) that are not part of this artifact's input contract: "
            f"{', '.join(unused_defaults)}."
        )
    defaults = {name: value for name, value in defaults.items() if name in expected_set}

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
    prepared_defaults = {}
    for name, value in defaults.items():
        if name not in defaults_to_apply:
            continue
        if name in categorical_values:
            prepared_defaults[name] = _convert_categorical_input(
                value,
                categorical_values[name],
                name in normalized_categorical_feature_set,
            )
        elif categorical_feature_set is not None and name in categorical_feature_set:
            prepared_defaults[name] = value
        else:
            prepared_defaults[name] = convert_value(value)

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
                "Inference fallback value(s) must be non-null scalar values for: "
                f"{', '.join(invalid_defaults)}."
            ),
        )

    invalid_numeric_defaults = []
    for name, value in prepared_defaults.items():
        if categorical_feature_set is not None and name in categorical_feature_set:
            continue
        if _numeric_value_problem(
            value,
            allow_text=categorical_feature_set is None,
        ) is not None:
            invalid_numeric_defaults.append(name)
    if invalid_numeric_defaults:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                "Inference fallback value(s) for numeric feature(s) must be finite scalar "
                "numbers or booleans: "
                f"{', '.join(invalid_numeric_defaults)}."
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
                "Invalid categorical default or saved training fill(s): "
                f"{', '.join(invalid_categorical_defaults)}. Each categorical fallback must "
                "match a category fitted by the model."
            ),
        )

    unexpected_features = [
        name for name in normalized_inputs if name not in expected_set and name not in allowed_extra_set
    ]
    if unexpected_features:
        warning = (
            "Ignored unexpected inference input(s): "
            f"{', '.join(unexpected_features)}. Accepted inference inputs: "
            f"{', '.join(expected_features + sorted(allowed_extra_set))}."
        )
        logger.warning(warning)
        if inference_warnings is not None:
            inference_warnings.append(warning)
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
    unresolved_upstream_features = [
        name
        for name in unfilled_features
        if name in normalized_inputs
        and any(_is_unresolved_upstream_value(value) for value in normalized_inputs[name])
    ]
    if unresolved_upstream_features:
        problems.append(
            "Unresolved upstream value(s) for feature(s): "
            f"{', '.join(unresolved_upstream_features)}. A value of 'null' means the "
            "upstream node did not produce that field. Fix the upstream node output before "
            "running inference."
        )
        problems.append(
            f"Required model features: {', '.join(expected_features)}."
        )
    elif unfilled_features:
        problems.append(
            f"Provide every value or configure '{FEATURE_DEFAULTS_PARAM}' in the model's inference parameters. "
            f"Required model features: {', '.join(expected_features)}."
        )
    if problems:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=" ".join(problems),
        )

    prepared_inputs = {
        name: values
        for name, values in normalized_inputs.items()
        if name not in unexpected_features
    }
    batch_size = _infer_batch_size(prepared_inputs) or 1
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


def _numeric_value_problem(value: Any, allow_text: bool) -> Optional[str]:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, (bool, np.bool_)):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if _FLOAT_PATTERN.fullmatch(stripped):
            try:
                if not np.isfinite(float(stripped)):
                    return "not finite"
            except ValueError:
                pass
        return None if allow_text else "not numeric"
    if isinstance(value, (dict, list, tuple, set)) or value is None:
        return "not numeric"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        if allow_text and not isinstance(value, Number):
            return None
        return "not numeric"
    return None if np.isfinite(numeric_value) else "not finite"


def _wrapped_model_candidates(model: Any) -> List[Any]:
    """Return a model and fitted estimators held by supported wrappers."""
    candidates = []
    pending = [model]
    visited = set()
    while pending:
        candidate = pending.pop()
        if candidate is None or id(candidate) in visited:
            continue
        visited.add(id(candidate))
        candidates.append(candidate)
        pending.extend(
            getattr(candidate, attr, None)
            for attr in ("best_estimator_", "regressor_")
        )
    return candidates


def _model_accepts_raw_text_features(model: Any) -> bool:
    """Return whether a fitted pipeline owns raw feature preprocessing."""
    for candidate in _wrapped_model_candidates(model):
        module_root = type(candidate).__module__.split(".", 1)[0]
        steps = getattr(candidate, "steps", None)
        if module_root in {"sklearn", "imblearn"} and isinstance(
            steps, (list, tuple)
        ) and bool(steps):
            return True
    return False


def _selected_feature_names(
    selector: Any, feature_names: Sequence[str]
) -> List[str]:
    """Resolve fitted column-transformer selectors to model feature names."""
    if isinstance(selector, str):
        return [selector] if selector in feature_names else []
    if isinstance(selector, (int, np.integer)) and not isinstance(
        selector, (bool, np.bool_)
    ):
        index = int(selector)
        return [feature_names[index]] if 0 <= index < len(feature_names) else []
    if isinstance(selector, slice):
        return list(feature_names[selector])
    if not isinstance(selector, (list, tuple, np.ndarray, pd.Index)):
        return []

    selected = list(selector)
    if len(selected) == len(feature_names) and all(
        isinstance(value, (bool, np.bool_)) for value in selected
    ):
        return [
            name for name, is_selected in zip(feature_names, selected) if is_selected
        ]

    names = []
    for value in selected:
        if isinstance(value, str) and value in feature_names:
            names.append(value)
        elif isinstance(value, (int, np.integer)) and not isinstance(
            value, (bool, np.bool_)
        ):
            index = int(value)
            if 0 <= index < len(feature_names):
                names.append(feature_names[index])
    return names


def _transformer_categories(transformer: Any) -> Optional[List[Any]]:
    if transformer is None or (
        isinstance(transformer, str) and transformer in {"drop", "passthrough"}
    ):
        return None
    categories = getattr(transformer, "categories_", None)
    if isinstance(categories, (list, tuple)):
        return list(categories)
    steps = getattr(transformer, "steps", None)
    if isinstance(steps, (list, tuple)):
        for _, step_transformer in reversed(steps):
            categories = _transformer_categories(step_transformer)
            if categories is not None:
                return categories
    return None


def _pipeline_categorical_values(
    pipeline: Any, feature_names: Sequence[str]
) -> Dict[str, set[Any]]:
    categorical_values: Dict[str, set[Any]] = {}
    steps = getattr(pipeline, "steps", None)
    if not isinstance(steps, (list, tuple)):
        return categorical_values

    for _, transformer in steps:
        fitted_transformers = getattr(transformer, "transformers_", None)
        if isinstance(fitted_transformers, (list, tuple)):
            for _, column_transformer, selector in fitted_transformers:
                selected_names = _selected_feature_names(selector, feature_names)
                categories = _transformer_categories(column_transformer)
                if categories is None or len(categories) != len(selected_names):
                    continue
                categorical_values.update(
                    {
                        name: {_category_key(value) for value in values.tolist()}
                        for name, values in zip(selected_names, categories)
                    }
                )
            continue

        categories = _transformer_categories(transformer)
        if categories is not None and len(categories) == len(feature_names):
            categorical_values.update(
                {
                    name: {_category_key(value) for value in values.tolist()}
                    for name, values in zip(feature_names, categories)
                }
            )
    return categorical_values


def _model_native_text_features(
    model: Any, feature_names: Sequence[str]
) -> set[str]:
    """Return named features a fitted estimator handles as text itself."""
    text_features = set()
    for candidate in _wrapped_model_candidates(model):
        text_features.update(
            _pipeline_categorical_values(candidate, feature_names)
        )
        candidate_names = _normalize_estimator_feature_names(
            getattr(candidate, "feature_names_", None),
            None,
        ) or list(feature_names)
        if candidate_names == [str(index) for index in range(len(candidate_names))]:
            candidate_names = list(feature_names)
        for getter_name in (
            "get_cat_feature_indices",
            "get_text_feature_indices",
        ):
            getter = getattr(candidate, getter_name, None)
            if not callable(getter):
                continue
            try:
                indices = getter()
            except Exception:
                continue
            for index in indices or []:
                if (
                    isinstance(index, (int, np.integer))
                    and not isinstance(index, (bool, np.bool_))
                    and 0 <= int(index) < len(candidate_names)
                ):
                    text_features.add(candidate_names[int(index)])
    return text_features


def _model_native_categorical_values(
    model: Any, feature_names: Sequence[str]
) -> Dict[str, set[Any]]:
    """Return fitted categories owned by model-native preprocessing."""
    categorical_values: Dict[str, set[Any]] = {}
    for candidate in _wrapped_model_candidates(model):
        categorical_values.update(
            _pipeline_categorical_values(candidate, feature_names)
        )
    return categorical_values


def _validate_numeric_inputs(
    normalized_inputs: Dict[str, List[Any]],
    numeric_features: Sequence[str],
    allow_text: bool,
    text_features: Optional[Sequence[str]] = None,
) -> None:
    """Reject invalid scalar numbers while preserving supported text."""
    allowed_text_features = set(text_features or [])
    problems = []
    for name in numeric_features:
        invalid_value_rows: Dict[str, List[int]] = {}
        has_more = False
        for row_number, value in enumerate(
            normalized_inputs.get(name, []), start=1
        ):
            if name in allowed_text_features and isinstance(value, str):
                continue
            if _numeric_value_problem(value, allow_text) is None:
                continue
            value_text = _format_error_value(value)
            if (
                value_text not in invalid_value_rows
                and len(invalid_value_rows) >= _MAX_LISTED_VALUES
            ):
                has_more = True
                break
            rows = invalid_value_rows.setdefault(value_text, [])
            if len(rows) < _MAX_LISTED_VALUES:
                rows.append(row_number)
        if invalid_value_rows:
            suffix = " …" if has_more else ""
            problems.append(
                f"'{_format_error_value(name)}': "
                f"{_format_value_rows(invalid_value_rows)}{suffix}"
            )
    if problems:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                "Numeric feature(s) received values that are not valid finite numbers: "
                f"{'; '.join(problems)}. Use plain numbers such as 1000, 2.5 or 1e5."
            ),
        )


def _echo_input_columns(
    normalized_inputs: Dict[str, List[Any]],
    feature_names: Sequence[str],
    batch_size: int,
) -> Dict[str, List[Any]]:
    """Echo the prepared inputs column by column, so each value keeps its own
    type. A single combined numpy array would turn every value into a string
    as soon as one feature is text (1.5 -> "1.5", True -> "True")."""
    return {
        name: [
            _json_safe_scalar(value)
            for value in _broadcast_column(normalized_inputs[name], batch_size, name)
        ]
        for name in feature_names
    }


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
    missing = [col for col in columns if col not in normalized_inputs]
    if missing:
        raise ValueError(f"Missing prepared feature column(s): {', '.join(missing)}")
    out = np.empty((batch_size, len(columns)), dtype=float)
    for i, col in enumerate(columns):
        # Preserve each original value type. np.column_stack can stringify
        # mixed values either across columns or within one batch column.
        values = np.asarray(
            _broadcast_column(normalized_inputs[col], batch_size, col),
            dtype=object,
        )
        mapping = mappings.get(col, {})
        if normalize_keys:
            mapping = {ordinal_key(k): v for k, v in mapping.items()}
            out[:, i] = [mapping.get(ordinal_key(v), unseen_value) for v in values]
        else:
            mapping = {_category_key(k): v for k, v in mapping.items()}
            out[:, i] = [
                mapping.get(_category_key(v), unseen_value) for v in values
            ]
    return out


def _json_safe_scalar(value: Any) -> Any:
    """Convert NumPy scalars to JSON-safe Python scalar values."""
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, (list, tuple)):
        return [_json_safe_scalar(item) for item in value]

    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool, type(None))):
        return value

    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
    return value


def _prediction_array(raw_predictions: Any) -> np.ndarray:
    """Normalize model output without coercing mixed Python values to text."""
    try:
        predictions = np.asarray(raw_predictions)
    except ValueError:
        return np.asarray(raw_predictions, dtype=object)

    if (
        isinstance(raw_predictions, (list, tuple))
        and predictions.dtype.kind in {"S", "U"}
    ):
        object_predictions = np.asarray(raw_predictions, dtype=object)
        if any(
            not isinstance(value, (str, np.str_))
            for value in object_predictions.flat
        ):
            return object_predictions
    return predictions


def _validated_ratio_baseline_values(
    normalized_inputs: Dict[str, List[Any]],
    baseline_column: Any,
    batch_size: int,
    target_variable: Any,
) -> np.ndarray:
    """Return finite, non-zero numeric baseline values aligned to the batch."""
    if not isinstance(baseline_column, str) or not baseline_column:
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail="Ratio-target metadata does not identify a baseline column.",
        )

    if baseline_column not in normalized_inputs:
        raise AppException(
            error_key=ErrorKey.MISSING_PARAMETER,
            error_detail=(
                "This model was trained on a ratio target "
                f"('{target_variable}' / '{baseline_column}'); "
                f"'{baseline_column}' must be supplied as an inference input so "
                "predictions can be converted back to real units."
            ),
        )

    raw_values = _broadcast_column(
        normalized_inputs[baseline_column],
        batch_size,
        baseline_column,
    )
    baseline_values = np.empty(len(raw_values), dtype=float)
    invalid_rows = []
    for row_number, value in enumerate(raw_values, start=1):
        reason = None
        if (isinstance(value, str) and not value.strip()) or _is_missing_value(value):
            reason = "missing"
        elif isinstance(value, (bool, np.bool_)):
            reason = "not numeric"
        else:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError, OverflowError):
                reason = "not numeric"
            else:
                if not np.isfinite(numeric_value):
                    reason = "not finite"
                elif numeric_value == 0:
                    reason = "zero"
                else:
                    baseline_values[row_number - 1] = numeric_value
        if reason is not None:
            invalid_rows.append(f"{row_number} ({reason})")

    if invalid_rows:
        displayed_rows = invalid_rows[:10]
        omitted_row_count = len(invalid_rows) - len(displayed_rows)
        invalid_rows_detail = ", ".join(displayed_rows)
        if omitted_row_count:
            invalid_rows_detail += f", and {omitted_row_count} more"
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                f"Invalid value(s) for ratio baseline '{baseline_column}' at row(s): "
                f"{invalid_rows_detail}. Baseline values must be numeric, finite, and non-zero."
            ),
        )

    return baseline_values


def _apply_ratio_target_transform(
    predictions: np.ndarray,
    baseline_values: np.ndarray,
) -> np.ndarray:
    """Scale each prediction row by its corresponding ratio baseline."""
    if predictions.ndim == 0 or predictions.shape[0] != len(baseline_values):
        prediction_rows = 0 if predictions.ndim == 0 else predictions.shape[0]
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail=(
                "Ratio-target model returned "
                f"{prediction_rows} prediction row(s) for "
                f"{len(baseline_values)} baseline row(s)."
            ),
        )
    baseline_shape = (len(baseline_values),) + (1,) * max(predictions.ndim - 1, 0)
    return predictions * baseline_values.reshape(baseline_shape)


def _describe_feature_names(names: Any) -> str:
    if isinstance(names, np.ndarray):
        names = names.tolist()
    if isinstance(names, (list, tuple)):
        return f"[{', '.join(repr(name) for name in names)}]"
    return repr(names)


def _resolve_feature_order(
    metadata: Dict[str, Any],
    model: Any,
    model_name: str,
    registered_names: Any = None,
    metadata_is_authoritative: bool = False,
) -> tuple[List[str], List[str], str]:
    module_root = type(model).__module__.split(".", 1)[0]
    expected_feature_count = _model_feature_count(model)
    estimator_names = _resolve_estimator_feature_names(
        model,
        module_root,
        expected_feature_count,
    )

    if metadata_is_authoritative:
        recorded_names = _normalize_estimator_feature_names(
            metadata.get("feature_columns"),
            None,
        )
        if recorded_names is not None:
            return recorded_names, estimator_names or [], "artifact_metadata"
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                f"Model '{model_name}' artifact does not record its required feature set. "
                "Its feature_columns metadata must be a non-empty, unique list of names. "
                "Retrain and upload a complete model artifact."
            ),
        )

    if estimator_names is not None:
        caller_names = _match_registered_feature_names(
            estimator_names,
            registered_names,
            module_root,
        )
        if caller_names is not None:
            return caller_names, estimator_names, "estimator"
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                f"Model '{model_name}' records estimator feature names "
                f"{_describe_feature_names(estimator_names)}, but its registered features are "
                f"{_describe_feature_names(registered_names)}. Update the registered feature "
                "list to contain the same names. Retrain only if the estimator names are incorrect."
            ),
        )

    raise AppException(
        error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
        error_detail=(
            "Feature order source: refused. "
            f"Model '{model_name}' does not record a safe, unambiguous feature-name order, "
            "so an unknown order could "
            "swap values between columns. Registry order was not used as a substitute. "
            "Please retrain it on data with named columns (a pandas DataFrame), ensure "
            "those names match the registered features, and upload the new file."
        ),
    )


def _step_output_columns(step: Dict[str, Any]) -> List[str]:
    """The model columns a feature-engineering step produces."""
    strategy = step.get("strategy")
    if strategy in ("normalize", "standardize"):
        return [stats.get("out_col") for stats in (step.get("column_stats") or {}).values()]
    if strategy == "polynomial":
        return list(step.get("new_names") or [])
    if strategy in COLUMN_TRANSFORM_STRATEGY_LABELS:
        return list(step.get("output_columns") or [])
    return [step.get("new_col")]


def _replay_input_error_detail(step: Dict[str, Any], cause: str) -> str:
    feature = step.get("new_col") or step.get("feature")
    return (
        f"Could not compute engineered feature '{feature}' "
        f"(step '{step.get('strategy')}') from the inputs: {cause}. "
        "Check the input values this feature is calculated from."
    )


def _record_replay_problem(
    problems: Optional[List[Dict[str, Any]]],
    failed_columns: Dict[str, tuple[str, bool]],
    available: Dict[str, List[Any]],
    available_frame: pd.DataFrame,
    computed: Dict[str, np.ndarray],
    step: Dict[str, Any],
    cause: str,
    outputs: Optional[List[str]] = None,
    input_problem: bool = True,
    log_cause: Optional[str] = None,
) -> None:
    outputs = [c for c in (outputs if outputs is not None else _step_output_columns(step)) if c]
    for column in outputs:
        failed_columns[column] = (step.get("new_col") or column, input_problem)
        available.pop(column, None)
        computed.pop(column, None)
        if column in available_frame.columns:
            available_frame.drop(columns=[column], inplace=True)
    logger.warning(
        "Failed to replay feature-engineering step '%s' (%s) at inference: %s",
        step.get("new_col"), step.get("strategy"), log_cause or cause,
    )
    if problems is None:
        if input_problem:
            raise AppException(
                error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                error_detail=_replay_input_error_detail(step, cause),
            )
        return
    problems.append({
        "feature": step.get("new_col"),
        "strategy": step.get("strategy"),
        "cause": cause,
        "outputs": outputs,
        "input_problem": input_problem,
    })


def _missing_step_inputs_problem(
    absent: List[str], failed_columns: Dict[str, tuple[str, bool]]
) -> tuple[str, str, bool]:
    """Explain why a step's input columns are absent, pointing at the earlier
    step that failed to produce them when that is the reason. The boolean
    says whether the root cause came from caller input rather than metadata."""
    raw_inputs = [column for column in absent if column not in failed_columns]
    upstream_failures = [failed_columns[column] for column in absent if column in failed_columns]
    upstream = sorted({feature for feature, _ in upstream_failures})
    client_causes = []
    log_causes = []
    if raw_inputs:
        message = f"input column(s) {raw_inputs} were not provided"
        client_causes.append(message)
        log_causes.append(message)
    if upstream:
        client_causes.append(
            "other required engineered input(s) could not be computed because an earlier step failed"
        )
        log_causes.append(
            f"input column(s) {[column for column in absent if column in failed_columns]} "
            f"could not be computed because engineered feature(s) {upstream} failed first"
        )
    input_problem = not raw_inputs and (
        bool(upstream_failures)
        and all(problem_is_input for _, problem_is_input in upstream_failures)
    )
    return "; ".join(client_causes), "; ".join(log_causes), input_problem


def _validate_replay_expression(
    expression: str,
    available_frame: pd.DataFrame,
    failed_columns: Dict[str, tuple[str, bool]],
) -> tuple[List[str], Optional[Exception]]:
    """Validate saved expression syntax independently from caller values."""
    placeholder = pd.DataFrame({column: [1.0] for column in available_frame.columns})
    try:
        placeholder.eval(expression)
        return [], None
    except Exception as original_error:
        if not failed_columns:
            return [], original_error

    with_failed = placeholder.copy()
    for column in failed_columns:
        with_failed[column] = 1.0
    try:
        with_failed.eval(expression)
    except Exception as error:
        return [], error

    referenced = []
    for column in failed_columns:
        try:
            with_failed.drop(columns=[column]).eval(expression)
        except Exception:
            referenced.append(column)
    return referenced, None


def _raise_for_replay_problems(
    problems: List[Dict[str, Any]], missing_columns: Sequence[str]
) -> None:
    """Raise the first caller-input problem behind a missing model column.

    Metadata problems fall through to the reconstruction error, while failed
    outputs the model does not need cannot block an otherwise valid request.
    """
    needed = set(missing_columns)
    for problem in problems:
        if problem["input_problem"] and needed.intersection(problem["outputs"]):
            raise AppException(
                error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                error_detail=_replay_input_error_detail(problem, problem["cause"]),
            )


def _replay_feature_engineering(
    normalized_inputs: Dict[str, List[Any]],
    steps: List[Dict[str, Any]],
    batch_size: int,
    problems: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, np.ndarray]:
    """Recompute engineered feature columns from raw caller-supplied inputs,
    using the exact fitted parameters (bin edges, mean/std, fitted
    PolynomialFeatures transformer) captured at training time - see
    TrainModelNode._engineer_features, which returns these same steps.

    Steps run in the same order they were trained in. A later step can
    reference an earlier step's new column (e.g. a polynomial feature built
    from a normalized one), same as at training time, so each computed
    column is folded into `available` for subsequent steps to read.

    A step that raises, or whose input columns are absent, is recorded in
    `problems` (feature, step, cause, output columns) instead of being
    skipped silently; the caller decides whether the model needs it (see
    _raise_for_replay_problems). Steps with incomplete saved parameters are
    still skipped, which surfaces later as a metadata problem.
    """
    computed: Dict[str, np.ndarray] = {}
    available = dict(normalized_inputs)
    available_frame = pd.DataFrame({
        column: _build_input_array(available, [column])[:, 0]
        for column in available
    })
    failed_columns: Dict[str, tuple[str, bool]] = {}

    def record_problem(
        step: Dict[str, Any],
        cause: str,
        outputs: Optional[List[str]] = None,
        input_problem: bool = True,
        log_cause: Optional[str] = None,
    ) -> None:
        _record_replay_problem(
            problems,
            failed_columns,
            available,
            available_frame,
            computed,
            step,
            cause,
            outputs=outputs,
            input_problem=input_problem,
            log_cause=log_cause,
        )

    def record_absent_inputs(
        step: Dict[str, Any],
        absent: List[str],
        outputs: Optional[List[str]] = None,
    ) -> None:
        cause, log_cause, input_problem = _missing_step_inputs_problem(
            absent, failed_columns
        )
        record_problem(
            step,
            cause,
            outputs=outputs,
            input_problem=input_problem,
            log_cause=log_cause,
        )

    def record_numeric_problem(
        step: Dict[str, Any],
        error: Exception,
        outputs: Optional[List[str]] = None,
    ) -> None:
        record_problem(
            step,
            "the values used by this step must be numeric",
            outputs=outputs,
            log_cause=f"{type(error).__name__}: {_summarize_error(error)}",
        )

    def store_output(column: str, values: Any) -> None:
        output = np.asarray(values)
        computed[column] = output
        available[column] = output.tolist()
        available_frame[column] = output
        failed_columns.pop(column, None)

    for step in steps:
        strategy = step.get("strategy")
        new_col = step.get("new_col")

        try:
            if strategy == "custom_expression":
                expression = normalize_feature_expression(step.get("expression"))
                try:
                    result = np.asarray(available_frame.eval(expression))
                except Exception as e:
                    absent, expression_error = _validate_replay_expression(
                        expression, available_frame, failed_columns
                    )
                    if absent:
                        record_absent_inputs(step, absent)
                    elif expression_error is not None:
                        record_problem(
                            step,
                            "the saved expression could not be evaluated",
                            input_problem=False,
                            log_cause=(
                                f"{type(expression_error).__name__}: "
                                f"{_summarize_error(expression_error)}"
                            ),
                        )
                    elif isinstance(e, (TypeError, ValueError, ZeroDivisionError)):
                        record_problem(
                            step,
                            "the supplied values are incompatible with the configured expression",
                            log_cause=f"{type(e).__name__}: {_summarize_error(e)}",
                        )
                    else:
                        record_problem(
                            step,
                            "the saved expression could not be evaluated",
                            input_problem=False,
                            log_cause=f"{type(e).__name__}: {_summarize_error(e)}",
                        )
                    continue
                store_output(new_col, result)

            elif strategy == "bin_numeric":
                bin_column = step.get("bin_column")
                bin_edges = step.get("bin_edges") or []
                if len(bin_edges) < 2:
                    continue
                if bin_column not in available:
                    record_absent_inputs(step, [bin_column])
                    continue
                try:
                    raw = _build_input_array(available, [bin_column]).astype(float)[:, 0]
                except (TypeError, ValueError) as e:
                    record_numeric_problem(step, e)
                    continue
                clipped = np.clip(raw, bin_edges[0], bin_edges[-1])
                binned = pd.cut(
                    pd.Series(clipped), bins=bin_edges, labels=False, include_lowest=True
                ).to_numpy()
                store_output(new_col, binned)

            elif strategy in ("normalize", "standardize"):
                # Retired for new features (see train_model_node), but models
                # trained with them still need them replayed.
                for col, stats in (step.get("column_stats") or {}).items():
                    out_col = stats.get("out_col")
                    if not out_col:
                        logger.warning(
                            "Failed to replay feature-engineering step '%s' (%s) at inference: "
                            "saved column statistics for '%s' do not record an output column",
                            new_col, strategy, col,
                        )
                        continue
                    if col not in available:
                        record_absent_inputs(step, [col], outputs=[out_col])
                        continue
                    try:
                        raw = _build_input_array(available, [col]).astype(float)[:, 0]
                    except (TypeError, ValueError) as e:
                        record_numeric_problem(step, e, outputs=[out_col])
                        continue
                    try:
                        if strategy == "normalize":
                            result = (raw - stats["min"]) / (stats["max"] - stats["min"])
                        else:
                            result = (raw - stats["mean"]) / stats["std"]
                    except Exception as e:
                        record_problem(
                            step,
                            "the saved feature-engineering step could not be replayed",
                            outputs=[out_col],
                            input_problem=False,
                            log_cause=f"{type(e).__name__}: {_summarize_error(e)}",
                        )
                        continue
                    store_output(out_col, result)

            elif strategy == "polynomial":
                poly_columns = step.get("poly_columns") or []
                poly = step.get("poly")
                new_names = step.get("new_names") or []
                if not poly_columns or poly is None:
                    continue
                absent = [c for c in poly_columns if c not in available]
                if absent:
                    record_absent_inputs(step, absent)
                    continue
                try:
                    raw = _build_input_array(available, poly_columns).astype(float)
                except (TypeError, ValueError) as e:
                    record_numeric_problem(step, e)
                    continue
                poly_out = poly.transform(raw)
                new_values = poly_out[:, len(poly_columns):]
                for i, name in enumerate(new_names):
                    store_output(name, new_values[:, i])

            elif strategy in COLUMN_TRANSFORM_STRATEGY_LABELS:
                label = COLUMN_TRANSFORM_STRATEGY_LABELS[strategy]
                columns = step.get("columns") or []
                absent = [c for c in columns if c not in available]
                if absent:
                    record_absent_inputs(step, absent)
                    continue
                try:
                    raw = _build_input_array(available, columns).astype(float)
                except (TypeError, ValueError) as e:
                    record_numeric_problem(step, e)
                    continue
                problem_code = column_transform_value_problem_code(
                    strategy, raw, step.get("power_method")
                )
                problem = column_transform_value_problem(
                    strategy, raw, columns, step.get("power_method")
                )
                if problem:
                    if problem_code == "negative_log_input":
                        cause = (
                            "Log Transform needs values of 0 or more; "
                            "negative values were supplied"
                        )
                    elif problem_code == "non_positive_box_cox_input":
                        cause = "Box-Cox needs values above 0"
                    elif problem_code == "non_finite":
                        cause = "the supplied values contain empty or infinite values"
                    else:
                        cause = f"the supplied values are not valid for {label}"
                    record_problem(
                        step,
                        cause,
                        log_cause=problem,
                    )
                    continue
                out = apply_column_transform(strategy, step.get("transformer"), raw)
                for i, name in enumerate(step.get("output_columns") or []):
                    store_output(name, out[:, i])
        except AppException:
            raise
        except Exception as e:
            record_problem(
                step,
                "the saved feature-engineering step could not be replayed",
                input_problem=False,
                log_cause=f"{type(e).__name__}: {_summarize_error(e)}",
            )

    return computed


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
    probabilities: np.ndarray,
    class_labels: Sequence[Any],
    prediction_values: Sequence[Any],
) -> tuple[List[Dict[str, Any]], Optional[List[Any]]]:
    """Build probability dictionaries and confidence for each predicted class."""
    probabilities = np.asarray(probabilities)
    json_class_labels = [_json_safe_scalar(class_label) for class_label in class_labels]
    class_indexes = {}
    for index, class_label in enumerate(json_class_labels):
        try:
            class_indexes.setdefault(class_label, index)
        except TypeError:
            continue
    if probabilities.ndim != 2:
        raise ValueError("Probability output must be a two-dimensional array")
    if probabilities.shape[0] != len(prediction_values):
        raise ValueError(
            "Probability output row count does not match prediction row count"
        )
    if probabilities.shape[1] != len(json_class_labels):
        raise ValueError(
            "Probability output column count does not match model class count"
        )
    probability_outputs = [
        {f"Class_{json_class_labels[index]}": _json_safe_scalar(probability) for index, probability in enumerate(row)}
        for row in probabilities
    ]
    confidences = []
    for row, prediction in zip(probabilities, prediction_values, strict=True):
        try:
            predicted_class_index = class_indexes.get(prediction)
        except TypeError:
            return probability_outputs, None
        if predicted_class_index is None:
            return probability_outputs, None
        confidences.append(_json_safe_scalar(row[predicted_class_index]))
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
                    error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                    error_detail="modelId must be a valid UUID.",
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

            # Artifact identity/version may be a fingerprint and does not describe
            # the metadata layout. Only the metadata schema is load-bearing here.
            inference_warnings: List[str] = []
            model = model_response.get("model", {})
            metadata = _resolve_artifact_metadata(model_response)
            metadata_is_authoritative = bool(metadata)

            feature_names, estimator_feature_names, feature_order_source = (
                _resolve_feature_order(
                    metadata,
                    model,
                    ml_model.name,
                    registered_names=getattr(ml_model, "features", None),
                    metadata_is_authoritative=metadata_is_authoritative,
                )
            )

            # Prepare input array for prediction (always batch format)
            defaults_applied: List[str] = []
            ratio_baseline_values: Optional[np.ndarray] = None
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
                label_columns = list(label_encodings.keys())
                ordinal_columns = list(ordinal_encodings.keys())
                encoded_feature_columns = (
                    categorical_columns
                    + categorical_columns_no_drop
                    + label_columns
                    + ordinal_columns
                )
                model_handles_raw_text = (
                    not encoded_feature_columns
                    and _model_accepts_raw_text_features(model)
                )
                model_native_text_features = (
                    _model_native_text_features(model, feature_names)
                    if not encoded_feature_columns
                    else set()
                )
                model_native_categorical_values = (
                    _model_native_categorical_values(model, feature_names)
                    if not encoded_feature_columns
                    else {}
                )
                categorical_values.update(model_native_categorical_values)
                conversion_categorical_features = list(
                    dict.fromkeys(categorical_features + list(model_native_text_features))
                )
                inference_inputs = convert_input_types(
                    inference_inputs,
                    categorical_features=(
                        conversion_categorical_features
                        if metadata or model_native_text_features
                        else None
                    ),
                    categorical_values=(
                        categorical_values
                        if metadata or model_native_categorical_values
                        else None
                    ),
                    normalized_categorical_features=list(ordinal_encodings),
                )
                normalized_inputs = _normalize_inference_inputs(inference_inputs)
                allowed_extra_features = {
                    inference_params.get("ratioBaselineColumn")
                    if isinstance(inference_params, dict)
                    else None,
                    target_transform.get("baselineColumn") if target_transform else None,
                }
                legacy_defaults = metadata.get("missing_value_fills")
                registered_feature_names = list(
                    getattr(ml_model, "features", None) or []
                )
                default_feature_names = registered_feature_names or list(feature_names)
                if isinstance(legacy_defaults, dict):
                    registered_feature_set = set(default_feature_names)
                    expected_feature_set = set(feature_names)
                    legacy_defaults = {
                        name: value
                        for name, value in legacy_defaults.items()
                        if name in registered_feature_set and name in expected_feature_set
                    }
                configured_feature_defaults = _feature_defaults(inference_params)
                feature_defaults = _feature_defaults(
                    inference_params,
                    legacy_defaults=legacy_defaults,
                )
                normalized_inputs, defaults_applied = _prepare_inference_inputs(
                    normalized_inputs,
                    feature_names,
                    defaults=feature_defaults,
                    allowed_extra_features=allowed_extra_features,
                    categorical_features=(
                        conversion_categorical_features if metadata else None
                    ),
                    categorical_values=(
                        categorical_values
                        if metadata or model_native_categorical_values
                        else None
                    ),
                    normalized_categorical_features=list(ordinal_encodings),
                    default_feature_names=default_feature_names,
                    inference_warnings=inference_warnings,
                )
                legacy_defaults_applied = [
                    name
                    for name in defaults_applied
                    if isinstance(legacy_defaults, dict)
                    and name in legacy_defaults
                    and name not in configured_feature_defaults
                ]
                if legacy_defaults_applied:
                    inference_warnings.append(
                        "Applied saved training fill(s) as fallback defaults for: "
                        f"{', '.join(legacy_defaults_applied)}. Explicit Feature Defaults "
                        "override saved fills per feature."
                    )

                # Validated raw values aligned to feature_names, including any
                # deliberate per-model defaults applied above. Used below to
                # build the model-ready matrix and the echoed "input_data".
                batch_size = _infer_batch_size(normalized_inputs) or 1
                if target_transform is not None:
                    ratio_baseline_values = _validated_ratio_baseline_values(
                        normalized_inputs,
                        target_transform.get("baselineColumn"),
                        batch_size,
                        ml_model.target_variable,
                    )
                logger.debug(
                    "Inference input: batch_size=%d, features=%d, expected=%s",
                    batch_size, len(feature_names), list(feature_names),
                )

                # Reapply the same categorical encoding fitted at training time
                # (if any) so the matrix handed to the model has the exact
                # columns it was trained on, instead of the raw (pre-encoding)
                # feature names. No-op for models with no categorical features
                # or legacy models that predate this metadata.
                numeric_order = [f for f in feature_names if f not in encoded_feature_columns]
                _validate_numeric_inputs(
                    normalized_inputs,
                    numeric_order if metadata_is_authoritative else feature_names,
                    allow_text=(
                        not metadata_is_authoritative or model_handles_raw_text
                    ),
                    text_features=model_native_text_features,
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
                        _validate_ordinal_inputs(normalized_inputs, ordinal_columns, ordinal_encodings)
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
                    raw_input_data = _build_input_array(
                        normalized_inputs, feature_names
                    )
                    for i, col in enumerate(feature_names):
                        column_arrays[col] = raw_input_data[:, i]
                    legacy_order = list(feature_names)

                # Recompute any engineered features (bin_numeric, normalize,
                # standardize, polynomial, custom_expression) from the inputs, using the exact fitted parameters captured at
                # training time (TrainModelNode._engineer_features). No-op
                # for models with no feature engineering or legacy models
                # that predate this metadata.
                feature_engineering_steps = metadata.get("feature_engineering_steps") or []
                replay_problems: List[Dict[str, Any]] = []
                if feature_engineering_steps:
                    fe_inputs: Dict[str, List[Any]] = normalized_inputs
                    mapped_columns = label_columns + ordinal_columns
                    if metadata.get("encoding_before_feature_engineering") and mapped_columns:
                        # These models built their derived features from the
                        # label/ordinal codes, so replay them from codes too.
                        # Same order as training: missing values were already
                        # filled above (_prepare_inference_inputs), then encode.
                        fe_inputs = dict(normalized_inputs)
                        if label_columns:
                            codes = _mapped_transform(
                                normalized_inputs, label_columns, label_encodings, batch_size, unseen_value=-1
                            )
                            for i, col in enumerate(label_columns):
                                fe_inputs[col] = codes[:, i].tolist()
                        if ordinal_columns:
                            codes = _mapped_transform(
                                normalized_inputs, ordinal_columns, ordinal_encodings, batch_size,
                                unseen_value=np.nan, normalize_keys=True,
                            )
                            for i, col in enumerate(ordinal_columns):
                                fe_inputs[col] = codes[:, i].tolist()
                    engineered = _replay_feature_engineering(
                        fe_inputs, feature_engineering_steps, batch_size,
                        problems=replay_problems,
                    )
                    column_arrays.update(engineered)
                    failed_outputs = {
                        output
                        for problem in replay_problems
                        for output in problem["outputs"]
                        if output not in engineered
                    }
                    for output in failed_outputs:
                        column_arrays.pop(output, None)
                    for step in feature_engineering_steps:
                        for output in _step_output_columns(step):
                            if output and output not in legacy_order:
                                legacy_order.append(output)

                # The real training-time column order, when available, always
                # wins over the grouped fallback above.
                recorded_model_input_columns = metadata.get("model_input_columns")
                model_input_columns = None
                if recorded_model_input_columns is not None:
                    model_input_columns = _normalize_estimator_feature_names(
                        recorded_model_input_columns,
                        None,
                    )
                    if model_input_columns is None:
                        raise AppException(
                            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                            error_detail=(
                                f"Model '{ml_model.name}' artifact has invalid "
                                "model_input_columns metadata. Retrain and upload "
                                "a complete model artifact."
                            ),
                        )

                artifact_model_order = model_input_columns or legacy_order
                if estimator_feature_names:
                    module_root = type(model).__module__.split(".", 1)[0]
                    if module_root == "catboost" and estimator_feature_names == [
                        str(index) for index in range(len(estimator_feature_names))
                    ]:
                        matrix_column_order = artifact_model_order
                    else:
                        matrix_column_order = _match_registered_feature_names(
                            estimator_feature_names,
                            artifact_model_order,
                            module_root,
                        )
                    if matrix_column_order is None:
                        raise AppException(
                            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
                            error_detail=(
                                f"Model '{ml_model.name}' artifact feature names disagree "
                                "with the names recorded by its fitted estimator. Retrain "
                                "and upload a consistent model artifact."
                            ),
                        )
                    model_feature_names = estimator_feature_names
                else:
                    model_feature_names = artifact_model_order
                    matrix_column_order = artifact_model_order

                missing_columns = [
                    column for column in matrix_column_order if column not in column_arrays
                ]
                # A caller-input problem behind a missing model column is
                # reported as such. Metadata failures keep the generic
                # reconstruction error below, and unused failures are ignored.
                _raise_for_replay_problems(replay_problems, missing_columns)

                if missing_columns:
                    error = ValueError(
                        f"Could not reconstruct column(s) {missing_columns} that the model "
                        "was trained on - the saved model metadata may be incomplete or from "
                        "an incompatible older version."
                    )
                    raise AppException(error_key=ErrorKey.INTERNAL_ERROR, error_detail=str(error))

                input_data = np.column_stack(
                    [column_arrays[column] for column in matrix_column_order]
                )

                # Reapply the scaler fitted at training time (if any) so scaled
                # features match what the model was trained on. No-op for
                # models trained with scalingMethod "none" or legacy models
                # that predate this metadata.
                scaler = metadata.get("scaler")
                scaled_columns = metadata.get("scaled_columns") or []
                if scaler is not None and scaled_columns:
                    scaled_indices = [
                        matrix_column_order.index(c)
                        for c in scaled_columns
                        if c in matrix_column_order
                    ]
                    if scaled_indices:
                        input_data = input_data.astype(float)
                        input_data[:, scaled_indices] = scaler.transform(input_data[:, scaled_indices])

                prediction_input = pd.DataFrame(
                    input_data,
                    columns=model_feature_names,
                )
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

                raw_predictions = model.predict(prediction_input)
                predictions = _prediction_array(raw_predictions)
                if predictions.ndim == 2 and predictions.shape[1] == 1:
                    predictions = predictions[:, 0]

                # Probability outputs are optional and do not determine the predicted class.
                probabilities: Optional[np.ndarray] = None
                if hasattr(model, "predict_proba") and class_labels is not None:
                    try:
                        probabilities = model.predict_proba(prediction_input)
                    except Exception as exc:
                        logger.warning(
                            "Probabilities unavailable for model %s; returning predictions "
                            "without probabilities/confidences: %s: %s",
                            model_id,
                            type(exc).__name__,
                            _summarize_error(exc),
                        )
                        probabilities = None

                # Reconstruct real-unit predictions for a model trained on a
                # ratio target (target / baselineColumn - see TrainModelNode's
                # targetTransform). Without this, predictions come back as the
                # raw ratio (e.g. 0.73) instead of the real-unit value the
                # caller expects (e.g. 54750). No-op for models with no
                # targetTransform or legacy models that predate this metadata.
                if ratio_baseline_values is not None:
                    predictions = _apply_ratio_target_transform(
                        predictions,
                        ratio_baseline_values,
                    )

                # Build response (always batch format)
                # Convert the raw (pre-encoding) input to a column-wise dictionary
                # (columns ordered by feature_names) so the echoed input reflects
                # what the caller actually submitted, not the expanded matrix
                # handed to the model.
                input_data_by_column = _echo_input_columns(
                    normalized_inputs, feature_names, batch_size
                )

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
                    try:
                        probability_outputs, confidences = _build_probability_outputs(
                            probabilities,
                            class_labels,
                            prediction_values,
                        )
                    except (IndexError, TypeError, ValueError) as exc:
                        logger.warning(
                            "Ignoring invalid probability output for model %s: %s",
                            model_id,
                            exc,
                        )
                    else:
                        result["probabilities"] = probability_outputs
                        if confidences is None:
                            logger.warning(
                                "Confidence omitted for model %s because a predicted class "
                                "is not present in the model class list",
                                model_id,
                            )
                        else:
                            result["confidences"] = confidences
                if inference_warnings:
                    result["warnings"] = inference_warnings
                logger.info(
                    "Prediction complete: %d rows for model %s (feature order: %s)",
                    batch_size,
                    model_id,
                    feature_order_source,
                )
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
        # Use the copy in the ML models folder, downloading the uploaded file first when needed
        if await local_model_file(ml_model, ml_service) is not None:
            return

        error_msg = f"PKL file not found for model {ml_model.name}"
        if ml_model.pkl_file:
            error_msg += f" at path: {ml_model.pkl_file}"
        raise AppException(error_key=ErrorKey.FILE_NOT_FOUND, error_detail=error_msg)
