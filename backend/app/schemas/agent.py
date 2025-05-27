from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator


class AgentBase(BaseModel):
    name: str
    description: str
    llm_provider_id: Optional[UUID] = None
    tool_ids: List[UUID] = Field(default_factory=list)
    knowledge_base_ids: List[UUID] = Field(default_factory=list)
    system_prompt: str
    settings: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = False
    email: EmailStr = Field(...,
                            description="Email address, since user tables requires one..")
    welcome_message: str = Field(..., max_length=500,
                                 description="Welcome message returned when starting a conversation with an agent.")
    possible_queries: list[str] = Field(...,
                                  description="Possible queries, suggested when starting a conversation with an agent.")

    model_config = ConfigDict(extra='forbid', from_attributes=True)  # shared rules


class AgentCreate(AgentBase):
    pass


class AgentUpdate(AgentBase):
    name: Optional[str] = None
    description: Optional[str] = None
    llm_provider_id: Optional[UUID] = None
    tool_ids: Optional[List[UUID]] = None
    knowledge_base_ids: Optional[List[UUID]] = None
    system_prompt: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    welcome_message: Optional[str] = None
    possible_queries: Optional[list[str]] = None
    email: Optional[EmailStr] = Field(None, exclude=True)


class AgentRead(AgentBase):
    id: UUID
    model_config = ConfigDict(extra='ignore')  # shared rules
    email: EmailStr = Field(None, exclude=True)
    user_id: Optional[UUID] = None
    operator_id: UUID

    @field_validator("possible_queries", mode="before")
    def deserialize_possible_queries(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return v.split(";") if v else []
        return v

class QueryRequest(BaseModel):
    query: str
