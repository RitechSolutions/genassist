import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services.ml_model_manager import download_pkl_file, get_ml_model_manager

logger = logging.getLogger(__name__)

SUPPORTED_ARTIFACT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ModelArtifactContract:
    features: tuple[str, ...]
    target_variable: str


def _contract_error(detail: str) -> AppException:
    return AppException(
        error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
        error_detail=detail,
    )


def extract_model_artifact_contract(artifact: Any) -> ModelArtifactContract:
    """Extract the self-described feature contract from a loaded model artifact."""
    if not isinstance(artifact, dict):
        raise _contract_error(
            "The uploaded model artifact does not contain self-described metadata. "
            "Upload an artifact produced by the current GenAssist training pipeline."
        )

    metadata = artifact.get("metadata")
    if not isinstance(metadata, dict) or not metadata:
        raise _contract_error(
            "The uploaded model artifact does not contain self-described feature metadata. "
            "Retrain or export the model with the current GenAssist training pipeline."
        )

    schema_version = metadata.get("metadata_schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version < 1
    ):
        raise _contract_error(
            "The uploaded model artifact has an invalid metadata schema version. "
            "Retrain or export the model with the current GenAssist training pipeline."
        )
    if schema_version > SUPPORTED_ARTIFACT_SCHEMA_VERSION:
        raise _contract_error(
            f"The uploaded model artifact uses metadata schema v{schema_version}, but this server "
            f"supports up to v{SUPPORTED_ARTIFACT_SCHEMA_VERSION}. Upgrade the server or retrain the model."
        )

    feature_columns = metadata.get("feature_columns")
    if (
        not isinstance(feature_columns, list)
        or not feature_columns
        or any(
            not isinstance(name, str) or not name.strip() for name in feature_columns
        )
        or len(set(feature_columns)) != len(feature_columns)
    ):
        raise _contract_error(
            "The uploaded model artifact has invalid feature_columns metadata. "
            "It must be a non-empty ordered list of unique feature names."
        )

    target_column = metadata.get("target_column")
    if not isinstance(target_column, str) or not target_column.strip():
        raise _contract_error(
            "The uploaded model artifact has invalid target_column metadata. "
            "It must identify the model's prediction target."
        )

    return ModelArtifactContract(
        features=tuple(feature_columns),
        target_variable=target_column,
    )


async def load_model_artifact_contract(
    pkl_file: Optional[str],
    pkl_file_id: Optional[str],
) -> Optional[ModelArtifactContract]:
    """Safely load an artifact and return its declared registry contract."""
    if not pkl_file and not pkl_file_id:
        return None

    manager = get_ml_model_manager()
    try:
        if pkl_file:
            artifact = await manager.load_artifact(pkl_file)
        else:
            with tempfile.TemporaryDirectory(
                prefix="ml-model-contract-"
            ) as temporary_directory:
                temporary_path = await download_pkl_file(
                    pkl_file_id,
                    os.path.join(temporary_directory, "model.pkl"),
                )
                artifact = await manager.load_artifact(temporary_path)
    except Exception as exc:
        logger.warning(
            "Unable to inspect uploaded model artifact: %s", type(exc).__name__
        )
        raise _contract_error(
            "The uploaded model artifact could not be safely read. "
            "Upload a supported model artifact and verify its dependencies are installed."
        ) from exc

    return extract_model_artifact_contract(artifact)


def validate_registry_contract(
    contract: ModelArtifactContract,
    feature_names: Optional[Sequence[str]],
    target_variable: Optional[str],
) -> None:
    """Require registry fields to exactly match the artifact contract."""
    registered_features = list(feature_names or [])
    artifact_features = list(contract.features)
    mismatches = []

    if registered_features != artifact_features:
        mismatches.append(
            "Features must match exactly, including order. "
            f"Artifact features: {artifact_features}. Registered features: {registered_features}."
        )
    if target_variable != contract.target_variable:
        mismatches.append(
            f"Artifact target: {contract.target_variable!r}. Registered target: {target_variable!r}."
        )

    if mismatches:
        raise _contract_error(
            "Model registry fields do not match the uploaded model artifact. "
            + " ".join(mismatches)
        )


async def validate_model_artifact_registration(
    pkl_file: Optional[str],
    pkl_file_id: Optional[str],
    feature_names: Optional[Sequence[str]],
    target_variable: Optional[str],
) -> None:
    """Validate registry fields when an artifact is attached."""
    contract = await load_model_artifact_contract(pkl_file, pkl_file_id)
    if contract is not None:
        validate_registry_contract(contract, feature_names, target_variable)
