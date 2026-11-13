import logging
import math
import numbers
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence
from uuid import UUID

import numpy as np
from injector import inject

from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.storage_path import path_relative_to_tenant_root
from app.core.utils.training_upload import is_stored_training_upload
from app.db.models.file import FileModel
from app.db.models.ml_model import MLModel
from app.repositories.ml_models import MLModelsRepository
from app.schemas.ml_model import FEATURE_DEFAULTS_PARAM, MLModelCreate, MLModelUpdate, is_in_ml_models_dir
from app.services.ml_model_artifacts import (
    ModelArtifactContract,
    RegistryContractCheck,
    validate_model_artifact_registration,
)
from app.services.ml_model_manager import ML_MODELS_UPLOAD_DIR, is_outdated_download

logger = logging.getLogger(__name__)

# Uploads from POST /ml-models/upload are stored under this File Manager folder.
ML_MODEL_UPLOAD_FOLDER = "ml_models"
# A rejected save is cleaned up right away; older uploads are never discarded this way.
UNUSED_UPLOAD_MAX_AGE = timedelta(hours=1)


# Train Data Source uploads (POST /file-manager/upload and its upload sessions) go here.
TRAINING_UPLOAD_FOLDER = "uploads"
# The Train Data Source dialog can stay open a long while between picking a file and
# closing it, so its unused uploads may be discarded for longer than a rejected .pkl.
UNUSED_TRAINING_UPLOAD_MAX_AGE = timedelta(hours=24)


def _upload_folder_path(file: FileModel) -> str:
    """File path without the S3 tenant root, so 'tenants/<slug>/ml_models/x.pkl' reads as 'ml_models/x.pkl'."""
    if file.storage_provider == "s3":
        return path_relative_to_tenant_root(file.path)
    return str(file.path or "")


def _is_own_recent_upload(file: FileModel, file_manager: Any, folder: str, max_age: timedelta) -> bool:
    """True for a file the caller uploaded into `folder` within `max_age`, on the current storage."""
    created_at = file.created_at
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    # Delete only through the storage the file was saved to: if File Manager Settings
    # changed since the upload, the delete would miss the file but still drop its record.
    provider = getattr(file_manager, "storage_provider", None)
    same_storage = (
        provider is not None
        and getattr(provider, "name", None) == file.storage_provider
        and str(provider.get_base_path()) == str(file.storage_path)
    )
    return (
        same_storage
        and _upload_folder_path(file).startswith(f"{folder}/")
        and file.created_by is not None
        and file.created_by == get_current_user_id()
        and created_at is not None
        and datetime.now(timezone.utc) - created_at <= max_age
    )

_RATIO_BASELINE_PARAM = "ratioBaselineColumn"
STALE_CATEGORICAL_DEFAULT_WARNING_PREFIX = (
    "Feature default(s) no longer match categories fitted by this run"
)

# Same labels the UI shows (frontend/src/constants/mlModelTypes.ts).
MODEL_TYPE_LABELS = {
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
    "random_forest": "Random Forest",
    "extra_trees": "Extra Trees",
    "gradient_boosting": "Gradient Boosting",
    "decision_tree": "Decision Tree",
    "linear_regression": "Linear Regression",
    "ridge_regression": "Ridge Regression",
    "lasso_regression": "Lasso Regression",
    "elastic_net": "Elastic Net",
    "logistic_regression": "Logistic Regression",
    "svm": "Support Vector Machine",
    "knn": "K-Nearest Neighbors",
    "neural_network": "Neural Network",
}


def _model_type_value(model_type: Any) -> str:
    return str(getattr(model_type, "value", model_type) or "").lower()


