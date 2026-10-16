import asyncio
import logging
import os
import stat
import tempfile
from dataclasses import dataclass
from typing import Any, Optional, Sequence
from uuid import UUID

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.ml_model_feature_contract import (
    _match_registered_feature_names,
    _model_feature_count,
    _normalize_estimator_feature_names,
    _resolve_artifact_metadata,
    _resolve_estimator_feature_names,
)
from app.services.ml_model_manager import (
    _MODEL_LOAD_EXECUTOR,
    MLModelManager,
    _load_pickle_sync,
)

logger = logging.getLogger(__name__)

# Same limit the upload endpoint enforces for .pkl files.
MAX_ARTIFACT_BYTES = 500 * 1024 * 1024
# Download + read must finish within the frontend's 120s request timeout.
ARTIFACT_DOWNLOAD_TIMEOUT_SECONDS = 45.0
ARTIFACT_READ_TIMEOUT_SECONDS = 60.0
# Keep error details under the API's 450-character detail limit.
_MAX_DETAIL_LENGTH = 440
_MAX_NAMES_IN_ERROR = 3
_MAX_NAME_LENGTH = 40
# One message for every read failure: pkl_file is caller-supplied, so distinct
# messages (missing, not a file, too large, parse error) would let a caller
# probe the server filesystem. The reason is logged instead.
_UNREADABLE_DETAIL = (
    "The model file could not be read or validated. Upload a supported .pkl file "
    "(500MB max) and try again."
)


@dataclass(frozen=True)
class ModelArtifactContract:
    """What a model artifact declares about its inputs and target.

    ``target_variable`` is None for raw models, which do not record a target.
    ``feature_order_source`` distinguishes caller-facing artifact metadata
    from names recorded directly by a fitted estimator.
    """

    features: Optional[tuple[str, ...]]
    target_variable: Optional[str]
    feature_count: int
    module_root: str = ""
    feature_order_source: str = "artifact_metadata"


def _artifact_error(detail: str) -> AppException:
    if len(detail) > _MAX_DETAIL_LENGTH:
        detail = detail[: _MAX_DETAIL_LENGTH - 1] + "…"
    return AppException(error_key=ErrorKey.ML_MODEL_ARTIFACT_INVALID, error_detail=detail)


def _unreadable(reason: str) -> AppException:
    logger.warning("Model artifact rejected during registration: %s", reason)
    return _artifact_error(_UNREADABLE_DETAIL)


def _unavailable(reason: str) -> AppException:
    # Storage, database or capacity problems are retryable server errors, not bad input.
    logger.error("Model artifact could not be checked during registration: %s", reason)
    return AppException(error_key=ErrorKey.INTERNAL_ERROR, status_code=503)


def _extract_metadata_contract(metadata: Any) -> ModelArtifactContract:
    if not isinstance(metadata, dict) or "feature_columns" not in metadata:
        raise _artifact_error(
            "The model file does not contain feature metadata. "
            "Retrain or export the model with the current GenAssist training pipeline."
        )

    feature_columns = _normalize_estimator_feature_names(
        metadata["feature_columns"],
        None,
    )
    if feature_columns is None:
        raise _artifact_error(
            "The model file has invalid feature_columns metadata. "
            "It must be a non-empty ordered list of unique feature names."
        )

    target_column = metadata.get("target_column")
    if target_column is not None and (not isinstance(target_column, str) or not target_column.strip()):
        raise _artifact_error(
            "The model file has invalid target_column metadata. It must name the model's prediction target."
        )

    return ModelArtifactContract(
        features=tuple(feature_columns),
        target_variable=target_column,
        feature_count=len(feature_columns),
    )


def _extract_raw_model_contract(model: Any) -> ModelArtifactContract:
    module_root = type(model).__module__.split(".", 1)[0]
    feature_count = _model_feature_count(model)
    recorded_names = _resolve_estimator_feature_names(
        model,
        module_root,
        feature_count,
    )
    if recorded_names is not None:
        return ModelArtifactContract(
            features=tuple(recorded_names),
            target_variable=None,
            feature_count=len(recorded_names),
            module_root=module_root,
            feature_order_source="estimator",
        )

    raise _artifact_error(
        "The model file does not record a safe, unambiguous feature-name order, so inference "
        "cannot use it. Fit the model on a DataFrame with named columns, or retrain it with "
        "the GenAssist training pipeline."
    )


def extract_model_artifact_contract(artifact: Any) -> ModelArtifactContract:
    """Read the same feature contract that inference will enforce."""
    normalized = MLModelManager._normalize_loaded_model(artifact)
    metadata = _resolve_artifact_metadata(
        normalized,
        error_key=ErrorKey.ML_MODEL_ARTIFACT_INVALID,
    )
    if metadata:
        return _extract_metadata_contract(metadata)
    return _extract_raw_model_contract(normalized["model"])


def _read_artifact_sync(pkl_file: str) -> Any:
    from app.core.utils.model_validator import validate_pickle_file_safe

    try:
        file_stat = os.stat(pkl_file)
    except OSError as exc:
        raise _unreadable(f"stat failed ({type(exc).__name__})") from exc
    if not stat.S_ISREG(file_stat.st_mode):
        raise _unreadable("not a regular file")
    if file_stat.st_size > MAX_ARTIFACT_BYTES:
        raise _unreadable(f"{file_stat.st_size} bytes exceeds the limit")

    is_valid, error = validate_pickle_file_safe(pkl_file)
    if not is_valid:
        raise _unreadable(f"safety check failed: {error}")

    try:
        return _load_pickle_sync(pkl_file)
    except Exception as exc:
        raise _unreadable(f"load failed ({type(exc).__name__})") from exc


