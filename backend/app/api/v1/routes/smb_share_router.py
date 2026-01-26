import os
import re
from fastapi import APIRouter, Query, Depends, UploadFile, HTTPException
from typing import Optional, List, Union
from pydantic import BaseModel
from app.auth.dependencies import auth, permissions

from app.services.smb_share_service import SMBShareFSService
from app.tasks.share_folder_tasks import transcribe_audio_files_async_with_scope


def get_safe_path(user_path: str) -> str:
    """
    Sanitize and validate a user-provided path to prevent path traversal attacks.

    Args:
        user_path: The user-provided path to validate

    Returns:
        A sanitized path string that is safe to use

    Raises:
        HTTPException: If path contains traversal sequences
    """
    if not user_path:
        return ""

    # Normalize the path to resolve any . or .. components
    normalized = os.path.normpath(user_path)

    # After normalization, check if it still contains parent directory references
    # or starts with absolute path indicators
    if ".." in normalized:
        raise HTTPException(
            status_code=400,
            detail="Invalid path: path traversal not allowed"
        )

    # Reject absolute paths - all paths should be relative to root
    if os.path.isabs(normalized) or normalized.startswith("/") or normalized.startswith("\\"):
        raise HTTPException(
            status_code=400,
            detail="Invalid path: absolute paths not allowed"
        )

    # Check for URL-encoded traversal attempts
    user_path_lower = user_path.lower()
    if "%2e" in user_path_lower or "%252e" in user_path_lower:
        raise HTTPException(
            status_code=400,
            detail="Invalid path: encoded traversal not allowed"
        )

    return normalized

router = APIRouter()
router = APIRouter(prefix="/smb", tags=["SMB Share / Local FS"])


# -----------------------------------------------------------------------------
# Pydantic models for requests
# -----------------------------------------------------------------------------
class SMBConnection(BaseModel):
    smb_host: Optional[str] = None
    smb_share: Optional[str] = None
    smb_user: Optional[str] = None
    smb_pass: Optional[str] = None
    smb_port: Optional[int] = 445
    use_local_fs: bool = False
    local_root: Optional[str] = None


class PathRequest(SMBConnection):
    subpath: Optional[str] = ""


class FileRequest(PathRequest):
    filepath: str
    content: Optional[Union[str, bytes]] = None
    binary: Optional[bool] = False
    overwrite: Optional[bool] = True


