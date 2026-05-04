"""Chunked upload session service (file-manager-owned)."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Request
from injector import inject

from app.core.config.settings import file_storage_settings, settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.core.utils.upload_streaming import append_bytes_to_path
from app.db.models.files_upload_session import FilesUploadSessionModel
from app.repositories.file_upload_session import FileUploadSessionRepository
from app.schemas.file import FileBase
from app.schemas.files_upload import (
    FilesUploadSessionCreateResponse,
    FilesUploadSessionStatusResponse,
)
from app.schemas.files_upload_direct import (
    FinalizeDirectUploadRequest,
    FinalizeDirectUploadResponse,
    PresignDirectUploadCreate,
    PresignDirectUploadResponse,
)
from app.services.app_settings import AppSettingsService
from app.services.file_manager import FileManagerService

logger = logging.getLogger(__name__)

SESSION_SUBDIR = "uploads/sessions"

STATUS_RECEIVING = "receiving"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
# Direct browser -> S3 presigned PUT flow only.
STATUS_AWAITING_CLIENT_UPLOAD = "awaiting_client_upload"

UPLOAD_MODE_SERVER_CHUNKED = "server_chunked"
UPLOAD_MODE_DIRECT_S3 = "direct_s3"

# Sentinel ``temp_path`` value used by the direct-S3 flow. The legacy chunked flow
# always writes to a real path under ``SESSION_SUBDIR``; the direct flow never
# touches local disk so we store this sentinel to keep the existing NOT NULL
# constraint on ``temp_path`` happy.
DIRECT_S3_TEMP_PATH_SENTINEL = "<direct_s3>"


@inject
class FileUploadSessionService:
    def __init__(self, repository: FileUploadSessionRepository):
        self.repository = repository
        self._session_dir = str(DATA_VOLUME / SESSION_SUBDIR)
        os.makedirs(self._session_dir, exist_ok=True)

    def _max_upload_bytes(self) -> int:
        # Backward compatible: if FILES_* is not present, fall back to KNOWLEDGE_*.
        return int(getattr(settings, "FILES_MAX_UPLOAD_BYTES", settings.FILES_MAX_UPLOAD_BYTES))

    def _max_chunk_bytes(self) -> int:
        return int(
            getattr(settings, "FILES_UPLOAD_MAX_CHUNK_BYTES", settings.FILES_UPLOAD_MAX_CHUNK_BYTES)
        )

    async def create_session(
        self,
        original_filename: str,
        expected_size: Optional[int],
        content_type: Optional[str] = None,
    ) -> FilesUploadSessionCreateResponse:
        max_b = self._max_upload_bytes()
        if expected_size is not None and expected_size > max_b:
            max_mb = round(max_b / 1024 / 1024, 2)
            raise ValueError(f"Declared file size exceeds maximum allowed ({max_mb} MB).")

        sid = uuid.uuid4()
        temp_path = os.path.join(self._session_dir, f"{sid}.part")
        row = FilesUploadSessionModel(
            id=sid,
            status=STATUS_RECEIVING,
            original_filename=original_filename,
            content_type=content_type,
            temp_path=temp_path,
            bytes_received=0,
            expected_bytes=expected_size,
            error_message=None,
            result_json=None,
        )
        await self.repository.create(row)
        return FilesUploadSessionCreateResponse(
            session_id=str(sid),
            max_chunk_bytes=self._max_chunk_bytes(),
        )

    async def append_chunk(
        self,
        session_id: UUID,
        chunk_bytes: bytes,
        chunk_index: int,
    ) -> int:
        max_b = self._max_upload_bytes()
        max_chunk = self._max_chunk_bytes()
        if len(chunk_bytes) > max_chunk:
            raise ValueError(f"Chunk exceeds maximum chunk size ({max_chunk} bytes).")

        row = await self.repository.get_by_id(session_id)
        if not row:
            raise ValueError("Upload session not found.")
        if row.status != STATUS_RECEIVING:
            raise ValueError(f"Cannot append to session in status: {row.status}")

        new_total = row.bytes_received + len(chunk_bytes)
        if new_total > max_b:
            row.status = STATUS_FAILED
            row.error_message = f"Upload exceeds maximum allowed size ({max_b} bytes)."
            await self.repository.update(row)
            raise ValueError(row.error_message)

        await append_bytes_to_path(row.temp_path, chunk_bytes)
        row.bytes_received = new_total
        row.status = STATUS_RECEIVING
        await self.repository.update(row)
        logger.info(
            "files_upload_session chunk: id=%s index=%s bytes=%s total=%s",
            session_id,
            chunk_index,
            len(chunk_bytes),
            new_total,
        )
        return new_total

    async def get_status(self, session_id: UUID) -> FilesUploadSessionStatusResponse:
        row = await self.repository.get_by_id(session_id)
        if not row:
            raise ValueError("Upload session not found.")
        result = None
        if row.status == STATUS_COMPLETED and row.result_json:
            result = row.result_json
        return FilesUploadSessionStatusResponse(
            id=str(row.id),
            status=row.status,
            bytes_received=row.bytes_received,
            expected_bytes=row.expected_bytes,
            error_message=row.error_message,
            result=result,
        )

    async def complete_session(
        self,
        session_id: UUID,
        request: Request,
        file_manager_service: FileManagerService,
        app_settings_svc: AppSettingsService,
        *,
        sub_folder: str = "uploads",
    ) -> dict:
        row = await self.repository.get_by_id(session_id)
        if not row:
            raise ValueError("Upload session not found.")
        if row.status == STATUS_COMPLETED and row.result_json:
            return row.result_json
        if row.status == STATUS_FAILED:
            raise ValueError(row.error_message or "Upload session failed.")
        if row.bytes_received <= 0:
            raise ValueError("No data received for this upload session.")

        max_b = self._max_upload_bytes()
        if row.bytes_received > max_b:
            row.status = STATUS_FAILED
            row.error_message = f"Upload exceeds maximum allowed size ({max_b} bytes)."
            await self.repository.update(row)
            raise ValueError(row.error_message)

        if row.expected_bytes is not None and row.bytes_received != row.expected_bytes:
            raise ValueError(
                f"Size mismatch: received {row.bytes_received} bytes, expected {row.expected_bytes}."
            )

        temp_path = row.temp_path
        if not os.path.isfile(temp_path):
            row.status = STATUS_FAILED
            row.error_message = "Staged upload file missing on server."
            await self.repository.update(row)
            raise ValueError(row.error_message)

        try:
            original_name = row.original_filename
            file_extension = original_name.split(".")[-1] if "." in original_name else ""
            unique_filename = (
                f"{uuid.uuid4()}.{file_extension}" if file_extension else f"{uuid.uuid4()}"
            )

            result: dict = {
                "filename": unique_filename,
                "original_filename": original_name,
            }

            use_file_manager = file_storage_settings.FILE_MANAGER_ENABLED
            if use_file_manager:
                app_settings_config = await app_settings_svc.get_by_type_and_name(
                    "FileManagerSettings", "File Manager Settings"
                )
                storage_provider = await file_manager_service.initialize(
                    base_url=str(request.base_url).rstrip("/"),
                    base_path=str(DATA_VOLUME),
                    app_settings=app_settings_config,
                )

                file_base = FileBase(
                    name=unique_filename,
                    storage_path=storage_provider.get_base_path(),
                    path=sub_folder,
                    storage_provider=storage_provider.name,
                    file_extension=file_extension,
                )

                created_file = await file_manager_service.create_file_from_local_path(
                    temp_path,
                    file_base=file_base,
                    original_filename=original_name,
                    mime_type=row.content_type,
                    max_file_size=max_b,
                    delete_source=True,
                )

                file_url = await file_manager_service.get_file_source_url(created_file.id)
                result["file_type"] = "url"
                result["file_url"] = file_url
                result["file_id"] = str(created_file.id)
                if created_file.storage_provider == "local":
                    result["file_path"] = f"{created_file.storage_path}/{created_file.path}"
            else:
                upload_dir = str(DATA_VOLUME / sub_folder)
                os.makedirs(upload_dir, exist_ok=True)
                dest_path = os.path.join(upload_dir, unique_filename)

                def _move() -> None:
                    shutil.move(temp_path, dest_path)

                await asyncio.to_thread(_move)
                result["file_path"] = dest_path

            row.status = STATUS_COMPLETED
            row.result_json = result
            row.error_message = None
            await self.repository.update(row)
            return result
        except Exception as e:
            logger.exception("complete_session failed: %s", e)
            row.status = STATUS_FAILED
            row.error_message = str(e)
            await self.repository.update(row)
            staged = row.temp_path
            if staged and os.path.isfile(staged):
                try:
                    os.unlink(staged)
                except OSError:
                    pass
            raise

    # ==================== Direct S3 (presigned PUT) flow ====================

    def _direct_s3_enabled(self) -> bool:
        """Return True when the opt-in direct browser -> S3 upload flow is active.

        Activation requires both the global file-manager toggle and the new feature
        flag. The provider check happens in the service methods because we need an
        initialized provider to actually mint a presigned URL.
        """
        return bool(
            file_storage_settings.FILE_MANAGER_ENABLED
            and getattr(settings, "FILES_DIRECT_S3_UPLOAD_ENABLED", False)
        )

    def _direct_s3_expires_in(self) -> int:
        return int(getattr(settings, "FILES_DIRECT_S3_PRESIGN_EXPIRES_SECONDS", 600))

    async def create_direct_upload_session(
        self,
        payload: PresignDirectUploadCreate,
        request: Request,
        file_manager_service: FileManagerService,
        app_settings_svc: AppSettingsService,
        *,
        sub_folder: str = "uploads",
    ) -> PresignDirectUploadResponse:
        """Allocate an S3 object key, pre-create a pending ``files`` row and
        return a presigned PUT URL for the client to upload directly.

        On any error during this method we fail closed (no DB rows leaked).
        """

        if not self._direct_s3_enabled():
            raise AppException(
                ErrorKey.INTERNAL_ERROR,
                501,
                "Direct S3 upload is disabled. Set FILES_DIRECT_S3_UPLOAD_ENABLED=true.",
            )

        max_b = self._max_upload_bytes()
        if payload.expected_size is not None and payload.expected_size > max_b:
            max_mb = round(max_b / 1024 / 1024, 2)
            raise ValueError(f"Declared file size exceeds maximum allowed ({max_mb} MB).")

        # Initialize the file-manager + storage provider.
        app_settings_config = await app_settings_svc.get_by_type_and_name(
            "FileManagerSettings", "File Manager Settings"
        )
        storage_provider = await file_manager_service.initialize(
            base_url=str(request.base_url).rstrip("/"),
            base_path=str(DATA_VOLUME),
            app_settings=app_settings_config,
        )
        provider_name = getattr(storage_provider, "name", None)
        if provider_name != "s3":
            raise AppException(
                ErrorKey.INTERNAL_ERROR,
                501,
                "Direct upload is only supported when the file manager provider is s3.",
            )
        if not hasattr(storage_provider, "generate_presigned_put_url"):
            raise AppException(
                ErrorKey.INTERNAL_ERROR,
                501,
                "Active S3 provider does not support presigned PUT URLs.",
            )

        # Allocate a unique object key.
        original_name = payload.original_filename
        file_extension = (
            original_name.split(".")[-1].lower() if "." in original_name else ""
        )
        unique_filename = (
            f"{uuid.uuid4()}.{file_extension}" if file_extension else f"{uuid.uuid4()}"
        )
        clean_sub_folder = (sub_folder or "").strip("/").strip()
        object_key = (
            f"{clean_sub_folder}/{unique_filename}" if clean_sub_folder else unique_filename
        )

        # Pre-create a placeholder ``files`` row so the client gets a stable file_id
        # back that already points at a real (pending) record. The row is filled in
        # with size/mime_type on finalize, or soft-deleted on failure.
        file_base = FileBase(
            name=unique_filename,
            original_filename=original_name,
            storage_path=storage_provider.get_base_path(),
            path=object_key,
            storage_provider=provider_name,
            file_extension=file_extension or None,
            mime_type=payload.content_type,
            size=None,
            file_metadata={"direct_upload": True, "status": "pending"},
        )
        try:
            created_file = await file_manager_service.repository.create_file(file_base)
        except Exception as e:
            logger.exception("create_direct_upload_session: failed to create files row")
            raise AppException(
                ErrorKey.INTERNAL_ERROR,
                500,
                f"Failed to create pending file record: {e}",
            )

        # Mint the presigned URL.
        try:
            expires_in = self._direct_s3_expires_in()
            presigned_url = await storage_provider.generate_presigned_put_url(
                object_key,
                payload.content_type,
                expires_in,
            )
        except Exception as e:
            logger.exception("create_direct_upload_session: presign failed; rolling back")
            try:
                await file_manager_service.repository.delete_file(created_file.id)
            except Exception:
                pass
            raise AppException(
                ErrorKey.INTERNAL_ERROR, 500, f"Failed to generate presigned URL: {e}"
            )

        # Persist the upload-session row that ties the presigned URL to the files row.
        sid = uuid.uuid4()
        result_json: Dict[str, Any] = {
            "object_key": object_key,
            "file_id": str(created_file.id),
            "sub_folder": clean_sub_folder,
            "unique_filename": unique_filename,
            "provider_name": provider_name,
        }
        row = FilesUploadSessionModel(
            id=sid,
            status=STATUS_AWAITING_CLIENT_UPLOAD,
            original_filename=original_name,
            content_type=payload.content_type,
            temp_path=DIRECT_S3_TEMP_PATH_SENTINEL,
            bytes_received=0,
            expected_bytes=payload.expected_size,
            error_message=None,
            result_json=result_json,
            upload_mode=UPLOAD_MODE_DIRECT_S3,
        )
        try:
            await self.repository.create(row)
        except Exception as e:
            logger.exception("create_direct_upload_session: failed to persist session row")
            try:
                await file_manager_service.repository.delete_file(created_file.id)
            except Exception:
                pass
            raise AppException(
                ErrorKey.INTERNAL_ERROR,
                500,
                f"Failed to persist upload session: {e}",
            )

        required_headers: Dict[str, str] = {}
        if payload.content_type:
            required_headers["Content-Type"] = payload.content_type

        return PresignDirectUploadResponse(
            session_id=str(sid),
            file_id=str(created_file.id),
            object_key=object_key,
            presigned_url=presigned_url,
            method="PUT",
            required_headers=required_headers,
            expires_in=expires_in,
        )

    async def finalize_direct_upload_session(
        self,
        session_id: UUID,
        body: FinalizeDirectUploadRequest,
        request: Request,
        file_manager_service: FileManagerService,
        app_settings_svc: AppSettingsService,
    ) -> FinalizeDirectUploadResponse:
        """Finalize a direct S3 upload session.

        On success: HEAD the S3 object, validate size, fill in the placeholder
        ``files`` row and return an UploadFileResponse-compatible payload.
        On failure: best-effort delete of the S3 object + soft-delete of the
        placeholder ``files`` row, mark session ``failed``.
        """

        row = await self.repository.get_by_id(session_id)
        if not row:
            raise ValueError("Upload session not found.")
        if (row.upload_mode or UPLOAD_MODE_SERVER_CHUNKED) != UPLOAD_MODE_DIRECT_S3:
            raise ValueError(
                "Session does not belong to the direct-S3 upload flow; use /complete instead."
            )

        # Idempotent re-finalize: if a previous successful call already produced a
        # result_json with a file_url we just return it.
        meta = dict(row.result_json or {})
        if (
            row.status == STATUS_COMPLETED
            and meta.get("file_url")
            and meta.get("file_id")
        ):
            return FinalizeDirectUploadResponse(
                file_id=str(meta["file_id"]),
                filename=meta.get("filename") or row.original_filename,
                original_filename=meta.get("original_filename") or row.original_filename,
                file_type="url",
                file_url=meta.get("file_url"),
                file_path=meta.get("file_path"),
                extra=None,
            )
        if row.status not in (STATUS_AWAITING_CLIENT_UPLOAD,):
            raise ValueError(
                f"Cannot finalize session in status: {row.status}. "
                "Already finalized or failed."
            )

        object_key = meta.get("object_key")
        file_id_str = meta.get("file_id")
        if not object_key or not file_id_str:
            raise ValueError("Session is missing object_key/file_id metadata.")
        try:
            file_id = UUID(file_id_str)
        except (TypeError, ValueError):
            raise ValueError("Session has malformed file_id metadata.")

        # Initialize the storage provider regardless of branch (cleanup may need it).
        app_settings_config = await app_settings_svc.get_by_type_and_name(
            "FileManagerSettings", "File Manager Settings"
        )
        storage_provider = await file_manager_service.initialize(
            base_url=str(request.base_url).rstrip("/"),
            base_path=str(DATA_VOLUME),
            app_settings=app_settings_config,
        )

        if not body.success:
            await self._cleanup_direct_upload(
                row,
                storage_provider,
                file_manager_service,
                file_id,
                object_key,
                error=body.error_message or "Client reported upload failure.",
            )
            raise ValueError(row.error_message or "Client reported upload failure.")

        # ---- Verify the object actually landed in S3 ----
        try:
            head = await storage_provider.head_object(object_key)
        except Exception as e:
            logger.warning(
                "finalize_direct_upload_session: head_object failed for %s: %s",
                object_key,
                e,
            )
            await self._cleanup_direct_upload(
                row,
                storage_provider,
                file_manager_service,
                file_id,
                object_key,
                error=f"Uploaded object not found in S3: {e}",
            )
            raise ValueError("Uploaded object not found in S3.")

        actual_size = int(head.get("size") or 0)
        max_b = self._max_upload_bytes()
        if actual_size <= 0:
            await self._cleanup_direct_upload(
                row,
                storage_provider,
                file_manager_service,
                file_id,
                object_key,
                error="Uploaded object is empty.",
            )
            raise ValueError("Uploaded object is empty.")
        if actual_size > max_b:
            await self._cleanup_direct_upload(
                row,
                storage_provider,
                file_manager_service,
                file_id,
                object_key,
                error=f"Uploaded object exceeds max allowed size ({max_b} bytes).",
            )
            raise ValueError(
                f"Uploaded object exceeds max allowed size ({max_b} bytes)."
            )
        if (
            row.expected_bytes is not None
            and row.expected_bytes > 0
            and actual_size != row.expected_bytes
        ):
            await self._cleanup_direct_upload(
                row,
                storage_provider,
                file_manager_service,
                file_id,
                object_key,
                error=(
                    f"Size mismatch: S3 reports {actual_size} bytes, "
                    f"client declared {row.expected_bytes}."
                ),
            )
            raise ValueError(
                f"Size mismatch: S3 reports {actual_size} bytes, "
                f"client declared {row.expected_bytes}."
            )

        # ---- Update the placeholder files row in place ----
        try:
            db_file = await file_manager_service.repository.get_file_by_id(file_id)
            db_file.size = actual_size
            mime_from_head = head.get("content_type")
            if mime_from_head and not db_file.mime_type:
                db_file.mime_type = mime_from_head
            existing_meta = dict(db_file.file_metadata or {})
            existing_meta.update(
                {
                    "direct_upload": True,
                    "status": "completed",
                    "etag": head.get("etag"),
                }
            )
            db_file.file_metadata = existing_meta
            await file_manager_service.repository.db.commit()
            await file_manager_service.repository.db.refresh(db_file)
        except Exception as e:
            logger.exception(
                "finalize_direct_upload_session: failed to update files row"
            )
            await self._cleanup_direct_upload(
                row,
                storage_provider,
                file_manager_service,
                file_id,
                object_key,
                error=f"Failed to register file metadata: {e}",
            )
            raise

        # ---- Build the UploadFileResponse-shaped result and persist on session ----
        file_url = await file_manager_service.get_file_source_url(db_file.id)
        result: Dict[str, Any] = {
            "file_id": str(db_file.id),
            "filename": meta.get("unique_filename") or db_file.name,
            "original_filename": row.original_filename,
            "file_type": "url",
            "file_url": file_url,
            "object_key": object_key,
        }

        row.bytes_received = actual_size
        row.status = STATUS_COMPLETED
        row.error_message = None
        row.result_json = {**meta, **result}
        await self.repository.update(row)

        return FinalizeDirectUploadResponse(
            file_id=result["file_id"],
            filename=result["filename"],
            original_filename=result["original_filename"],
            file_type="url",
            file_url=file_url,
            file_path=None,
            extra=None,
        )

    async def _cleanup_direct_upload(
        self,
        row: FilesUploadSessionModel,
        storage_provider: Any,
        file_manager_service: FileManagerService,
        file_id: UUID,
        object_key: str,
        *,
        error: str,
    ) -> None:
        """Best-effort cleanup for a failed/incomplete direct-S3 upload.

        Never raises: cleanup is always advisory and we want the original error
        path to surface its message.
        """
        try:
            await storage_provider.delete_file(object_key)
        except Exception as e:
            logger.warning(
                "cleanup direct upload: delete_file(%s) failed: %s", object_key, e
            )
        try:
            await file_manager_service.repository.delete_file(file_id)
        except Exception as e:
            logger.warning(
                "cleanup direct upload: delete_file row %s failed: %s", file_id, e
            )
        try:
            row.status = STATUS_FAILED
            row.error_message = error
            await self.repository.update(row)
        except Exception as e:
            logger.warning("cleanup direct upload: update session row failed: %s", e)

