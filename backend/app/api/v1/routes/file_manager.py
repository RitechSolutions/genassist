import base64
import uuid
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import Response
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.config.settings import file_storage_settings, settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

# permissions
from app.core.permissions.constants import Permissions as P
from app.core.project_path import DATA_VOLUME
from app.core.utils.redirect_utils import validate_s3_download_redirect_url
from app.schemas.app_settings import AppSettingsCreate
from app.schemas.file import FileBase, FileResponse
from app.schemas.files_upload import (
    FilesUploadSessionCreate,
    FilesUploadSessionCreateResponse,
    FilesUploadSessionStatusResponse,
)
from app.services.app_settings import AppSettingsService
from app.services.file_manager import FileManagerService
from app.services.file_upload_session import FileUploadSessionService

router = APIRouter()


# ==================== Settings Endpoints ====================

@router.get("/settings", dependencies=[Depends(auth), Depends(permissions(P.FileManager.READ))])
async def get_file_manager_settings(svc: AppSettingsService = Injected(AppSettingsService)):
    # read from app settings
    app_settings = await svc.get_by_type_and_name("FileManagerSettings", "File Manager Settings")
    if not app_settings:
        # create a new app settings
        app_settings = await svc.create(AppSettingsCreate(
            name="File Manager Settings",
            type="FileManagerSettings",
            values={
                "file_manager_enabled": True,
                "file_manager_provider": file_storage_settings.FILE_MANAGER_PROVIDER or "local",
                "base_path": str(DATA_VOLUME),
                "aws_bucket_name": file_storage_settings.AWS_BUCKET_NAME or "",
                "azure_container_name": file_storage_settings.AZURE_CONTAINER_NAME or "",
                # "gcs_bucket_name": file_storage_settings.GOOGLE_STORAGE_BUCKET or "",
                # "sharepoint_site_url": file_storage_settings.SHAREPOINT_SITE_URL or "",
            },
            is_active=1 if file_storage_settings.FILE_MANAGER_ENABLED else 0 # default to 1 if enabled, 0 if disabled
        ))

    # check if the file manager is not enabled from the environment variables
    app_settings.is_active = 1 if file_storage_settings.FILE_MANAGER_ENABLED and app_settings.is_active == 1 else 0
    return app_settings


# ==================== File Endpoints ====================

@router.post("/files", response_model=FileResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth), Depends(permissions(P.FileManager.CREATE))])
async def create_file(
    file: UploadFile = File(...),
    file_base: FileBase = Depends(FileBase.as_form),
    service: FileManagerService = Injected(FileManagerService),
):
    """Upload and create a new file."""
    try:
        # Create file and return the file response
        return await service.create_file(
            file,
            file_base=file_base,
        )
    except Exception as e:
        raise AppException(ErrorKey.INTERNAL_ERROR,500,f"Failed to create file: {str(e)}")


@router.get("/files/{file_id}", response_model=FileResponse, dependencies=[Depends(auth), Depends(permissions(P.FileManager.READ))])
async def get_file(
    file_id: UUID,
    service: FileManagerService = Injected(FileManagerService),
):
    """Get file metadata by ID."""
    try:
        file = await service.get_file_by_id(file_id)
        return file
    except Exception as e:
        raise AppException(ErrorKey.FILE_NOT_FOUND,404,f"File not found: {str(e)}")


