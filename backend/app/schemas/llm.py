from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ConnectionStatus


class LlmProviderBase(BaseModel):
    name: Optional[str] = None
    llm_model_provider: Optional[str] = None
    llm_model: Optional[str] = None
    connection_data: Optional[Dict[str, Any]] = Field(None, description="Connection parameters like api key.")
    connection_status: Optional[ConnectionStatus] = None
    is_active: Optional[int] = 1
    is_default: Optional[int] = 0
    model_config = ConfigDict(
        from_attributes = True
    )



class LlmProviderCreate(LlmProviderBase):
    name: str
    llm_model_provider: str
    llm_model: str
    connection_data: Dict[str, Any]


class LlmProviderRead(LlmProviderBase):
    id: UUID


class LlmProviderUpdate(LlmProviderBase):
    pass


class LlmAnalystBase(BaseModel):
    name: str
    llm_provider_id: UUID
    prompt: Optional[str]
    is_active: Optional[int]
    context_enrichments: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        from_attributes = True
    )


class LlmAnalystCreate(LlmAnalystBase):
    pass


class LlmAnalyst(LlmAnalystBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    llm_provider: Optional[LlmProviderRead] = None

    model_config = ConfigDict(
        from_attributes = True
    )



class LlmAnalystUpdate(BaseModel):
    name: Optional[str] = None
    llm_provider_id: Optional[UUID] = None
    prompt: Optional[str] = None
    is_active: Optional[int] = None
    context_enrichments: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None
