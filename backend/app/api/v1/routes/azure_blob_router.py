from fastapi import APIRouter, Depends, UploadFile, Form
from typing import Optional, List
import tempfile
import os
import aiofiles
from app.auth.dependencies import auth
from app.services.AzureStorageService import AzureStorageService
from app.schemas.azure_blob import (
    AzureConnection,
    AzureFileRequest as FileRequest,
    AzureListRequest as ListRequest,
    AzureMoveRequest as MoveRequest,
    AzureExistsResponse,
    AzureUploadResponse,
    AzureDeleteResponse,
)

router = APIRouter(dependencies=[Depends(auth)])


@router.post("/list", response_model=List[str])
async def list_files(req: ListRequest):
    """List blobs in a container with optional prefix"""
    svc = AzureStorageService.from_request(req)
    return svc.file_list(prefix=req.prefix)


@router.post("/exists", response_model=AzureExistsResponse)
async def file_exists(req: FileRequest):
    """Check if a blob exists"""
    svc = AzureStorageService.from_request(req)
    return AzureExistsResponse(exists=svc.file_exists(req.filename, prefix=req.prefix))


@router.post("/upload", response_model=AzureUploadResponse)
async def upload_file(
    file: UploadFile,
    connection_string: str = Form(...),
    container: str = Form(...),
    destination_name: str = Form(...),
    prefix: Optional[str] = Form(None),
):
    """Upload a file stream to Azure Blob"""
    tmp_path = None
    try:
        svc = AzureStorageService.from_request(AzureConnection(connection_string=connection_string, container=container))

        fd, tmp_path = tempfile.mkstemp()
        os.close(fd)
        async with aiofiles.open(tmp_path, "wb") as tmp:
            await tmp.write(await file.read())

        url = svc.file_upload(tmp_path, destination_name=destination_name, prefix=prefix)
        return AzureUploadResponse(status="success", url=url)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/upload-content", response_model=AzureUploadResponse)
async def upload_file_content(req: FileRequest):
    """Upload provided text/bytes content directly"""
    svc = AzureStorageService.from_request(req)
    data = req.content.encode("utf-8") if not req.binary else req.content
    url = svc.file_upload_content(
        local_file_content=data,
        local_file_name=req.filename,
        destination_name=req.filename,
        prefix=req.prefix,
    )
    return AzureUploadResponse(status="success", url=url)


@router.delete("/file", response_model=AzureDeleteResponse)
async def delete_file(req: FileRequest):
    """Delete a blob"""
    svc = AzureStorageService.from_request(req)
    ok = svc.file_delete(req.filename, prefix=req.prefix)
    return AzureDeleteResponse(status="success" if ok else "failed", deleted=ok)


@router.post("/move", response_model=AzureUploadResponse)
async def move_file(req: MoveRequest):
    """Move a blob (copy then delete original)"""
    svc = AzureStorageService.from_request(req)
    url = svc.file_move(
        source_name=req.source_name,
        destination_name=req.destination_name,
        source_prefix=req.source_prefix,
        destination_prefix=req.destination_prefix,
    )
    return AzureUploadResponse(status="success", url=url)


@router.post("/bucket-exists", response_model=AzureExistsResponse)
async def bucket_exists(req: AzureConnection):
    """Check if container exists"""
    svc = AzureStorageService.from_request(req)
    return AzureExistsResponse(exists=svc.bucket_exists())