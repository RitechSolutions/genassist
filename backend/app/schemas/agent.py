from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from fastapi import UploadFile

from app.schemas.operator import OperatorReadMinimal
from app.schemas.agent_security_settings import (
    AgentSecuritySettingsRead,
    AgentSecuritySettingsCreate,
    AgentSecuritySettingsUpdate,
)


class AgentBase(BaseModel):
    name: str
    description: str
    is_active: bool = False
    welcome_message: str = Field(..., max_length=500,
                                 description="Welcome message returned when starting a conversation with an agent.")
    welcome_image: Optional[bytes] = Field(None,
                                           description="Welcome image blob displayed when starting a conversation with an agent.")
    welcome_title: Optional[str] = Field(None, max_length=200,
                                         description="Welcome title displayed when starting a conversation with an agent.")
    possible_queries: list[str] = Field(...,
                                        description="Possible queries, suggested when starting a conversation with an agent.")
    thinking_phrases: Optional[list[str]] = Field(
        description="Thinking phrases, suggested when starting a conversation with an agent.", default=[])
    thinking_phrase_delay: Optional[int] = Field(None, ge=0,
                                                 description="Delay in seconds before showing thinking phrases.")
    security_settings: Optional[AgentSecuritySettingsCreate] = Field(
        None,
        description="Security settings for this agent. If null, uses global defaults."
    )
    model_config = ConfigDict(
        extra='forbid', from_attributes=True)  # shared rules
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
    security_settings: Optional[AgentSecuritySettingsUpdate] = None
    model_config = ConfigDict(extra='forbid', from_attributes=True)


class AgentRead(AgentBase):
    id: UUID
    model_config = ConfigDict(extra='ignore')  # shared rules
    user_id: Optional[UUID] = None
    operator_id: UUID
    operator: Optional[OperatorReadMinimal] = None
    workflow_id: UUID
    workflow: Optional[Dict[str, Any]] = None  # Workflow dict (from workflow.to_dict()) - needed for RegistryItem
    test_input: Optional[dict] = None
    security_settings: Optional[AgentSecuritySettingsRead] = None
    # Exclude the image blob from serialization
    welcome_image: Optional[bytes] = Field(None, exclude=True)

    @model_validator(mode='before')
    @classmethod
    def convert_workflow_to_dict(cls, data: Any) -> Any:
        """Convert SQLAlchemy WorkflowModel to dict during validation"""
        # Handle SQLAlchemy model with workflow relationship
        if hasattr(data, 'workflow') and data.workflow is not None:
            if hasattr(data.workflow, 'to_dict'):
                # It's a SQLAlchemy WorkflowModel - convert to dict
                workflow_dict = data.workflow.to_dict()
                # Need to convert SQLAlchemy model to dict for Pydantic to process
                if not isinstance(data, dict):
                    # Convert SQLAlchemy model attributes to dict
                    data_dict = {}
                    for key in dir(data):
                        if not key.startswith('_') and key not in ['metadata', 'registry']:
                            try:
                                value = getattr(data, key)
                                # Skip methods and relationships except workflow and security_settings
                                if not callable(value):
                                    data_dict[key] = value
                            except Exception:
                                pass
                    data_dict['workflow'] = workflow_dict
                    # Handle security_settings relationship
                    if hasattr(data, 'security_settings') and data.security_settings is not None:
                        data_dict['security_settings'] = data.security_settings
                    return data_dict
                else:
                    data['workflow'] = workflow_dict
        return data

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
