from typing import Optional, Dict, List, Literal
from uuid import UUID
from fastapi import UploadFile
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

StorageProviderType = Literal["local", "s3", "azure", "gcs", "sharepoint"]


class FileBase(BaseModel):
    name: str = Field(..., max_length=500, description="File name")
    path: str = Field(..., max_length=1000, description="File path")
    size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, max_length=255, description="MIME type")
    storage_provider: StorageProviderType = Field(default="local", description="Storage provider")
    storage_path: str = Field(..., max_length=1000, description="Path in storage provider")
    description: Optional[str] = Field(None, description="File description")
    file_metadata: Optional[Dict] = Field(default_factory=dict, description="File metadata")
    file_extension: Optional[str] = Field(None, max_length=10, description="File extension")
    tags: Optional[List[str]] = Field(default_factory=list, description="File tags")
    permissions: Optional[Dict] = Field(default_factory=dict, description="File permissions")

    model_config = ConfigDict(from_attributes=True)


class FileCreate(FileBase):
    file: UploadFile = Field(..., description="File to upload", alias="file")

class FileUpdate(FileBase):
    file: Optional[UploadFile] = Field(None, description="File to upload", alias="file")

class FileResponse(FileBase):
    id: UUID
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: int
    model_config = ConfigDict(from_attributes=True)

class FileUploadResponse(BaseModel):
    filename: str = Field(..., description="File name")
    original_filename: str = Field(..., description="Original file name")
    storage_path: str = Field(..., description="Storage path")
    file_path: str = Field(..., description="File path")
    file_url: str = Field(..., description="File URL")
    file_id: str = Field(..., description="File ID")