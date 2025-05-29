from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, Optional
from datetime import datetime

class LlmProviderBase(BaseModel):
    name: str
    llm_model_provider: str
    llm_model: str
    connection_data: Dict[str, Any] = Field(..., description="Connection parameters like api key.")
    is_active: Optional[int] = 1
    is_default: Optional[int] = 0
    model_config = ConfigDict(
        from_attributes = True
    )



class LlmProviderCreate(LlmProviderBase):
    pass


class LlmProviderRead(LlmProviderBase):
    id: UUID

    model_config = ConfigDict(
        from_attributes = True
    )


class LlmProviderUpdate(BaseModel):
    name: Optional[str] = None
    llm_model_provider: Optional[str] = None
    llm_model: Optional[str] = None
    connection_data: Optional[Dict[str, Any]] = None
    is_default: Optional[int] = None
    is_active: Optional[int] = None


class LlmAnalystBase(BaseModel):
    name: str
    llm_provider_id: UUID
    prompt: Optional[str]
    is_active: Optional[int]

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