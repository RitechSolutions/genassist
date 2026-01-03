from fastapi import APIRouter, Depends, UploadFile, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import tempfile
import os

from app.auth.dependencies import auth
from app.services.AzureStorageService import AzureStorageService

router = APIRouter(dependencies=[Depends(auth)])


# -----------------------------------------------------------------------------
# Pydantic models matching request style
# -----------------------------------------------------------------------------
class AzureConnection(BaseModel):
    connectionstring: Optional[str] = None
    container: Optional[str] = None


class FileRequest(AzureConnection):
    filename: str
    prefix: Optional[str] = None
    overwrite: Optional[bool] = True
    content: Optional[str] = None  # For text/binary content upload
    binary: Optional[bool] = False


class MoveRequest(AzureConnection):
    source_name: str
    destination_name: str
    source_prefix: Optional[str] = None
    destination_prefix: Optional[str] = None


class ListRequest(AzureConnection):
    prefix: Optional[str] = None


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
        raise HTTPException(status_code=400, detail=f"Azure init failed: {e}")


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@router.get("/list", response_model=List[str])
async def list_files(
    connectionstring: str,
    container: str,
    prefix: Optional[str] = None,
    dependencies=[Depends(auth)]
):
    """List blobs in a container with optional prefix"""
    try:
        svc = get_service(AzureConnection(connectionstring=connectionstring, container=container))
        return svc.file_list(prefix=prefix)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/exists")
async def file_exists(
    connectionstring: str,
    container: str,
    filename: str,
    prefix: Optional[str] = None
):
    """Check if a blob exists"""
    try:
        svc = get_service(AzureConnection(connectionstring=connectionstring, container=container))
        return {"exists": svc.file_exists(filename, prefix=prefix)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload")
async def upload_file(
    connectionstring: str,
    container: str,
    destination_name: str,
    file: UploadFile,
    prefix: Optional[str] = None
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

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload failed: {e}")
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/upload-content")
async def upload_file_content(req: FileRequest):
    """Upload provided text/bytes content directly"""
    try:
        svc = get_service(req)
        data = req.content.encode("utf-8") if not req.binary else req.content
        url = svc.file_upload_content(
            local_file_content=data,
            local_file_name=req.filename,
            destination_name=req.filename,
            prefix=req.prefix,
        )
        return {"status": "success", "url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/file")
async def delete_file(req: FileRequest):
    """Delete a blob"""
    try:
        svc = get_service(req)
        ok = svc.file_delete(req.filename, prefix=req.prefix)
        return {"status": "success" if ok else "failed", "deleted": ok}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/move")
async def move_file(req: MoveRequest):
    """Move a blob (copy then delete original)"""
    try:
        svc = get_service(req)
        url = svc.file_move(
            source_name=req.source_name,
            destination_name=req.destination_name,
            source_prefix=req.source_prefix,
            destination_prefix=req.destination_prefix,
        )
        return {"status": "success", "url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bucket-exists")
async def bucket_exists(connectionstring: str, container: str):
    """Check if container exists"""
    try:
        svc = get_service(AzureConnection(connectionstring=connectionstring, container=container))
        return {"exists": svc.bucket_exists()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
