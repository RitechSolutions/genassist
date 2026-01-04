from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID

class FeatureFlagBase(BaseModel):
    key: str
    val: str
    description: Optional[str] = None
    is_active: int

class FeatureFlagCreate(FeatureFlagBase):
    pass

class FeatureFlagUpdate(BaseModel):
    key: Optional[str] = None
    val: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None

class FeatureFlagRead(FeatureFlagBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
