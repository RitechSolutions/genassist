from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Dict, Any, Literal
from uuid import UUID
from datetime import datetime

AppSettingsType = Literal[
    "Zendesk", "WhatsApp", "Gmail", "Microsoft", "Slack", "Jira", "Other"
]


class AppSettingsBase(BaseModel):
    name: str
    type: AppSettingsType
    values: Dict[str, Any]
    description: Optional[str] = None
    is_active: int

    @field_validator("values")
    @classmethod
    def validate_values_not_empty(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v or len(v) == 0:
            raise ValueError("values cannot be empty")
        return v

    @field_validator("is_active")
    @classmethod
    def validate_is_active(cls, v: int) -> int:
        if v not in [0, 1]:
            raise ValueError("is_active must be 0 or 1")
        return v


class AppSettingsCreate(AppSettingsBase):
    pass


class AppSettingsUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[AppSettingsType] = None
    values: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


class AppSettingsRead(AppSettingsBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
