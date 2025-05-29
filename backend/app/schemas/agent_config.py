from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, List, Optional

class AgentConfig(BaseModel):
    """Agent configuration model"""
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    knowledge_base_ids: List[str] = Field(default_factory=list)
    tool_ids: List[str] = Field(default_factory=list)
    system_prompt: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = False

    model_config = ConfigDict(
            extra='allow'  # Allow extra fields for backward compatibility
            )