def model_type_mismatch_message(
    model_name: Optional[str], registered_type: Any, trained_type: Any
) -> Optional[str]:
    """Explain why a model of one type can't take a file trained as another.

    A model's type is chosen when it is registered; a training run must not
    change it, so a run whose Train Model node trains a different type is
    refused. Returns None when the types match (or the model has none yet).
    """
    registered = _model_type_value(registered_type)
    trained = _model_type_value(trained_type)
    if not registered or not trained or registered == trained:
        return None
    registered_label = MODEL_TYPE_LABELS.get(registered, registered)
    trained_label = MODEL_TYPE_LABELS.get(trained, trained)
    return (
        f"Model '{model_name}' is registered as {registered_label}, but the Train Model "
        f"node is set to {trained_label}. The model was not changed. Set the Train Model "
        f"node's Model Type to {registered_label}, or register a new {trained_label} model."
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


def normalize_training_metrics(metrics: Optional[dict]) -> Optional[dict]:
    """Keep only finite numeric metric values (numpy scalars included).

    ``None`` stays ``None``; anything else that is not a dict becomes ``{}``.
    """
    if metrics is None:
        return None
    if not isinstance(metrics, dict):
        return {}
    clean = {}
    for key, value in metrics.items():
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            continue
        value = float(value)
        if math.isfinite(value):
            clean[str(key)] = value
    return clean


def _collect_notices(notices: Optional[list[str]], check: Optional[RegistryContractCheck]) -> None:
    if notices is not None and check is not None:
        notices.extend(check.notices)


@inject
class MLModelsService:
    """Service for ML models business logic."""

    def __init__(self, repository: MLModelsRepository):
        self.repository = repository

    async def create(
        self,
        ml_model: MLModelCreate,
        artifact_contract: Optional[ModelArtifactContract] = None,
        training_metrics: Optional[dict] = None,
        notices: Optional[list[str]] = None,
    ) -> MLModel:
        """Create a new ML model.

        ``training_metrics`` is for server-side callers (Train Model registration);
        the client schemas do not carry it. Pass a list as ``notices`` to receive
        what the model-file check changed or could not check (not stored).
        """
        validate_model_inference_params(ml_model.features, ml_model.inference_params)

        # Check if a model with the same name already exists
        existing_model = await self.repository.get_by_name(ml_model.name)
        if existing_model:
            raise AppException(
                error_key=ErrorKey.ML_MODEL_NAME_EXISTS
            )

        # With an uploaded file, validate that file: a caller-supplied pkl_file
        # path must not decide what is read (see _artifact_source).
        check = await validate_model_artifact_registration(
            None if ml_model.pkl_file_id else ml_model.pkl_file,
            ml_model.pkl_file_id,
            ml_model.features,
            ml_model.target_variable,
            artifact_contract=artifact_contract,
        )

        changes = {"pkl_file": None} if ml_model.pkl_file_id else {}
        if check is not None:
            changes["features"] = list(check.features)
        model_to_create = ml_model.model_copy(update=changes) if changes else ml_model
        db_ml_model = await self.repository.create(
            model_to_create, training_metrics=normalize_training_metrics(training_metrics)
        )
        _collect_notices(notices, check)
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
        training_metrics: Optional[dict] = None,
        notices: Optional[list[str]] = None,
    ) -> MLModel:
        """Update an existing ML model.

        ``notices``: as in ``create``.

        ``training_metrics`` is for server-side callers (Train Model registration and
        promotion): a dict replaces the stored metrics. ``None`` keeps them, unless
        the model file changes, which leaves the model with empty metrics.
        """
        update_data = ml_model_update.model_dump(exclude_unset=True)
        if training_metrics is not None:
            update_data["training_metrics"] = normalize_training_metrics(training_metrics)
        if update_data.get("pkl_file_id") is not None:
            update_data["pkl_file_id"] = str(update_data["pkl_file_id"])

        # Cheap checks first: validating the artifact may download and read it.
        if 'name' in update_data:
            same_name = await self.repository.get_by_name(update_data['name'])
            if same_name and same_name.id != ml_model_id:
                raise AppException(
                    error_key=ErrorKey.ML_MODEL_NAME_EXISTS
                )

        # A new pkl_file must be inside the ML models folder. An unchanged one is let through,
        # since the edit form sends back paths stored before this check existed.
        new_pkl_file = update_data.get('pkl_file')
        if new_pkl_file and not is_in_ml_models_dir(new_pkl_file):
            existing_model = await self.repository.get_by_id(ml_model_id)
            if new_pkl_file != existing_model.pkl_file:
                raise AppException(
                    error_key=ErrorKey.INVALID_FILE_PATH
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
        file_changed = file_id_changed or (
            not file_id
            and update_data.get("pkl_file", existing_model.pkl_file) != existing_model.pkl_file
        )
        if file_changed and "training_metrics" not in update_data:
            # The stored metrics belong to the previous file.
            update_data["training_metrics"] = {}
        check = None
        if contract_changed:
            check = await validate_model_artifact_registration(
                *self._artifact_source(existing_model, update_data, file_id, file_id_changed),
                update_data.get("features", existing_model.features),
                update_data.get("target_variable", existing_model.target_variable),
                artifact_contract=artifact_contract,
            )
            if check is not None:
                update_data["features"] = list(check.features)

        db_ml_model = await self.repository.update(ml_model_id, update_data)
        _collect_notices(notices, check)
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
            # A copy of an earlier upload is not the file inference will use.
            local_copy = existing_model.pkl_file
            if file_id_changed or (
                local_copy and is_outdated_download(existing_model.id, file_id, local_copy)
            ):
                local_copy = None
            return local_copy, file_id
        return update_data.get("pkl_file", existing_model.pkl_file), None

    async def discard_unused_upload(self, file_id: UUID, file_manager: Any) -> None:
        """Delete a .pkl upload whose model was never saved (a rejected Create or Update).

        The form uploads the file before it saves the model, so a rejected save would
        otherwise leave the file in File Manager. Only a recent ML model upload made by
        the caller and used by no model is deleted; anything else answers "not found",
        so the endpoint can't be used to remove or probe other files.
        """
        not_found = AppException(error_key=ErrorKey.FILE_NOT_FOUND, status_code=404)
        try:
            file = await file_manager.get_file_by_id(file_id)
        except AppException:
            raise not_found from None
        # The upload route hands the client these on-disk paths, and a model may point
        # at them through pkl_file alone, so they count as references too.
        copy_path = os.path.join(ML_MODELS_UPLOAD_DIR, f"{file.id}.pkl")
        upload_paths = {copy_path}
        if file.storage_provider == "local" and file.storage_path and file.path:
            upload_paths.add(f"{file.storage_path}/{file.path}")
        upload_paths |= {os.path.normpath(p) for p in upload_paths}
        discardable = (
            _is_own_recent_upload(file, file_manager, ML_MODEL_UPLOAD_FOLDER, UNUSED_UPLOAD_MAX_AGE)
            and (file.file_extension or "").lower() == "pkl"
            and not await self.repository.is_file_referenced(file.id, sorted(upload_paths))
        )
        if not discardable:
            raise not_found

        await file_manager.delete_file(file.id)
        # The upload route also copies the file into the ML models folder when File
        # Manager stores it elsewhere; remove that copy too.
        if os.path.isfile(copy_path):
            try:
                os.remove(copy_path)
            except OSError as exc:
                logger.warning("Could not remove the model file copy %s: %s", copy_path, type(exc).__name__)

    async def discard_unused_training_upload(self, file_id: UUID, file_manager: Any) -> None:
        """Delete a Train Data Source upload that the dialog no longer uses.

        The dialog uploads a training file as soon as it is picked, so a file that is
        rejected, replaced, removed or cancelled would otherwise stay in File Manager.
        Only a recent training upload (marked as one when it was uploaded) made by the
        caller that no live workflow version or ML model points at is deleted; anything else answers "not found", so the
        endpoint can't be used to remove or probe other files.
        """
        from app.modules.workflow.engine.nodes.ml.training_file_readers import SUPPORTED_TRAINING_FILE_SUFFIXES

        not_found = AppException(error_key=ErrorKey.FILE_NOT_FOUND, status_code=404)
        try:
            file = await file_manager.get_file_by_id(file_id)
        except AppException:
            raise not_found from None
        # Local uploads are also handed to the dialog as csvFilePath, which a node can keep.
        upload_paths = set()
        if file.storage_provider == "local" and file.storage_path and file.path:
            upload_path = f"{file.storage_path}/{file.path}"
            upload_paths |= {upload_path, os.path.normpath(upload_path)}
        discardable = (
            _is_own_recent_upload(file, file_manager, TRAINING_UPLOAD_FOLDER, UNUSED_TRAINING_UPLOAD_MAX_AGE)
            # Other features (knowledge bases, for example) upload into the same folder.
            and is_stored_training_upload(file.file_metadata)
            and f".{(file.file_extension or '').lower()}" in SUPPORTED_TRAINING_FILE_SUFFIXES
            and not await self.repository.is_training_file_referenced(file.id, sorted(upload_paths))
        )
        if not discardable:
            raise not_found

        await file_manager.delete_file(file.id)

    async def record_local_pkl_file(self, ml_model_id: UUID, pkl_file: str) -> MLModel:
        """Record where a downloaded copy of the model's own pkl_file_id is stored.

        The artifact itself is unchanged, so the registry contract is not re-validated.
        """
        return await self.repository.update(ml_model_id, {"pkl_file": pkl_file})

    async def delete(self, ml_model_id: UUID):
        """Delete an ML model and its associated .pkl file if it exists."""
        # Get the model first to access the pkl_file path
        ml_model = await self.repository.get_by_id(ml_model_id)

        # If there's a pkl_file, attempt to delete it. Rows saved before pkl_file was
        # validated may point anywhere, so only remove files inside the ML models folder.
        if ml_model.pkl_file and not is_in_ml_models_dir(ml_model.pkl_file):
            logger.warning(f"Not deleting pkl file outside the ML models folder: {ml_model.pkl_file}")
        elif ml_model.pkl_file and os.path.exists(ml_model.pkl_file):
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
