import logging
import os
from typing import Any, Optional, Sequence
from uuid import UUID

import numpy as np
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.file import FileModel
from app.db.models.ml_model import MLModel
from app.repositories.ml_models import MLModelsRepository
from app.schemas.ml_model import FEATURE_DEFAULTS_PARAM, MLModelCreate, MLModelUpdate
from app.services.ml_model_artifacts import (
    ModelArtifactContract,
    validate_model_artifact_registration,
)

logger = logging.getLogger(__name__)

_RATIO_BASELINE_PARAM = "ratioBaselineColumn"
STALE_CATEGORICAL_DEFAULT_WARNING_PREFIX = (
    "Feature default(s) no longer match categories fitted by this run"
)


def _category_key(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return ("bool", value)
    return value


def stale_categorical_defaults(inference_params, categorical_contracts) -> list[str]:
    if not isinstance(inference_params, dict) or not isinstance(categorical_contracts, dict):
        return []
    defaults = inference_params.get(FEATURE_DEFAULTS_PARAM)
    if not isinstance(defaults, dict):
        return []

    stale_defaults = []
    for name, default in defaults.items():
        contract = categorical_contracts.get(name)
        if not isinstance(contract, dict) or not isinstance(contract.get("values"), list):
            continue
        values = contract["values"]
        if contract.get("normalize_keys"):
            from app.modules.workflow.engine.nodes.ml.ml_utils import ordinal_key

            matches = ordinal_key(default) in {ordinal_key(value) for value in values}
        else:
            matches = _category_key(default) in {
                _category_key(value) for value in values
            }
        if not matches:
            stale_defaults.append(name)
    return sorted(stale_defaults)


def merge_model_inference_params(
    existing_params: Any,
    feature_names: Sequence[str],
    ratio_baseline_column: Optional[str],
) -> Optional[dict]:
    """Preserve explicit per-model settings that remain valid for the feature set."""
    merged = dict(existing_params) if isinstance(existing_params, dict) else {}
    feature_set = set(feature_names)
    existing_defaults = merged.get(FEATURE_DEFAULTS_PARAM)

    retained_defaults = {}
    if isinstance(existing_defaults, dict):
        retained_defaults = {
            name: value
            for name, value in existing_defaults.items()
            if name in feature_set
        }

    if retained_defaults:
        merged[FEATURE_DEFAULTS_PARAM] = retained_defaults
    else:
        merged.pop(FEATURE_DEFAULTS_PARAM, None)

    if ratio_baseline_column:
        merged[_RATIO_BASELINE_PARAM] = ratio_baseline_column
    else:
        merged.pop(_RATIO_BASELINE_PARAM, None)

    return merged or None


def validate_model_inference_params(
    feature_names: Optional[Sequence[str]],
    inference_params: Any,
) -> None:
    if not isinstance(inference_params, dict):
        return

    feature_defaults = inference_params.get(FEATURE_DEFAULTS_PARAM)
    if not isinstance(feature_defaults, dict):
        return

    feature_set = set(feature_names or [])
    unknown_defaults = sorted(name for name in feature_defaults if name not in feature_set)
    if unknown_defaults:
        raise AppException(
            error_key=ErrorKey.ML_INFERENCE_INPUT_INVALID,
            error_detail=(
                "Feature defaults reference unknown model feature(s): "
                f"{', '.join(unknown_defaults)}."
            ),
        )


@inject
class MLModelsService:
    """Service for ML models business logic."""

    def __init__(self, repository: MLModelsRepository):
        self.repository = repository

    async def create(
        self,
        ml_model: MLModelCreate,
        artifact_contract: Optional[ModelArtifactContract] = None,
    ) -> MLModel:
        """Create a new ML model."""
        validate_model_inference_params(ml_model.features, ml_model.inference_params)

        # Check if a model with the same name already exists
        existing_model = await self.repository.get_by_name(ml_model.name)
        if existing_model:
            raise AppException(
                error_key=ErrorKey.ML_MODEL_NAME_EXISTS
            )

        # With an uploaded file, validate that file: a caller-supplied pkl_file
        # path must not decide what is read (see _artifact_source).
        await validate_model_artifact_registration(
            None if ml_model.pkl_file_id else ml_model.pkl_file,
            ml_model.pkl_file_id,
            ml_model.features,
            ml_model.target_variable,
            artifact_contract=artifact_contract,
        )

        model_to_create = ml_model.model_copy(update={"pkl_file": None}) if ml_model.pkl_file_id else ml_model
        db_ml_model = await self.repository.create(model_to_create)
        return db_ml_model

    async def get_by_id(self, ml_model_id: UUID) -> MLModel:
        """Get ML model by ID."""
        db_ml_model = await self.repository.get_by_id(ml_model_id)
        return db_ml_model

    async def get_by_name(self, name: str) -> Optional[MLModel]:
        """Get ML model by name, or None if no such model exists."""
        return await self.repository.get_by_name(name)

    async def get_all(self):
        """Get all ML models."""
        db_ml_models = await self.repository.get_all()
        return db_ml_models

    async def update(
        self,
        ml_model_id: UUID,
        ml_model_update: MLModelUpdate,
        artifact_contract: Optional[ModelArtifactContract] = None,
    ) -> MLModel:
        """Update an existing ML model."""
        update_data = ml_model_update.model_dump(exclude_unset=True)
        if update_data.get("pkl_file_id") is not None:
            update_data["pkl_file_id"] = str(update_data["pkl_file_id"])

        # Cheap checks first: validating the artifact may download and read it.
        if 'name' in update_data:
            same_name = await self.repository.get_by_name(update_data['name'])
            if same_name and same_name.id != ml_model_id:
                raise AppException(
                    error_key=ErrorKey.ML_MODEL_NAME_EXISTS
                )

        contract_fields = {"features", "target_variable", "pkl_file", "pkl_file_id"}
        if not (contract_fields.intersection(update_data) or "inference_params" in update_data):
            return await self.repository.update(ml_model_id, update_data)

        existing_model = await self.repository.get_by_id(ml_model_id)

        if "features" in update_data or "inference_params" in update_data:
            feature_names = update_data.get("features", existing_model.features)
            inference_params = update_data.get(
                "inference_params", existing_model.inference_params
            )
            validate_model_inference_params(feature_names, inference_params)

        existing_file_id = (
            str(existing_model.pkl_file_id) if existing_model.pkl_file_id is not None else None
        )
        file_id = update_data.get("pkl_file_id", existing_file_id)
        file_id_changed = "pkl_file_id" in update_data and file_id != existing_file_id
        if file_id_changed and file_id:
            # A caller-supplied path must never override the uploaded file that
            # was validated and will be downloaded for inference.
            update_data["pkl_file"] = None
        elif file_id and not file_id_changed:
            # pkl_file is only a local copy of the uploaded file, which inference
            # records itself. A stale value from the edit form must neither count
            # as a change nor overwrite the recorded copy.
            update_data.pop("pkl_file", None)
        elif file_id_changed and "pkl_file" not in update_data:
            # Any local copy belongs to the previous file.
            update_data["pkl_file"] = None

        contract_changed = (
            file_id_changed
            or any(
                field in update_data and update_data[field] != getattr(existing_model, field)
                for field in ("features", "target_variable")
            )
            or (not file_id and update_data.get("pkl_file", existing_model.pkl_file) != existing_model.pkl_file)
        )
        if contract_changed:
            await validate_model_artifact_registration(
                *self._artifact_source(existing_model, update_data, file_id, file_id_changed),
                update_data.get("features", existing_model.features),
                update_data.get("target_variable", existing_model.target_variable),
                artifact_contract=artifact_contract,
            )

        db_ml_model = await self.repository.update(ml_model_id, update_data)
        return db_ml_model

    @staticmethod
    def _artifact_source(
        existing_model: MLModel, update_data: dict, file_id: Optional[str], file_id_changed: bool
    ) -> tuple[Optional[str], Optional[str]]:
        """Pick the (pkl_file, pkl_file_id) to validate.

        With an uploaded file, only the server-recorded local copy of that same
        file may be read; a caller-supplied path never decides what is read, so
        it cannot be used to probe the filesystem.
        """
        if file_id:
            local_copy = None if file_id_changed else existing_model.pkl_file
            return local_copy, file_id
        return update_data.get("pkl_file", existing_model.pkl_file), None

    async def record_local_pkl_file(self, ml_model_id: UUID, pkl_file: str) -> MLModel:
        """Record where a downloaded copy of the model's own pkl_file_id is stored.

        The artifact itself is unchanged, so the registry contract is not re-validated.
        """
        return await self.repository.update(ml_model_id, {"pkl_file": pkl_file})

    async def delete(self, ml_model_id: UUID):
        """Delete an ML model and its associated .pkl file if it exists."""
        # Get the model first to access the pkl_file path
        ml_model = await self.repository.get_by_id(ml_model_id)

        # If there's a pkl_file, attempt to delete it
        if ml_model.pkl_file and os.path.exists(ml_model.pkl_file):
            try:
                os.remove(ml_model.pkl_file)
                logger.info(f"Deleted pkl file: {ml_model.pkl_file}")
            except OSError as e:
                logger.error(f"Error deleting pkl file {ml_model.pkl_file}: {str(e)}")
                # Continue with soft delete even if file deletion fails

        # if there's a pkl_file_id, delete the file from the file manager service
        if ml_model.pkl_file_id:
            from app.dependencies.injector import injector
            from app.services.file_manager import FileManagerService
            file_manager_service = injector.get(FileManagerService)
            try:
                await file_manager_service.delete_file(ml_model.pkl_file_id)
                logger.info(f"Deleted pkl file: {ml_model.pkl_file_id}")
            except Exception as e:
                logger.error(f"Error deleting pkl file {ml_model.pkl_file_id}: {str(e)}")
                # Continue with soft delete even if file deletion fails

        # Soft delete the model
        await self.repository.delete(ml_model_id)

    async def validate_pkl_file(self, pkl_file_path: str, file: Optional[FileModel] = None) -> dict:
        """Validate the PKL file for an ML model."""
        from app.core.utils.model_validator import get_model_info

        # case when file is provided

        model_info  = get_model_info(pkl_file_path)
        if not model_info["is_valid"]:
            raise AppException(
                error_key=ErrorKey.ML_MODEL_NOT_FOUND
            )

        return model_info
