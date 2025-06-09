from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

class AppSettingsBase(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    is_active: int
    encrypted: int

class AppSettingsCreate(AppSettingsBase):
    pass

class AppSettingsUpdate(AppSettingsBase):
    key: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None
    encrypted: Optional[int] = None

class AppSettingsRead(AppSettingsBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
