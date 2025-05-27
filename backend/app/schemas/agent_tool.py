from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, Literal
from uuid import UUID

class ParameterSchema(BaseModel):
    """Schema for a tool parameter"""
    type: str
    default: Optional[Any] = None
    description: Optional[str] = None

class ApiConfig(BaseModel):
    """Configuration for API-based tools"""
    endpoint: str
    method: str
    headers: Dict[str, Any] = Field(default_factory=dict)
    query_params: Dict[str, Any] = Field(default_factory=dict)
    body: Dict[str, Any] = Field(default_factory=dict)

class FunctionConfig(BaseModel):
    """Configuration for function-based tools"""
    code: str

class ToolConfigBase(BaseModel):
    """Configuration for a tool"""
    name: str
    description: str
    type: Literal["api", "function"]
    api_config: Optional[ApiConfig] = None
    function_config: Optional[FunctionConfig] = None
    parameters_schema: Dict[str, ParameterSchema] = Field(default_factory=dict)

    model_config = ConfigDict(
            extra='allow',  # Allow extra fields for backward compatibility
            from_attributes=True # to be able to use model_validate() to map instances
            )

class ToolConfigRead(ToolConfigBase):
    """Configuration for a tool"""
    id: UUID

