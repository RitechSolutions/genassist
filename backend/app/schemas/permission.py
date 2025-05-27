from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID



class PermissionBase(BaseModel):
    """
    Shared fields for creation and update.
    """
    name: str = Field(..., min_length=1, max_length=255, description="Permission name, e.g. GET:api_keys.")
    description: str = Field(..., min_length=1, max_length=255, description="Permission description")
    is_active: int = Field(1, description="Is the permission active (0/1)?")

class PermissionCreate(PermissionBase):
    """
    Fields required for creating a new Permission.
    (No extra fields here, but could be extended.)
    """
    pass

class PermissionUpdate(PermissionBase):
    """
    Fields allowed for updating an existing Permission.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[int] = None
    description: Optional[str] = Field(None, min_length=1, max_length=255)

class PermissionRead(PermissionBase):
    """
    Fields returned in GET operations.
    """
    id: UUID
    created_at: Optional[datetime] = None
    is_active: Optional[int] = None
    updated_at: Optional[datetime] = None
    description: Optional[str] = None

    model_config = ConfigDict(
        from_attributes = True
    )
