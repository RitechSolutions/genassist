from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Dict, List, Optional, Union


class BaseLLMConfig(BaseModel):
    """Base configuration for all LLM providers"""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0)
    timeout: int = Field(default=60, gt=0)

class OpenAIConfig(BaseLLMConfig):
    """Configuration for OpenAI models"""
    api_key: str
    model: str = Field(default="gpt-3.5-turbo")
    organization: Optional[str] = None

class GeminiConfig(BaseLLMConfig):
    """Configuration for Google Gemini models"""
    api_key: str
    model: str = Field(default="gemini-pro")
    project_id: Optional[str] = None

class LocalLLMConfig(BaseLLMConfig):
    """Base configuration for locally hosted models"""
    base_url: Union[HttpUrl, str]
    api_key: Optional[str] = None
    model: str

class LlamaConfig(LocalLLMConfig):
    """Configuration for Llama models"""
    model: str = Field(default="llama-2-7b-chat")
    context_window: Optional[int] = Field(default=4096, gt=0)
    stop_sequences: Optional[List[str]] = None

class MistralConfig(LocalLLMConfig):
    """Configuration for Mistral models"""
    model: str = Field(default="mistral-7b-instruct")
    context_window: Optional[int] = Field(default=8192, gt=0)
    stop_sequences: Optional[List[str]] = None
