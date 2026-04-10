import json
from typing import Optional, Dict, List, Literal, Any
from uuid import UUID
from fastapi import Form, UploadFile
from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime

StorageProviderType = Literal["local", "s3", "azure", "gcs", "sharepoint"]


def _parse_form_json_dict(raw: Optional[str]) -> Dict[str, Any]:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_form_json_list_str(raw: Optional[str]) -> List[str]:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


class FileBase(BaseModel):
    name: str = Field(..., max_length=500, description="File name")
    path: str = Field(..., max_length=1000, description="File path")
    storage_path: str = Field(..., max_length=1000, description="Path in storage provider")
    storage_provider: StorageProviderType = Field(default="local", description="Storage provider")
    original_filename: Optional[str] = Field(None, max_length=500, description="Original file name")
    size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, max_length=255, description="MIME type")
    description: Optional[str] = Field(None, description="File description")
    file_metadata: Optional[Dict] = Field(default_factory=dict, description="File metadata")
    file_extension: Optional[str] = Field(None, max_length=10, description="File extension")
    tags: Optional[List[str]] = Field(default_factory=list, description="File tags")
    permissions: Optional[Dict] = Field(default_factory=dict, description="File permissions")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _coerce_multipart_json_fields(cls, data: Any) -> Any:
        """Multipart form sends tags / file_metadata / permissions as JSON strings."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if isinstance(out.get("file_metadata"), str):
            out["file_metadata"] = _parse_form_json_dict(out["file_metadata"])
        if isinstance(out.get("tags"), str):
            out["tags"] = _parse_form_json_list_str(out["tags"])
        if isinstance(out.get("permissions"), str):
            out["permissions"] = _parse_form_json_dict(out["permissions"])
        return out

    @classmethod
    def as_form(
        cls,
        name: str = Form(...),
        path: str = Form(...),
        storage_provider: StorageProviderType = Form("local"),
        storage_path: str = Form(...),
        original_filename: Optional[str] = Form(None),
        size: Optional[int] = Form(None),
        mime_type: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        file_metadata: Optional[str] = Form(None),  # or JSON → str, then parse
        file_extension: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),           # e.g. JSON string, then parse
        permissions: Optional[str] = Form(None),    # same
    ) -> "FileBase":
        return cls(
            name=name,
            original_filename=original_filename,
            path=path,
            storage_path=storage_path,
            storage_provider=storage_provider,
            size=size,
            mime_type=mime_type,
            description=description,
            file_metadata=_parse_form_json_dict(file_metadata),
            file_extension=file_extension,
            tags=_parse_form_json_list_str(tags),
            permissions=_parse_form_json_dict(permissions),
        )

class FileResponse(FileBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: int
    model_config = ConfigDict(from_attributes=True)

class FileUploadResponse(BaseModel):
    original_filename: str = Field(..., description="Original file name")
    file_path: Optional[str] = Field(None, description="File path")
    storage_path: Optional[str] = Field(None, description="Storage path")
    filename: Optional[str] = Field(None, description="File name")
    file_url: Optional[str] = Field(None, description="File URL")
    file_id: Optional[str] = Field(None, description="File ID")