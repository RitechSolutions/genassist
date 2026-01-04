from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Standard search result format"""
    id: str = Field(description="Document/chunk identifier")
    content: str = Field(description="Text content")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Associated metadata")
    score: float = Field(default=0.0, description="Relevance score")
    source: str = Field(description="Source provider (vector, legra)")
    chunk_count: Optional[int] = Field(
        default=None, description="Number of chunks for this result")


class DataProviderInterface(BaseModel):
    """Interface definition for data providers"""
    provider_type: Literal["vector", "legra"] = Field(
        description="Type of provider")
    enabled: bool = Field(
        default=False, description="Whether provider is enabled")
    initialized: bool = Field(
        default=False, description="Whether provider is initialized")

    class Config:
        extra = "allow"
