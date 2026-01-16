from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
from fastapi.responses import Response
from uuid import UUID
from typing import Optional, List
import mimetypes

from app.schemas.file import (
    FileCreate, FileUpdate, FileResponse
)
from app.repositories.file_manager import FileManagerRepository
from app.modules.filemanager.manager import get_file_manager_manager
from app.auth.dependencies import auth
from fastapi_injector import Injected
from app.db.models.file import StorageProvider

router = APIRouter()


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


@router.get("/files/{file_id}/download", dependencies=[Depends(auth)])
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
        
        file, content = await service.download_file(file_id)
        
        # Determine media type
        media_type = file.mime_type or "application/octet-stream"
        
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file.name}"',
                "Content-Length": str(len(content)),
            }
        )
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
