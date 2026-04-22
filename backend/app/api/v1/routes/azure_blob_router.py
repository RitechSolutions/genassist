from fastapi import APIRouter, Depends, UploadFile, HTTPException, Form
from typing import Optional, List
import tempfile
import os
from app.auth.dependencies import auth
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services.AzureStorageService import AzureStorageService
import logging
from app.schemas.azure_blob import AzureConnection, AzureFileRequest as FileRequest, AzureListRequest as ListRequest, AzureMoveRequest as MoveRequest

router = APIRouter(dependencies=[Depends(auth)])

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def get_service(req: AzureConnection) -> AzureStorageService:
    try:
        return AzureStorageService(
            connection_string=req.connectionstring,
            container_name=req.container,
        )
    except Exception as e:
        logger.error(e)
        raise AppException(error_key=ErrorKey.AZURE_INIT_FAILED)


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@router.post("/list", response_model=List[str])
async def list_files(req: ListRequest):
    """List blobs in a container with optional prefix"""
    svc = get_service(AzureConnection(connectionstring=connectionstring, container=container))
    return svc.file_list(prefix=prefix)


@router.post("/exists")
async def file_exists(req: FileRequest):
    """Check if a blob exists"""
    svc = get_service(AzureConnection(connectionstring=connectionstring, container=container))
    return {"exists": svc.file_exists(filename, prefix=prefix)}


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    connectionstring: str = Form(...),
    container: str = Form(...),
    destination_name: str = Form(...),
    prefix: Optional[str] = Form(None),
):
    """Upload a file stream to Azure Blob"""
    try:
        svc = get_service(AzureConnection(connectionstring=connectionstring, container=container))

        # Save the uploaded data to a temporary file because the service requires a path
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        url = svc.file_upload(tmp_path, destination_name=destination_name, prefix=prefix)
        return {"status": "success", "url": url}
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/upload-content", dependencies=[
        Depends(auth),
    ])
async def upload_file_content(req: FileRequest):
    """Upload provided text/bytes content directly"""
    svc = get_service(req)
    data = req.content.encode("utf-8") if not req.binary else req.content
    url = svc.file_upload_content(
        local_file_content=data,
        local_file_name=req.filename,
        destination_name=req.filename,
        prefix=req.prefix,
    )
    return {"status": "success", "url": url}


@router.delete("/file", dependencies=[
        Depends(auth),
    ])
async def delete_file(req: FileRequest):
    """Delete a blob"""
    svc = get_service(req)
    ok = svc.file_delete(req.filename, prefix=req.prefix)
    return {"status": "success" if ok else "failed", "deleted": ok}


@router.post("/move", dependencies=[
        Depends(auth),
    ])
async def move_file(req: MoveRequest):
    """Move a blob (copy then delete original)"""
    svc = get_service(req)
    url = svc.file_move(
        source_name=req.source_name,
        destination_name=req.destination_name,
        source_prefix=req.source_prefix,
        destination_prefix=req.destination_prefix,
    )
    return {"status": "success", "url": url}


@router.post("/bucket-exists")
async def bucket_exists(req: AzureConnection):
    """Check if container exists"""
    svc = get_service(AzureConnection(connectionstring=connectionstring, container=container))
    return {"exists": svc.bucket_exists()}
