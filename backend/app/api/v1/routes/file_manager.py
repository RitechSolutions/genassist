from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Request
from fastapi.responses import Response
from uuid import UUID
from typing import Optional, List
import base64
import mimetypes
from urllib.parse import quote

from app.schemas.file import (
    FileCreate, FileUpdate, FileResponse
)
from app.repositories.file_manager import FileManagerRepository
from app.modules.filemanager.manager import get_file_manager_manager
from app.auth.dependencies import auth
from fastapi_injector import Injected
from app.db.models.file import StorageProvider

router = APIRouter()


def _build_file_headers(file, content: Optional[bytes] = None, disposition_type: str = "inline") -> tuple[dict, str]:
    """Build HTTP headers for file responses."""
    media_type = file.mime_type or "application/octet-stream"
    
    # Properly encode filename for Content-Disposition header
    # Use RFC 5987 encoding for non-ASCII characters to avoid latin-1 encoding errors
    # Percent-encode the filename for safe ASCII representation
    filename_encoded = quote(file.name, safe='')
    
    # For UTF-8 version (RFC 5987), percent-encode UTF-8 bytes
    filename_utf8_bytes = file.name.encode('utf-8')
    filename_utf8_encoded = ''.join(f'%{b:02X}' for b in filename_utf8_bytes)
    
    # Build Content-Disposition header with both ASCII fallback and UTF-8 version
    content_disposition = f'{disposition_type};filename="{filename_encoded}";filename*=UTF-8\'\'{filename_utf8_encoded}'
    
    headers = {
        "content-type": media_type,
        "content-disposition": content_disposition,
        "x-content-type-options": "nosniff",
        "access-control-allow-origin": "*",
        "access-control-expose-headers": "Age, Date, Content-Length, Content-Range, X-Content-Duration, X-Cache",
        "cache-control": "public, max-age=31536000"
    }
    
    # Add Content-Length if content is provided
    if content is not None:
        headers["content-length"] = str(len(content))
    elif hasattr(file, 'size') and file.size:
        headers["content-Length"] = str(file.size)
    
    return headers, media_type


# ==================== File Endpoints ====================

@router.post("/files", response_model=FileResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth)])
async def create_file(
    file: UploadFile,
    description: Optional[str] = None,
    file_metadata: Optional[dict] = None,
    tags: Optional[List[str]] = None,
    storage_provider: StorageProvider = StorageProvider.LOCAL,
    repository: FileManagerRepository = Injected(FileManagerRepository),
):
    """Upload and create a new file."""
    try:
        # Read file content
        file_content = await file.read()
        
        # Detect MIME type if not provided
        mime_type = file.content_type
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(file.filename or "")
        
        # Create file data
        file_data = FileCreate(
            name=file.filename or "untitled",
            mime_type=mime_type,
            size=len(file_content),
            description=description,
            file_metadata=file_metadata or {},
            tags=tags or [],
            storage_provider=storage_provider
        )
        
        # Get service from manager
        manager = get_file_manager_manager()
        service = await manager.get_service(repository)
        
        if not service:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize file manager service"
            )
        
        # Create file
        db_file = await service.create_file(file_data, file_content)
        return db_file
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create file: {str(e)}"
        )


@router.get("/files/{file_id}", response_model=FileResponse, dependencies=[Depends(auth)])
async def get_file(
    file_id: UUID,
    repository: FileManagerRepository = Injected(FileManagerRepository),
):
    """Get file metadata by ID."""
    try:
        manager = get_file_manager_manager()
        service = await manager.get_service(repository)
        
        if not service:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize file manager service"
            )
        
        file = await service.get_file_by_id(file_id)
        return file
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {str(e)}"
        )


@router.api_route("/files/{file_id}/download", methods=["GET", "HEAD"], operation_id="download_file")
async def download_file(
    file_id: UUID,
    repository: FileManagerRepository = Injected(FileManagerRepository),
):
    """Download a file by ID."""
    try:
        manager = get_file_manager_manager()
        service = await manager.get_service(repository)
        
        if not service:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize file manager service"
            )
        
        # download the file
        file, content = await service.download_file(file_id)
        headers, media_type = _build_file_headers(file, content=content, disposition_type="attachment")
        
        return Response(
            content=content,
            media_type=media_type,      
            headers=headers
        )
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {str(e)}"
        )

@router.api_route("/files/{file_id}/source", methods=["GET", "HEAD"], operation_id="get_file_source")
async def get_file_source(
    file_id: UUID,
    request: Request,
    repository: FileManagerRepository = Injected(FileManagerRepository),
):
    try:
        manager = get_file_manager_manager()
        service = await manager.get_service(repository)
        
        if not service:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize file manager service"
            )

        # For HEAD requests, only get metadata (no content download)
        if request.method == "HEAD":
            file = await service.get_file_by_id(file_id)
            headers, media_type = _build_file_headers(file, disposition_type="inline")
            return Response(
                content=b"",
                media_type=media_type,
                headers=headers
            )
        
        # For GET requests, download the file content
        file, content = await service.download_file(file_id)
        headers, media_type = _build_file_headers(file, content=content, disposition_type="inline")
        
        return Response(
            content=content,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {str(e)}"
        )


@router.get("/files/{file_id}/base64")
async def get_file_base64(
    file_id: UUID,
    repository: FileManagerRepository = Injected(FileManagerRepository),
):
    """Get file content as base64 encoded string (public endpoint)."""
    try:
        manager = get_file_manager_manager()
        service = await manager.get_service(repository)

        if not service:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize file manager service"
            )

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
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {str(e)}"
        )


@router.get("/files", response_model=List[FileResponse], dependencies=[Depends(auth)])
async def list_files(
    storage_provider: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    repository: FileManagerRepository = Injected(FileManagerRepository),
):
    """List files with optional filtering."""
    try:
        manager = get_file_manager_manager()
        service = await manager.get_service(repository)
        
        if not service:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize file manager service"
            )
        
        files = await service.list_files(
            storage_provider=storage_provider,
            limit=limit,
            offset=offset
        )
        return files
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )


@router.put("/files/{file_id}", response_model=FileResponse, dependencies=[Depends(auth)])
async def update_file(
    file_id: UUID,
    file_update: FileUpdate,
    repository: FileManagerRepository = Injected(FileManagerRepository),
):
    """Update file metadata."""
    try:
        manager = get_file_manager_manager()
        service = await manager.get_service(repository)
        
        if not service:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize file manager service"
            )
        
        file = await service.update_file(file_id, file_update)
        return file
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {str(e)}"
        )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(auth)])
async def delete_file(
    file_id: UUID,
    delete_from_storage: bool = True,
    repository: FileManagerRepository = Injected(FileManagerRepository),
):
    """Delete a file."""
    try:
        manager = get_file_manager_manager()
        service = await manager.get_service(repository)
        
        if not service:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize file manager service"
            )
        
        await service.delete_file(file_id, delete_from_storage=delete_from_storage)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {str(e)}"
        )
