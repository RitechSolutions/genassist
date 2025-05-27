from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class RoleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    is_active: Optional[int] = Field(1, description="1 = active, 0 = inactive")

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    is_active: Optional[int] = Field(None)


class RoleRead(RoleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes = True
    )