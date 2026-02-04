from fastapi import APIRouter, Depends, status, UploadFile, Request
from fastapi.responses import Response
from uuid import UUID
from typing import Optional, List
import base64
import mimetypes

from app.schemas.file import (
    FileCreate, FileUpdate, FileResponse
)
from app.services.file_manager import FileManagerService
from app.auth.dependencies import auth
from fastapi_injector import Injected
from app.db.models.file import StorageProvider
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey

router = APIRouter()


# ==================== File Endpoints ====================

@router.post("/files", response_model=FileResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth)])
async def create_file(
    file_create: FileCreate,
    service: FileManagerService = Injected(FileManagerService),
):
    """Upload and create a new file."""
    try:
        # if we want check for file extension, we can do it here
        # allowed_extensions = ["pdf", "docx", "txt", "jpg", "jpeg", "png"];
        allowed_extensions = None

        # Create file and return the file response
        return await service.create_file(file_create, allowed_extensions=allowed_extensions)
    except Exception as e:
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            status_code=500,
            detail=f"Failed to create file: {str(e)}"
        )


@router.get("/files/{file_id}", response_model=FileResponse, dependencies=[Depends(auth)])
async def get_file(
    file_id: UUID,
    service: FileManagerService = Injected(FileManagerService),
):
    """Get file metadata by ID."""
    try:
        file = await service.get_file_by_id(file_id)
        return file
    except Exception as e:
        raise AppException(
            error_key=ErrorKey.FILE_NOT_FOUND,
            status_code=404,
            detail=f"File not found: {str(e)}"
        )


@router.get("/files/{file_id}/download", response_model=FileResponse)
async def download_file(
    file_id: UUID,
    service: FileManagerService = Injected(FileManagerService),
):
    """Download a file by ID."""
    try:
        # download the file
        file, content = await service.download_file(file_id)
        headers, media_type = service.build_file_headers(file, content=content, disposition_type="attachment")

        return Response(
            content=content,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        raise AppException(
            error_key=ErrorKey.FILE_NOT_FOUND,
            status_code=404,
            detail=f"File not found: {str(e)}"
        )

@router.get("/files/{file_id}/source", response_model=FileResponse)
async def get_file_source(
    file_id: UUID,
    request: Request,
    service: FileManagerService = Injected(FileManagerService),
):
    """Get file source content for inline display."""
    try:
        # For HEAD requests, only get metadata (no content download)
        if request.method == "HEAD":
            file = await service.get_file_by_id(file_id)
            headers, media_type = service.build_file_headers(file, disposition_type="inline")
            return Response(
                content=b"",
                media_type=media_type,
                headers=headers
            )

        # For GET requests, download the file content
        file, content = await service.download_file(file_id)
        headers, media_type = service.build_file_headers(file, content=content, disposition_type="inline")

        return Response(
            content=content,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        raise AppException(
            error_key=ErrorKey.FILE_NOT_FOUND,
            status_code=404,
            detail=f"File not found: {str(e)}"
        )


@router.get("/files/{file_id}/base64")
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
        raise AppException(
            error_key=ErrorKey.FILE_NOT_FOUND,
            status_code=404,
            detail=f"File not found: {str(e)}"
        )


@router.get("/files", response_model=List[FileResponse], dependencies=[Depends(auth)])
async def list_files(
    storage_provider: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    service: FileManagerService = Injected(FileManagerService),
):
    """List files with optional filtering."""
    try:
        files = await service.list_files(
            storage_provider=storage_provider,
            limit=limit,
            offset=offset
        )
        return files
    except Exception as e:
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )


@router.put("/files/{file_id}", response_model=FileResponse, dependencies=[Depends(auth)])
async def update_file(
    file_id: UUID,
    file_update: FileUpdate,
    service: FileManagerService = Injected(FileManagerService),
):
    """Update file metadata."""
    try:
        file = await service.update_file(file_id, file_update)
        return file
    except Exception as e:
        raise AppException(
            error_key=ErrorKey.FILE_NOT_FOUND,
            status_code=404,
            detail=f"File not found: {str(e)}"
        )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(auth)])
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
        raise AppException(
            error_key=ErrorKey.FILE_NOT_FOUND,
            status_code=404,
            detail=f"File not found: {str(e)}"
        )
