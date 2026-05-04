"""Schemas for the direct browser -> S3 presigned PUT upload flow.

This is the request/response surface for the opt-in direct upload endpoints:

- ``POST /file-manager/upload-session/presign``
- ``POST /file-manager/upload-session/{session_id}/finalize``

The legacy chunked-session endpoints in ``files_upload.py`` continue to work
unchanged when the feature flag is disabled.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class PresignDirectUploadCreate(BaseModel):
    """Body for ``POST /file-manager/upload-session/presign``."""

    original_filename: str = Field(..., min_length=1, max_length=500)
    expected_size: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Optional declared total size in bytes. The server will validate the actual "
            "size on finalize via S3 HEAD and reject mismatches."
        ),
    )
    content_type: Optional[str] = Field(default=None, max_length=255)


class PresignDirectUploadResponse(BaseModel):
    """Response for ``POST /file-manager/upload-session/presign``.

    The frontend should:
    1. Issue ``method`` (``PUT``) to ``presigned_url`` with the file body and the
       headers in ``required_headers``.
    2. Then call ``POST /file-manager/upload-session/{session_id}/finalize``.
    """

    session_id: str
    file_id: str = Field(description="UUID of the pre-created files row (status pending)")
    object_key: str = Field(description="S3 object key the URL was signed for")
    presigned_url: str
    method: str = Field(default="PUT")
    required_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Headers the client MUST send on the PUT request to satisfy the signature",
    )
    expires_in: int = Field(description="Lifetime of the presigned URL in seconds")

    model_config = ConfigDict(from_attributes=True)


class FinalizeDirectUploadRequest(BaseModel):
    """Body for ``POST /file-manager/upload-session/{session_id}/finalize``."""

    success: bool = Field(
        description=(
            "True if the client successfully PUT the bytes to S3, False if the upload "
            "errored client-side and the server should clean up the pending record."
        )
    )
    etag: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional ETag returned by S3 on successful PUT (for client-side audit logs).",
    )
    error_message: Optional[str] = Field(default=None, max_length=2000)


class FinalizeDirectUploadResponse(BaseModel):
    """Response for ``POST /file-manager/upload-session/{session_id}/finalize``.

    Mirrors the dict shape returned by the legacy chunked ``/complete`` endpoint
    (UploadFileResponse-compatible) so the frontend can treat both flows uniformly.
    """

    file_id: str
    filename: str
    original_filename: str
    file_type: str = Field(default="url")
    file_url: Optional[str] = None
    file_path: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
