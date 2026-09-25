from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


class RolePermissionBase(BaseModel):
    role_id: UUID = Field(..., description="ID of the Role")
    permission_id: UUID = Field(..., description="ID of the Permission")

class RolePermissionCreate(RolePermissionBase):
    """
    Fields needed to create a RolePermission object.
    """
    pass

class RolePermissionUpdate(BaseModel):
    """
    Fields allowed when updating a RolePermission entry.
    In a typical join table, you might only allow toggling an 'is_active' field,
    or you might not allow updates at all.
    """
    role_id: Optional[UUID] = None
    permission_id: Optional[UUID] = None

class RolePermissionRead(RolePermissionBase):
    """
    Pydantic model used when reading back a RolePermission row.
    """
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes = True
    )
