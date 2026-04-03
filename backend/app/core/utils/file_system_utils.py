import os
from pathlib import Path
from typing import Union

from fastapi import HTTPException


def get_root_directory_path():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _rebuild_canonical_under_base(base_dir: Path, final_resolved: Path) -> str:
    """
    Rebuild an absolute path string using only the resolved base and validated
    relative segments. Helps static analysis treat the result as non-tainted for
    APIs like FileResponse(path=...).
    """
    base_r = base_dir.resolve()
    final_r = final_resolved.resolve()
    rel = final_r.relative_to(base_r)
    out = base_r
    for part in rel.parts:
        out = out / part
    return str(out.resolve())


def get_safe_file_path(
    file_path: str,
    allowed_directory: Union[str, Path],
    *,
    must_exist: bool = True,
) -> str:
    """
    Sanitize and validate that a file path is within an allowed directory.
    Prevents path traversal attacks by normalizing, validating, and reconstructing the path.

    Args:
        file_path: The file path to validate (can be relative or absolute)
        allowed_directory: The directory the file must be within
        must_exist: When True, require the path to exist (404 if missing)

    Returns:
        A sanitized absolute path string that is safe to use

    Raises:
        HTTPException: If the path escapes the allowed directory or contains traversal
    """
    # Convert to Path objects for safer manipulation
    input_path = Path(file_path)
    base_dir = Path(allowed_directory).resolve()

    # Ensure base directory exists and is a directory
    if not base_dir.exists() or not base_dir.is_dir():
        raise HTTPException(
            status_code=500,
            detail="Invalid file storage directory configuration"
        )

    # If input is absolute, check if it's within base_dir
    # If input is relative, join it with base_dir
    if input_path.is_absolute():
        # Reject any absolute path that contains path traversal sequences
        # This prevents attacks like "/allowed/../etc/passwd"
        if ".." in file_path:
            raise HTTPException(
                status_code=400,
                detail="Invalid file path"
            )

        # Resolve the absolute path to normalize it
        resolved_input = input_path.resolve()

        # Verify the resolved path is within the base directory
        try:
            relative_path = resolved_input.relative_to(base_dir)
        except ValueError:
            # Path is outside the allowed directory
            raise HTTPException(
                status_code=400,
                detail="Invalid file path"
            )
    else:
        # For relative paths, normalize and check for traversal
        normalized = os.path.normpath(file_path)

        # Explicit check for path traversal sequences
        if ".." in normalized or normalized.startswith("/"):
            raise HTTPException(
                status_code=400,
                detail="Invalid file path"
            )

        # Extract only the filename and path components, preventing traversal
        # Split and filter out any empty or problematic components
        path_parts = [p for p in normalized.split(os.sep) if p and p != "."]

        # Reconstruct relative path from sanitized parts
        relative_path = Path(*path_parts)

    # Reconstruct the absolute path using only the base directory and validated relative path
    # This completely breaks the taint chain by never using user input directly
    safe_absolute_path = base_dir / relative_path

    # Final validation: ensure the resolved path is still within base_dir
    # This catches edge cases with symlinks or other filesystem tricks
    try:
        final_resolved = safe_absolute_path.resolve()
        final_relative = final_resolved.relative_to(base_dir)
    except (ValueError, RuntimeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid file path"
        )

    # Additional safety check: ensure no parent directory traversal in final path
    if ".." in str(final_relative):
        raise HTTPException(
            status_code=400,
            detail="Invalid file path"
        )

    if must_exist and not final_resolved.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    return _rebuild_canonical_under_base(base_dir, final_resolved)
