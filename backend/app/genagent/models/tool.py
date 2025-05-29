from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal

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

class ToolConfig(BaseModel):
    """Configuration for a tool"""
    id: str
    name: str
    description: str
    type: Literal["api", "function"]
    api_config: Optional[ApiConfig] = None
    function_config: Optional[FunctionConfig] = None
    parameters_schema: Dict[str, ParameterSchema] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"  # Allow extra fields for backward compatibility 