"""Copies ML node output CSVs to File Manager storage, so any server can read them, even after a restart."""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.storage_path import tenant_scoped_storage_prefix
from app.modules.filemanager.providers.base import BaseStorageProvider
from app.modules.workflow.engine.nodes.ml import ml_utils

logger = logging.getLogger(__name__)

# DATA_VOLUME/train/<thread>/<file> is stored as tenants/<slug>/ml_training/<thread>/<file>
STORAGE_FOLDER = "ml_training"

FETCH_FAILED_DETAIL = (
    "Could not read the training data from file storage. "
    "Try again, or run the node that produced it again."
)


def _train_relative_path(path: Any) -> Optional[str]:
    """The path inside DATA_VOLUME/train, or None for any other file."""
    try:
        real_path = os.path.realpath(str(path))
        train_root = os.path.realpath(str(ml_utils.DATA_VOLUME / "train"))
    except (ValueError, OSError):
        return None
    if not real_path.startswith(train_root + os.sep):
        return None
    return Path(os.path.relpath(real_path, train_root)).as_posix()


def _storage_key(local_path: Any) -> str:
    return tenant_scoped_storage_prefix(f"{STORAGE_FOLDER}/{_train_relative_path(local_path)}")


async def _storage_provider() -> BaseStorageProvider:
    """The provider set in File Manager Settings."""
    from app.core.config.settings import file_storage_settings
    from app.dependencies.injector import injector
    from app.services.app_settings import AppSettingsService
    from app.services.file_manager import FileManagerService

    app_settings = await injector.get(AppSettingsService).get_by_type_and_name(
        "FileManagerSettings", "File Manager Settings"
    )
    return await injector.get(FileManagerService).initialize(
        base_url=(file_storage_settings.APP_URL or "http://localhost:8000").rstrip("/"),
        base_path=str(ml_utils.DATA_VOLUME),
        app_settings=app_settings,
    )


def _already_in_storage(provider: BaseStorageProvider, path: Any) -> bool:
    """True when the local provider's folder holds the file (by default that folder is the data volume)."""
    if provider.name != "local":
        return False
    base_path = os.path.realpath(provider.get_base_path())
    return os.path.realpath(str(path)).startswith(base_path + os.sep)


async def _download(provider: BaseStorageProvider, key: str, destination: Path) -> None:
    """Download beside the destination, then move it in, so readers never see half a file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, partial = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".part"
    )
    os.close(handle)
    try:
        if not await provider.download_file_to_path(key, partial):
            raise OSError(f"the storage provider did not return {key}")
        os.replace(partial, destination)
    finally:
        Path(partial).unlink(missing_ok=True)


async def save_training_data(csv_path: Any) -> None:
    """Copy an output CSV under DATA_VOLUME/train and its column types to storage; on failure keep them here and log it."""
    path = Path(csv_path)
    if _train_relative_path(path) is None:
        return
    sidecar = ml_utils.dtypes_sidecar_path(path)
    try:
        provider = await _storage_provider()
        if _already_in_storage(provider, path):
            return
        # Column types first, so a server that finds the CSV also finds its types
        for local_file in ([sidecar] if sidecar.exists() else []) + [path]:
            key = _storage_key(local_file)
            if not await provider.upload_file_from_local_path(str(local_file), key):
                raise OSError(f"the storage provider did not store {key}")
    except Exception as exc:
        # The run still works on this server; other servers can't read the output, and the reason is only in this log
        logger.error("Could not save training data to file storage, so only this server has it: %s", exc)


async def fetch_training_data(
    file_url: Optional[str], thread_id: Optional[str] = None, allowed_directories: Optional[list] = None
) -> None:
    """Download an output CSV from storage when this server doesn't have it; other references are left as they are."""
    reference = (file_url or "").strip()
    if not reference or reference.startswith(("[", "{", "http://", "https://")):
        return
    candidates = ml_utils.csv_path_candidates(reference, thread_id)
    directories = [ml_utils.DATA_VOLUME, *(allowed_directories or [])]
    if any(ml_utils._csv_path_inside(candidate, directories) for candidate in candidates):
        return  # resolve_csv_file_path can read it here
    # Only node outputs: CSVs under DATA_VOLUME/train (their column types come with them)
    missing = [
        candidate
        for candidate in candidates
        if str(candidate).lower().endswith(".csv") and _train_relative_path(candidate) is not None
    ]
    if not missing:
        return
    try:
        provider = await _storage_provider()
        for candidate in missing:
            if _already_in_storage(provider, candidate):
                continue
            key = _storage_key(candidate)
            if not await provider.file_exists(key):
                continue
            destination = Path(os.path.realpath(str(candidate)))
            sidecar = ml_utils.dtypes_sidecar_path(destination)
            sidecar_key = _storage_key(sidecar)
            if await provider.file_exists(sidecar_key):
                await _download(provider, sidecar_key, sidecar)
            await _download(provider, key, destination)
            logger.info("Downloaded training data %s from file storage", key)
            return
    except Exception as exc:
        logger.error("Could not read training data from file storage: %s", exc)
        raise AppException(
            error_key=ErrorKey.ML_TRAINING_DATA_STORAGE_FAILED, error_detail=FETCH_FAILED_DETAIL
        ) from None


async def load_training_csv(file_url: str, thread_id: Optional[str] = None) -> pd.DataFrame:
    """ml_utils.load_csv_file for a node output that may have been written on another server."""
    directories = await ml_utils.extra_csv_directories()
    await fetch_training_data(file_url, thread_id, directories)
    return ml_utils.load_csv_file(file_url, thread_id, directories)
