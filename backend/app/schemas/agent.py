from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from fastapi import UploadFile


class AgentBase(BaseModel):
    name: str
    description: str
    is_active: bool = False
    welcome_message: str = Field(
        ...,
        max_length=500,
        description="Welcome message returned when starting a conversation with an agent.",
    )
    welcome_image: Optional[bytes] = Field(
        None,
        description="Welcome image blob displayed when starting a conversation with an agent.",
    )
    welcome_title: Optional[str] = Field(
        None,
        max_length=200,
        description="Welcome title displayed when starting a conversation with an agent.",
    )
    possible_queries: list[str] = Field(
        ...,
        description="Possible queries, suggested when starting a conversation with an agent.",
    )
    thinking_phrases: Optional[list[str]] = Field(
        description="Thinking phrases, suggested when starting a conversation with an agent.",
        default=[],
    )
    thinking_phrase_delay: Optional[int] = Field(
        None, ge=0, description="Delay in seconds before showing thinking phrases."
    )
    model_config = ConfigDict(extra="forbid", from_attributes=True)  # shared rules
    workflow_id: Optional[UUID] = None


class AgentCreate(AgentBase):
    id: Optional[UUID] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    welcome_message: Optional[str] = None
    welcome_image: Optional[bytes] = None
    welcome_title: Optional[str] = None
    possible_queries: Optional[list[str]] = None
    thinking_phrases: Optional[list[str]] = None
    thinking_phrase_delay: Optional[int] = None
    workflow_id: Optional[UUID] = None
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AgentRead(AgentBase):
    id: UUID
    model_config = ConfigDict(extra="ignore")  # shared rules
    user_id: Optional[UUID] = None
    operator_id: UUID
    workflow_id: UUID
    test_input: Optional[dict] = None
    # Exclude the image blob from serialization
    welcome_image: Optional[bytes] = Field(None, exclude=True)

    @field_validator("possible_queries", mode="before")
    @classmethod
    def deserialize_possible_queries(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return v.split(";") if v else []
        return v

    @field_validator("thinking_phrases", mode="before")
    @classmethod
    def deserialize_thinking_phrases(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return v.split(";") if v else []
        return v

    @field_validator("thinking_phrase_delay", mode="before")
    @classmethod
    def deserialize_thinking_phrase_delay(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v


class AgentImageUpload(BaseModel):
    """Schema for agent image upload"""

    image: UploadFile


class QueryRequest(BaseModel):
    query: str
    metadata: Optional[Dict[str, Any]] = None
