from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ConnectionStatus


class AudioProviderBase(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    capability: Optional[str] = None
    connection_data: Optional[Dict[str, Any]] = Field(None, description="Connection parameters (e.g. api_key).")
    connection_status: Optional[ConnectionStatus] = None
    is_active: Optional[int] = 1
    is_default: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class AudioProviderMinimal(BaseModel):
    id: UUID
    name: Optional[str] = None
    provider_type: Optional[str] = None
    capability: Optional[str] = None
    is_active: Optional[int] = 1

    model_config = ConfigDict(from_attributes=True)


class AudioProviderCreate(AudioProviderBase):
    name: str
    provider_type: str
    capability: str
    connection_data: Dict[str, Any]


class AudioProviderRead(AudioProviderBase):
    id: UUID


class AudioProviderUpdate(AudioProviderBase):
    pass