async def _read_artifact(pkl_file: str) -> Any:
    # On the model-loader pool, not the event loop or the shared default
    # executor, and outside the model manager cache.
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_MODEL_LOAD_EXECUTOR, _read_artifact_sync, pkl_file),
            timeout=ARTIFACT_READ_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise _unavailable(f"read timed out after {ARTIFACT_READ_TIMEOUT_SECONDS}s") from exc


def _file_manager() -> Any:
    from app.dependencies.injector import injector
    from app.services.file_manager import FileManagerService

    return injector.get(FileManagerService)


async def _download_artifact(pkl_file_id: str, destination_path: str) -> None:
    try:
        file_uuid = UUID(str(pkl_file_id))
    except ValueError as exc:
        raise _unreadable("pkl_file_id is not a UUID") from exc

    file_manager = _file_manager()
    try:
        file = await file_manager.get_file_by_id(file_uuid)
    except AppException as exc:
        if exc.error_key is ErrorKey.DATASOURCE_NOT_FOUND:
            raise _unreadable("file record not found") from exc
        raise _unavailable(f"file record lookup failed ({exc.error_key})") from exc
    except Exception as exc:
        raise _unavailable(f"file record lookup failed ({type(exc).__name__})") from exc
    if not file:
        raise _unreadable("file record not found")
    # Check the recorded size before pulling the bytes from storage.
    if file.size is not None and file.size > MAX_ARTIFACT_BYTES:
        raise _unreadable(f"{file.size} bytes exceeds the limit")
    try:
        await asyncio.wait_for(
            file_manager.download_file_to_path(file.id, destination_path),
            timeout=ARTIFACT_DOWNLOAD_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise _unavailable(f"download timed out after {ARTIFACT_DOWNLOAD_TIMEOUT_SECONDS}s") from exc
    except Exception as exc:
        raise _unavailable(f"download failed ({type(exc).__name__})") from exc


async def load_model_artifact_contract(
    pkl_file: Optional[str],
    pkl_file_id: Optional[str],
) -> Optional[ModelArtifactContract]:
    """Read the contract of the artifact a registry entry points to, if any."""
    if pkl_file and os.path.exists(pkl_file):
        return extract_model_artifact_contract(await _read_artifact(pkl_file))

    if pkl_file_id:
        with tempfile.TemporaryDirectory(prefix="ml-model-contract-") as temporary_directory:
            temporary_path = os.path.join(temporary_directory, "model.pkl")
            await _download_artifact(pkl_file_id, temporary_path)
            return extract_model_artifact_contract(await _read_artifact(temporary_path))

    if pkl_file:
        raise _unreadable("local pkl_file missing and no pkl_file_id")
    return None


def _short(name: str) -> str:
    # Truncate after repr(): escaping can make a name several times longer.
    shown = repr(name)
    return shown if len(shown) <= _MAX_NAME_LENGTH else shown[: _MAX_NAME_LENGTH - 1] + "…"


def _name_list(names: Sequence[str]) -> str:
    shown = ", ".join(_short(name) for name in names[:_MAX_NAMES_IN_ERROR])
    hidden = len(names) - _MAX_NAMES_IN_ERROR
    return f"{shown} (+{hidden} more)" if hidden > 0 else shown


def validate_registry_contract(
    contract: ModelArtifactContract,
    feature_names: Optional[Sequence[str]],
    target_variable: Optional[str],
) -> None:
    """Require registry fields to name the same inputs accepted by inference."""
    registered = list(feature_names or [])
    problems = []

    if contract.target_variable is not None and target_variable != contract.target_variable:
        problems.append(
            f"Target must be {_short(contract.target_variable)}, not {_short(target_variable or '')}."
        )

    duplicates = sorted({name for name in registered if registered.count(name) > 1})
    if duplicates:
        problems.append(f"Duplicate features: {_name_list(duplicates)}.")

    expected = list(contract.features or [])
    if expected:
        if contract.feature_order_source == "estimator":
            names_match = (
                _match_registered_feature_names(
                    expected,
                    registered,
                    contract.module_root,
                )
                is not None
            )
        else:
            normalized_registered = _normalize_estimator_feature_names(
                registered,
                len(expected),
            )
            names_match = normalized_registered is not None and set(normalized_registered) == set(expected)

        if names_match:
            missing = []
            extra = []
        else:
            missing = [name for name in expected if name not in registered]
            extra = [name for name in registered if name not in expected]
        if missing:
            problems.append(f"Missing features: {_name_list(missing)}.")
        if extra:
            problems.append(f"Features not in the model: {_name_list(extra)}.")
        if not names_match and not missing and not extra:
            problems.append("Registered feature names are invalid or ambiguous.")
    else:
        problems.append("The model does not record a safe feature-name order and cannot be registered for inference.")

    if problems:
        raise _artifact_error("Registry fields do not match the model file. " + " ".join(problems))


async def validate_model_artifact_registration(
    pkl_file: Optional[str],
    pkl_file_id: Optional[str],
    feature_names: Optional[Sequence[str]],
    target_variable: Optional[str],
    artifact_contract: Optional[ModelArtifactContract] = None,
) -> None:
    """Validate registry fields against the attached artifact.

    Pass ``artifact_contract`` when the caller already knows what the artifact
    declares (e.g. the Train Model node that just wrote it) to skip reading it.
    """
    contract = artifact_contract or await load_model_artifact_contract(pkl_file, pkl_file_id)
    if contract is not None:
        validate_registry_contract(contract, feature_names, target_variable)
