from typing import Any, Dict, List, Optional

import numpy as np

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

SUPPORTED_ARTIFACT_SCHEMA_VERSION = 2
_UNREADABLE_MODEL_ATTRIBUTE = object()


def _read_model_attribute(model: Any, attribute: str) -> Any:
    try:
        return getattr(model, attribute, None)
    except Exception:
        return _UNREADABLE_MODEL_ATTRIBUTE


def _model_feature_count(model: Any) -> Optional[int]:
    count_value = _read_model_attribute(model, "n_features_in_")
    if count_value is None:
        return None
    if (
        count_value is _UNREADABLE_MODEL_ATTRIBUTE
        or isinstance(count_value, (bool, np.bool_))
        or not isinstance(count_value, (int, np.integer))
        or count_value < 1
    ):
        return -1
    return int(count_value)


def _normalize_estimator_feature_names(
    names: Any,
    expected_feature_count: Optional[int],
) -> Optional[List[str]]:
    if isinstance(names, np.ndarray):
        names = names.tolist()
    if not isinstance(names, (list, tuple)):
        return None

    normalized_names = list(names)
    if (
        not normalized_names
        or any(not isinstance(name, str) or not name.strip() for name in normalized_names)
        or len(set(normalized_names)) != len(normalized_names)
        or (expected_feature_count is not None and len(normalized_names) != expected_feature_count)
    ):
        return None
    return normalized_names


def _resolve_estimator_feature_names(
    model: Any,
    module_root: str,
    expected_feature_count: Optional[int],
) -> Optional[List[str]]:
    if module_root == "xgboost" and type(model).__name__ == "Booster":
        return None

    resolved_orders = []
    for attribute, required_module in (
        ("feature_names_in_", None),
        ("feature_names_", "catboost"),
        ("feature_name_", "lightgbm"),
    ):
        if required_module is not None and module_root != required_module:
            continue
        normalized_names = _normalize_estimator_feature_names(
            _read_model_attribute(model, attribute),
            expected_feature_count,
        )
        if normalized_names is not None:
            resolved_orders.append(normalized_names)

    if module_root == "xgboost":
        get_booster = _read_model_attribute(model, "get_booster")
        if not callable(get_booster):
            return None
        try:
            booster = get_booster()
        except Exception:
            return None
        native_names = _normalize_estimator_feature_names(
            _read_model_attribute(booster, "feature_names"),
            expected_feature_count,
        )
        if native_names is None:
            return None
        resolved_orders.append(native_names)

    if resolved_orders and all(names == resolved_orders[0] for names in resolved_orders[1:]):
        return resolved_orders[0]
    return None


def _lightgbm_feature_name(name: str) -> str:
    return "".join("_" if character.isspace() else character for character in name)


def _match_registered_feature_names(
    estimator_names: List[str],
    registered_names: Any,
    module_root: str,
) -> Optional[List[str]]:
    normalized_registered_names = _normalize_estimator_feature_names(
        registered_names,
        len(estimator_names),
    )
    if normalized_registered_names is None:
        return None

    if set(normalized_registered_names) == set(estimator_names):
        return list(estimator_names)

    if module_root != "lightgbm":
        return None

    registered_by_estimator_name = {_lightgbm_feature_name(name): name for name in normalized_registered_names}
    if set(registered_by_estimator_name) != set(estimator_names):
        return None
    return [registered_by_estimator_name[name] for name in estimator_names]


def _resolve_artifact_metadata(
    model_response: Dict[str, Any],
    error_key: ErrorKey = ErrorKey.ML_INFERENCE_INPUT_INVALID,
) -> Dict[str, Any]:
    metadata = model_response.get("metadata")
    if not isinstance(metadata, dict):
        return {}

    schema_version = metadata.get("metadata_schema_version")
    if schema_version is None:
        if not metadata:
            return {}
        raise AppException(
            error_key=error_key,
            error_detail=(
                "This model artifact has metadata but does not declare a metadata schema version, "
                "so it cannot be read safely. Retrain the model with the current version of GenAssist."
            ),
        )
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version < 1:
        raise AppException(
            error_key=error_key,
            error_detail=(
                "This model artifact declares an invalid metadata schema version. "
                "Retrain the model with the current version of GenAssist."
            ),
        )
    if schema_version > SUPPORTED_ARTIFACT_SCHEMA_VERSION:
        raise AppException(
            error_key=error_key,
            error_detail=(
                f"This model uses artifact schema v{schema_version}, but this server supports "
                f"up to v{SUPPORTED_ARTIFACT_SCHEMA_VERSION}. Upgrade the server or retrain the model."
            ),
        )
    return metadata
