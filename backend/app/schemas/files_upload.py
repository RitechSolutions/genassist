"""Schemas for chunked (file-manager) upload sessions."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class FilesUploadSessionCreate(BaseModel):
    original_filename: str = Field(..., min_length=1, max_length=500)
    expected_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional declared total size in bytes for validation on complete",
    )
    content_type: Optional[str] = Field(default=None, max_length=255)


class FilesUploadSessionCreateResponse(BaseModel):
    session_id: str
    max_chunk_bytes: int = Field(description="Maximum bytes accepted per /chunk request")


class FilesUploadSessionStatusResponse(BaseModel):
    id: str
    status: str
    bytes_received: int
    expected_bytes: Optional[int] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

