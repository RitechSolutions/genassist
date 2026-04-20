"""Chunked upload session service (file-manager-owned)."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from typing import Optional
from uuid import UUID

from fastapi import Request
from injector import inject

from app.core.config.settings import file_storage_settings, settings
from app.core.project_path import DATA_VOLUME
from app.core.utils.upload_streaming import append_bytes_to_path
from app.db.models.files_upload_session import FilesUploadSessionModel
from app.repositories.file_upload_session import FileUploadSessionRepository
from app.schemas.file import FileBase
from app.schemas.files_upload import (
    FilesUploadSessionCreateResponse,
    FilesUploadSessionStatusResponse,
)
from app.services.app_settings import AppSettingsService
from app.services.file_manager import FileManagerService

logger = logging.getLogger(__name__)

SESSION_SUBDIR = "uploads/sessions"

STATUS_RECEIVING = "receiving"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


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