class FolderRequest(PathRequest):
    folderpath: str


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@router.get("/list", response_model=List[str])
async def list_dir(
    smb_host: Optional[str] = None,
    smb_share: Optional[str] = None,
    smb_user: Optional[str] = None,
    smb_pass: Optional[str] = None,
    smb_port: Optional[int] = None,
    use_local_fs: bool = False,
    local_root: Optional[str] = None,
    subpath: str = "",
    only_files: bool = False,
    only_dirs: bool = False,
    extension: Optional[str] = None,
    name_contains: Optional[str] = None,
    pattern: Optional[str] = None,
    dependencies=[Depends(auth)]
):
    """List directory contents with optional filters."""
    try:
        async with SMBShareFSService(
            smb_host=smb_host,
            smb_share=smb_share,
            smb_user=smb_user,
            smb_pass=smb_pass,
            smb_port=smb_port,
            use_local_fs=use_local_fs,
            local_root=local_root,
        ) as svc:
            return await svc.list_dir(
                subpath=subpath,
                only_files=only_files,
                only_dirs=only_dirs,
                extension=extension,
                name_contains=name_contains,
                pattern=pattern,
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/read")
async def read_file(
    smb_host: Optional[str] = None,
    smb_share: Optional[str] = None,
    smb_user: Optional[str] = None,
    smb_pass: Optional[str] = None,
    smb_port: Optional[int] = None,
    use_local_fs: bool = False,
    local_root: Optional[str] = None,
    filepath: str = "",
    binary: bool = False,
    dependencies=[Depends(auth)]
):
    """Read file content."""
    # Sanitize filepath to prevent path traversal attacks
    safe_filepath = get_safe_path(filepath)

    try:
        async with SMBShareFSService(
            smb_host=smb_host,
            smb_share=smb_share,
            smb_user=smb_user,
            smb_pass=smb_pass,
            smb_port=smb_port,
            use_local_fs=use_local_fs,
            local_root=local_root,
        ) as svc:
            return await svc.read_file(safe_filepath, binary=binary)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/write")
async def write_file(req: FileRequest, dependencies=[Depends(auth)]):
    """Write or update a file."""
    # Sanitize filepath to prevent path traversal attacks
    safe_filepath = get_safe_path(req.filepath)

    try:
        async with SMBShareFSService(
            smb_host=req.smb_host,
            smb_share=req.smb_share,
            smb_user=req.smb_user,
            smb_pass=req.smb_pass,
            smb_port=req.smb_port,
            use_local_fs=req.use_local_fs,
            local_root=req.local_root,
        ) as svc:
            await svc.write_file(
                filepath=safe_filepath,
                content=req.content or "",
                binary=req.binary,
                overwrite=req.overwrite,
            )
        return {"status": "success", "message": f"File '{safe_filepath}' written."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/file")
async def delete_file(req: FileRequest, dependencies=[Depends(auth)]):
    """Delete a file."""
    try:
        async with SMBShareFSService(
            smb_host=req.smb_host,
            smb_share=req.smb_share,
            smb_user=req.smb_user,
            smb_pass=req.smb_pass,
            smb_port=req.smb_port,
            use_local_fs=req.use_local_fs,
            local_root=req.local_root, 
        ) as svc:
            await svc.delete_file(req.filepath)
        return {"status": "success", "message": f"File '{req.filepath}' deleted."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/folder")
async def create_folder(req: FolderRequest, dependencies=[Depends(auth)]):
    """Create a new folder (recursively)."""
    try:
        async with SMBShareFSService(
            smb_host=req.smb_host,
            smb_share=req.smb_share,
            smb_user=req.smb_user,
            smb_pass=req.smb_pass,
            smb_port=req.smb_port,
            use_local_fs=req.use_local_fs,
            local_root=req.local_root, 
        ) as svc:
            await svc.create_folder(req.folderpath)
        return {"status": "success", "message": f"Folder '{req.folderpath}' created."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/folder")
async def delete_folder(req: FolderRequest, dependencies=[Depends(auth)]):
    """Delete a folder and its contents."""
    # Sanitize folderpath to prevent path traversal attacks
    safe_folderpath = get_safe_path(req.folderpath)

    try:
        async with SMBShareFSService(
            smb_host=req.smb_host,
            smb_share=req.smb_share,
            smb_user=req.smb_user,
            smb_pass=req.smb_pass,
            smb_port=req.smb_port,
            use_local_fs=req.use_local_fs,
            local_root=req.local_root,
        ) as svc:
            await svc.delete_folder(safe_folderpath)
        return {"status": "success", "message": f"Folder '{safe_folderpath}' deleted."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/exists")
async def exists(
    smb_host: Optional[str] = None,
    smb_share: Optional[str] = None,
    smb_user: Optional[str] = None,
    smb_pass: Optional[str] = None,
    smb_port: Optional[int] = None,
    use_local_fs: bool = False,
    local_root: Optional[str] = None,
    path: str = "",
    dependencies=[Depends(auth)]
):
    """Check if a path exists."""
    try:
        async with SMBShareFSService(
            smb_host=smb_host,
            smb_share=smb_share,
            smb_user=smb_user,
            smb_pass=smb_pass,
            smb_port=smb_port,
            use_local_fs=use_local_fs,
            local_root=local_root, 
        ) as svc:
            return {"exists": await svc.exists(path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/execute-celery-jobs")
async def execute_celery_jobs():
    await transcribe_audio_files_async_with_scope()
