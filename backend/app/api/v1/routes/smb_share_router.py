import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Union
from pydantic import BaseModel

from app.auth.dependencies import auth
from app.core.project_path import DATA_VOLUME
from app.services.smb_share_service import SMBShareFSService
from app.tasks.share_folder_tasks import transcribe_audio_files_async_with_scope

# Allowed root directories for local filesystem mode.
# local_root must resolve to a path under one of these.
_ALLOWED_LOCAL_ROOTS: list[Path] = [
    DATA_VOLUME.resolve(),
]


def _validate_local_root(local_root: Optional[str]) -> Optional[str]:
    """Validate that local_root is under an allowed directory.

    Returns the value unchanged when valid, or raises HTTPException 400.
    When local_root is None (SMB mode), it is passed through unchanged.
    """
    if local_root is None:
        return None

    try:
        resolved = Path(local_root).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid local_root path")

    for allowed in _ALLOWED_LOCAL_ROOTS:
        try:
            resolved.relative_to(allowed)
            return local_root
        except ValueError:
            continue

    raise HTTPException(
        status_code=400,
        detail="local_root must be within the allowed data directory",
    )


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

@router.get("/list", response_model=List[str], dependencies=[Depends(auth)])
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
):
    """List directory contents with optional filters."""
    safe_local_root = _validate_local_root(local_root)
    safe_subpath = get_safe_path(subpath)
    try:
        async with SMBShareFSService(
            smb_host=smb_host,
            smb_share=smb_share,
            smb_user=smb_user,
            smb_pass=smb_pass,
            smb_port=smb_port,
            use_local_fs=use_local_fs,
            local_root=safe_local_root,
        ) as svc:
            return await svc.list_dir(
                subpath=safe_subpath,
                only_files=only_files,
                only_dirs=only_dirs,
                extension=extension,
                name_contains=name_contains,
                pattern=pattern,
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/read", dependencies=[Depends(auth)])
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
):
    """Read file content."""
    safe_local_root = _validate_local_root(local_root)
    safe_filepath = get_safe_path(filepath)

    try:
        async with SMBShareFSService(
            smb_host=smb_host,
            smb_share=smb_share,
            smb_user=smb_user,
            smb_pass=smb_pass,
            smb_port=smb_port,
            use_local_fs=use_local_fs,
            local_root=safe_local_root,
        ) as svc:
            return await svc.read_file(safe_filepath, binary=binary)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/write", dependencies=[Depends(auth)])
async def write_file(req: FileRequest):
    """Write or update a file."""
    safe_local_root = _validate_local_root(req.local_root)
    safe_filepath = get_safe_path(req.filepath)

    try:
        async with SMBShareFSService(
            smb_host=req.smb_host,
            smb_share=req.smb_share,
            smb_user=req.smb_user,
            smb_pass=req.smb_pass,
            smb_port=req.smb_port,
            use_local_fs=req.use_local_fs,
            local_root=safe_local_root,
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


@router.delete("/file", dependencies=[Depends(auth)])
async def delete_file(req: FileRequest):
    """Delete a file."""
    safe_local_root = _validate_local_root(req.local_root)
    safe_filepath = get_safe_path(req.filepath)

    try:
        async with SMBShareFSService(
            smb_host=req.smb_host,
            smb_share=req.smb_share,
            smb_user=req.smb_user,
            smb_pass=req.smb_pass,
            smb_port=req.smb_port,
            use_local_fs=req.use_local_fs,
            local_root=safe_local_root,
        ) as svc:
            await svc.delete_file(safe_filepath)
        return {"status": "success", "message": f"File '{safe_filepath}' deleted."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/folder", dependencies=[Depends(auth)])
async def create_folder(req: FolderRequest):
    """Create a new folder (recursively)."""
    safe_local_root = _validate_local_root(req.local_root)
    safe_folderpath = get_safe_path(req.folderpath)

    try:
        async with SMBShareFSService(
            smb_host=req.smb_host,
            smb_share=req.smb_share,
            smb_user=req.smb_user,
            smb_pass=req.smb_pass,
            smb_port=req.smb_port,
            use_local_fs=req.use_local_fs,
            local_root=safe_local_root,
        ) as svc:
            await svc.create_folder(safe_folderpath)
        return {"status": "success", "message": f"Folder '{safe_folderpath}' created."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/folder", dependencies=[Depends(auth)])
async def delete_folder(req: FolderRequest):
    """Delete a folder and its contents."""
    safe_local_root = _validate_local_root(req.local_root)
    safe_folderpath = get_safe_path(req.folderpath)

    try:
        async with SMBShareFSService(
            smb_host=req.smb_host,
            smb_share=req.smb_share,
            smb_user=req.smb_user,
            smb_pass=req.smb_pass,
            smb_port=req.smb_port,
            use_local_fs=req.use_local_fs,
            local_root=safe_local_root,
        ) as svc:
            await svc.delete_folder(safe_folderpath)
        return {"status": "success", "message": f"Folder '{safe_folderpath}' deleted."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/exists", dependencies=[Depends(auth)])
async def exists(
    smb_host: Optional[str] = None,
    smb_share: Optional[str] = None,
    smb_user: Optional[str] = None,
    smb_pass: Optional[str] = None,
    smb_port: Optional[int] = None,
    use_local_fs: bool = False,
    local_root: Optional[str] = None,
    path: str = ""
):
    """Check if a path exists."""
    safe_local_root = _validate_local_root(local_root)
    safe_path = get_safe_path(path)

    try:
        async with SMBShareFSService(
            smb_host=smb_host,
            smb_share=smb_share,
            smb_user=smb_user,
            smb_pass=smb_pass,
            smb_port=smb_port,
            use_local_fs=use_local_fs,
            local_root=safe_local_root,
        ) as svc:
            return {"exists": await svc.exists(safe_path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/execute-celery-jobs")
async def execute_celery_jobs():
    await transcribe_audio_files_async_with_scope()
