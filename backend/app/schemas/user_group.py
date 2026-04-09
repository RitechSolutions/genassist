from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class UserGroupCreate(UserGroupBase):
    pass


class UserGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class UserGroupRead(UserGroupBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)