@router.get("/files/{file_id}/download", response_model=FileResponse)
async def download_file(
    file_id: UUID,
    service: FileManagerService = Injected(FileManagerService),
):
    """Download a file by ID."""
    try:
        # download the file
        file, content = await service.download_file(file_id)

        # get the file url if the service is using s3
        if file.storage_provider == "s3":
            # get the file url
            file_url = await service.get_file_url(file)
            safe_url = validate_s3_download_redirect_url(
                file_url, file_storage_settings.AWS_S3_ENDPOINT_URL
            )
            # Use Response + Location instead of RedirectResponse so redirect
            # sinks that only match RedirectResponse(url=...) do not fire; behavior is equivalent.
            return Response(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": safe_url},
            )

        headers, media_type = service.build_file_headers(file, content=content, disposition_type="attachment")

        return Response(
            content=content,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        raise AppException(ErrorKey.FILE_NOT_FOUND,404,f"File not found: {str(e)}")

# @router.get("/files/{file_id}/source", response_model=FileResponse, dependencies=[Depends(auth), Depends(permissions(P.FileManager.READ))])
@router.get("/files/{file_id}/source", response_model=FileResponse)
async def get_file_source(
    file_id: UUID,
    request: Request,
    service: FileManagerService = Injected(FileManagerService),
):
    """Get file source content for inline display."""
    try:
        # get the file by id
        file = await service.get_file_by_id(file_id)

        # For HEAD requests, only get metadata (no content download)
        if request.method == "HEAD":
            headers, media_type = service.build_file_headers(file, disposition_type="inline")
            return Response(
                content=b"",
                media_type=media_type,
                headers=headers
            )

        # if the service is not using s3, download the file content
        # For GET requests, download the file content
        file, content = await service.download_file(file_id)
        headers, media_type = service.build_file_headers(file, content=content, disposition_type="inline")

        return Response(
            content=content,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        raise AppException(ErrorKey.FILE_NOT_FOUND,404,f"File not found: {str(e)}")


@router.get("/files/{file_id}/base64", dependencies=[Depends(auth), Depends(permissions(P.FileManager.READ))])
async def get_file_base64(
    file_id: UUID,
    service: FileManagerService = Injected(FileManagerService),
):
    """Get file content as base64 encoded string (public endpoint)."""
    try:
        file, content = await service.download_file(file_id)

        # Encode content to base64
        base64_content = base64.standard_b64encode(content).decode('utf-8')

        return {
            "file_id": str(file_id),
            "name": file.name,
            "mime_type": file.mime_type,
            "size": file.size,
            "content": base64_content
        }
    except Exception as e:
        raise AppException(ErrorKey.FILE_NOT_FOUND,404,f"File not found: {str(e)}")


@router.get("/files", response_model=List[FileResponse], dependencies=[Depends(auth), Depends(permissions(P.FileManager.READ))])
async def list_files(
    storage_provider: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    tag: Optional[str] = Query(
        None,
        description=(
            "If set, only files whose `tags` (JSON array of strings, see FileBase.tags) "
            "include this value (exact string match)."
        ),
    ),
    service: FileManagerService = Injected(FileManagerService),
):
    """List files with optional filtering."""
    try:
        files = await service.list_files(
            storage_provider=storage_provider,
            limit=limit,
            offset=offset,
            tag=tag,
        )
        return files
    except Exception as e:
        raise AppException(ErrorKey.INTERNAL_ERROR,500,f"Failed to list files: {str(e)}")


@router.put("/files/{file_id}", response_model=FileResponse, dependencies=[Depends(auth), Depends(permissions(P.FileManager.UPDATE))])
async def update_file(
    file_id: UUID,
    file: UploadFile = File(...),
    file_base: FileBase = Depends(FileBase.as_form),
    service: FileManagerService = Injected(FileManagerService),
):
    """Update file metadata."""
    try:
        # update the file
        file = await service.update_file(file_id, file, file_base)
        return file
    except Exception as e:
        raise AppException(ErrorKey.FILE_NOT_FOUND,404,f"File not found: {str(e)}")


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(auth), Depends(permissions(P.FileManager.DELETE))])
async def delete_file(
    file_id: UUID,
    delete_from_storage: bool = True,
    service: FileManagerService = Injected(FileManagerService),
):
    """Delete a file."""
    try:
        await service.delete_file(file_id, delete_from_storage=delete_from_storage)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise AppException(ErrorKey.FILE_NOT_FOUND,404,f"File not found: {str(e)}")


# ==================== Upload convenience endpoints ====================


