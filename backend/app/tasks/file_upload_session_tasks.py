"""Periodic cleanup for stale direct-S3 upload sessions.

This task only touches sessions in status ``awaiting_client_upload`` whose
``upload_mode`` is ``direct_s3``. Legacy chunked sessions (``server_chunked``
mode, status ``receiving``) are untouched and continue to follow their own
lifecycle.

It is safe to run with the feature flag off: in that case there will simply
be no rows to clean.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import select

from app.core.config.settings import settings
from app.db.models.files_upload_session import FilesUploadSessionModel
from app.dependencies.injector import injector
from app.repositories.file_manager import FileManagerRepository
from app.repositories.file_upload_session import FileUploadSessionRepository
from app.services.file_manager import FileManagerService
from app.services.file_upload_session import (
    STATUS_AWAITING_CLIENT_UPLOAD,
    STATUS_FAILED,
    UPLOAD_MODE_DIRECT_S3,
)

logger = logging.getLogger(__name__)


@shared_task
def cleanup_stale_direct_upload_sessions():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(cleanup_stale_direct_upload_sessions_with_scope())


async def cleanup_stale_direct_upload_sessions_with_scope():
    """Wrapper to run cleanup for all tenants."""
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        cleanup_stale_direct_upload_sessions_async,
        "cleanup of stale direct-S3 upload sessions",
    )


async def cleanup_stale_direct_upload_sessions_async() -> dict:
    """Mark expired direct-S3 sessions as failed and free the placeholder rows.

    A session is considered "stale" when its ``updated_at`` is older than
    ``2 * FILES_DIRECT_S3_PRESIGN_EXPIRES_SECONDS`` and it is still sitting in
    ``awaiting_client_upload``. We never touch sessions that already moved to
    ``completed``/``failed``/``receiving``.
    """

    expires_in = int(getattr(settings, "FILES_DIRECT_S3_PRESIGN_EXPIRES_SECONDS", 600))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(60, expires_in * 2))

    repo = injector.get(FileUploadSessionRepository)
    file_repo = injector.get(FileManagerRepository)

    query = select(FilesUploadSessionModel).where(
        FilesUploadSessionModel.status == STATUS_AWAITING_CLIENT_UPLOAD,
        FilesUploadSessionModel.upload_mode == UPLOAD_MODE_DIRECT_S3,
        FilesUploadSessionModel.is_deleted == 0,
        FilesUploadSessionModel.updated_at < cutoff,
    )
    result = await repo.db.execute(query)
    stale_rows = result.scalars().all()

    if not stale_rows:
        return {"status": "completed", "scanned": 0, "expired": 0, "errors": 0}

    fm_service = injector.get(FileManagerService)
    expired = 0
    errors = 0

    for row in stale_rows:
        try:
            meta = dict(row.result_json or {})
            object_key = meta.get("object_key")
            file_id = meta.get("file_id")

            if object_key and fm_service.storage_provider is not None:
                try:
                    await fm_service.storage_provider.delete_file(object_key)
                except Exception as e:
                    logger.warning(
                        "stale-direct-upload: best-effort S3 delete failed for %s: %s",
                        object_key,
                        e,
                    )

            if file_id:
                try:
                    from uuid import UUID as _UUID

                    await file_repo.delete_file(_UUID(str(file_id)))
                except Exception as e:
                    logger.warning(
                        "stale-direct-upload: failed to soft-delete files row %s: %s",
                        file_id,
                        e,
                    )

            row.status = STATUS_FAILED
            row.error_message = (
                row.error_message or "Direct upload expired before client finalize."
            )
            await repo.update(row)
            expired += 1
        except Exception as e:
            errors += 1
            logger.exception("stale-direct-upload: cleanup row %s failed: %s", row.id, e)

    return {
        "status": "completed",
        "scanned": len(stale_rows),
        "expired": expired,
        "errors": errors,
    }
