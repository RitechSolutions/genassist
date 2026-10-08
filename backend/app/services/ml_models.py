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
    """Preserve model-owned inference settings while refreshing trained metadata."""
    merged = dict(existing_params) if isinstance(existing_params, dict) else {}
    feature_set = set(feature_names)
    existing_defaults = merged.get(FEATURE_DEFAULTS_PARAM)

    if isinstance(existing_defaults, dict):
        retained_defaults = {
            name: value for name, value in existing_defaults.items() if name in feature_set
        }
        if retained_defaults:
            merged[FEATURE_DEFAULTS_PARAM] = retained_defaults
        else:
            merged.pop(FEATURE_DEFAULTS_PARAM, None)
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

    async def create(self, ml_model: MLModelCreate) -> MLModel:
        """Create a new ML model."""
        validate_model_inference_params(ml_model.features, ml_model.inference_params)

        # Check if a model with the same name already exists
        existing_model = await self.repository.get_by_name(ml_model.name)
        if existing_model:
            raise AppException(
                error_key=ErrorKey.ML_MODEL_NAME_EXISTS
            )

        db_ml_model = await self.repository.create(ml_model)
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

    async def update(self, ml_model_id: UUID, ml_model_update: MLModelUpdate) -> MLModel:
        """Update an existing ML model."""
        update_data = ml_model_update.model_dump(exclude_unset=True)

        if "features" in update_data or "inference_params" in update_data:
            existing_model = await self.repository.get_by_id(ml_model_id)
            feature_names = update_data.get("features", existing_model.features)
            inference_params = update_data.get(
                "inference_params", existing_model.inference_params
            )
            validate_model_inference_params(feature_names, inference_params)

        # If name is being updated, check for uniqueness
        if 'name' in update_data:
            existing_model = await self.repository.get_by_name(update_data['name'])
            if existing_model and existing_model.id != ml_model_id:
                raise AppException(
                    error_key=ErrorKey.ML_MODEL_NAME_EXISTS
                )

        db_ml_model = await self.repository.update(ml_model_id, update_data)
        return db_ml_model

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
