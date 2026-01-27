from typing import Optional, Dict, List, Literal
from uuid import UUID
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
    description: Optional[str] = None
    file_metadata: Optional[Dict] = Field(default_factory=dict)
    tags: Optional[List[str]] = Field(default_factory=list)
    permissions: Optional[Dict] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class FileCreate(BaseModel):
    name: str = Field(..., max_length=500, description="File name")
    size: Optional[int] = None
    mime_type: Optional[str] = Field(None, max_length=255)
    path: Optional[str] = Field(None, max_length=1000, description="File path (auto-generated if not provided)")
    storage_path: Optional[str] = Field(None, max_length=1000, description="Path in storage provider (auto-generated if not provided)")
    storage_provider: StorageProviderType = Field(default="local")
    description: Optional[str] = None
    file_extension: Optional[str] = Field(None, max_length=10, description="File extension")
    file_metadata: Optional[Dict] = Field(default_factory=dict)
    tags: Optional[List[str]] = Field(default_factory=list)
    permissions: Optional[Dict] = Field(default_factory=dict)


class FileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=500)
    path: Optional[str] = Field(None, max_length=1000)
    size: Optional[int] = None
    mime_type: Optional[str] = Field(None, max_length=255)
    storage_provider: Optional[StorageProviderType] = None
    storage_path: Optional[str] = Field(None, max_length=1000)
    description: Optional[str] = None
    file_metadata: Optional[Dict] = None
    tags: Optional[List[str]] = None
    permissions: Optional[Dict] = None


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