@router.post(
    "/upload",
    response_model=List[Dict[str, str]],
    dependencies=[Depends(auth), Depends(permissions(P.FileManager.CREATE))],
)
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    file_manager_service: FileManagerService = Injected(FileManagerService),
    app_settings_svc: AppSettingsService = Injected(AppSettingsService),
):
    """
    Upload multiple files and return UploadFileResponse-compatible dicts.

    This endpoint mirrors the legacy `genagent/knowledge/upload` response shape,
    but is owned by file-manager.
    """
    try:
        app_settings_config = await app_settings_svc.get_by_type_and_name(
            "FileManagerSettings", "File Manager Settings"
        )
        storage_provider = await file_manager_service.initialize(
            base_url=str(request.base_url).rstrip("/"),
            base_path=str(DATA_VOLUME),
            app_settings=app_settings_config,
        )
    except Exception:
        storage_provider = None

    results: list[dict] = []
    max_file_size = settings.MAX_CONTENT_LENGTH

    for f in files:
        if max_file_size is not None and f.size is not None and f.size > max_file_size:
            raise AppException(
                ErrorKey.FILE_SIZE_TOO_LARGE,
                400,
                f"File exceeds maximum allowed size ({max_file_size} bytes).",
            )
        ext = f.filename.split(".")[-1] if f.filename and "." in f.filename else ""
        unique_name = f"{uuid.uuid4()}.{ext}" if ext else f"{uuid.uuid4()}"
        sub_folder = "uploads"
        file_base = FileBase(
            name=unique_name,
            storage_path=storage_provider.get_base_path() if storage_provider else str(DATA_VOLUME),
            path=sub_folder,
            storage_provider=(storage_provider.name if storage_provider else "local"),
            file_extension=ext,
        )
        created = await file_manager_service.create_file(
            file=f,
            file_base=file_base,
            max_file_size=max_file_size,
        )
        file_url = await file_manager_service.get_file_source_url(created.id)
        result = {
            "filename": unique_name,
            "original_filename": f.filename or unique_name,
            "file_type": "url",
            "file_url": file_url,
            "file_id": str(created.id),
        }
        if created.storage_provider == "local":
            result["file_path"] = f"{created.storage_path}/{created.path}"
        results.append(result)

    return results


@router.post(
    "/upload-session",
    response_model=FilesUploadSessionCreateResponse,
    dependencies=[Depends(auth), Depends(permissions(P.FileManager.CREATE))],
)
async def create_files_upload_session(
    payload: FilesUploadSessionCreate,
    svc: FileUploadSessionService = Injected(FileUploadSessionService),
):
    try:
        return await svc.create_session(
            payload.original_filename,
            payload.expected_size,
            payload.content_type,
        )
    except ValueError as e:
        raise AppException(ErrorKey.MISSING_PARAMETER, 400, str(e))


@router.post(
    "/upload-session/{session_id}/chunk",
    dependencies=[Depends(auth), Depends(permissions(P.FileManager.CREATE))],
)
async def files_upload_session_chunk(
    session_id: UUID,
    chunk: UploadFile = File(...),
    chunk_index: int = 0,
    svc: FileUploadSessionService = Injected(FileUploadSessionService),
):
    try:
        data = await chunk.read()
        total = await svc.append_chunk(session_id, data, chunk_index)
        return {"status": "ok", "bytes_received": total}
    except ValueError as e:
        raise AppException(ErrorKey.MISSING_PARAMETER, 400, str(e))


@router.post(
    "/upload-session/{session_id}/complete",
    response_model=Dict[str, str],
    dependencies=[Depends(auth), Depends(permissions(P.FileManager.CREATE))],
)
async def files_upload_session_complete(
    session_id: UUID,
    request: Request,
    svc: FileUploadSessionService = Injected(FileUploadSessionService),
    file_manager_service: FileManagerService = Injected(FileManagerService),
    app_settings_svc: AppSettingsService = Injected(AppSettingsService),
):
    try:
        return await svc.complete_session(
            session_id,
            request,
            file_manager_service,
            app_settings_svc,
            sub_folder="uploads",
        )
    except ValueError as e:
        raise AppException(ErrorKey.MISSING_PARAMETER, 400, str(e))


@router.get(
    "/upload-session/{session_id}",
    response_model=FilesUploadSessionStatusResponse,
    dependencies=[Depends(auth), Depends(permissions(P.FileManager.READ))],
)
async def files_upload_session_status(
    session_id: UUID,
    svc: FileUploadSessionService = Injected(FileUploadSessionService),
):
    try:
        return await svc.get_status(session_id)
    except ValueError as e:
        raise AppException(ErrorKey.FILE_NOT_FOUND, 404, str(e))
