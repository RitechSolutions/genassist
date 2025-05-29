from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator



class AgentBase(BaseModel):
    name: str
    description: str
    is_active: bool = False
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
    is_active: Optional[bool] = None
    welcome_message: Optional[str] = None
    possible_queries: Optional[list[str]] = None

class AgentRead(AgentBase):
    id: UUID
    model_config = ConfigDict(extra='ignore')  # shared rules
    user_id: Optional[UUID] = None
    operator_id: UUID
    workflow_id: UUID

    @field_validator("possible_queries", mode="before")
    def deserialize_possible_queries(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return v.split(";") if v else []
        return v

class QueryRequest(BaseModel):
    query: str
    metadata: Optional[Dict[str, Any]] = None
