"""
Pydantic configuration models for the vector system
"""

from pydantic import BaseModel, Field

from .chunking import ChunkConfig
from .embedding import EmbeddingConfig
from .db import VectorDBConfig


class VectorConfig(BaseModel):
    """Complete vector system configuration"""
    enabled: bool = Field(
        default=False, description="Whether vector is enabled")

    chunking: ChunkConfig = Field(
        default_factory=ChunkConfig)
    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig)
    vector_db: VectorDBConfig = Field(
        default_factory=VectorDBConfig)

    class Config:
        extra = "allow"  # Allow additional fields for extensibility

    @staticmethod
    def from_rag_config(data: dict) -> "VectorConfig":
        if data is None or data.get("enabled", False) is False:
            return VectorConfig()

        if data.get("enabled", False) is False:
            return VectorConfig()

        chunking = data.get("chunking", None)
        embedding = data.get("embedding", None)
        vector_db = data.get("vector_db", None)

        return VectorConfig(
            enabled=data.get("enabled", False),
            chunking=ChunkConfig(**chunking) if chunking else ChunkConfig(),
            embedding=EmbeddingConfig(
                **embedding) if embedding else EmbeddingConfig(),
            vector_db=VectorDBConfig(
                **vector_db) if vector_db else VectorDBConfig(),
        )
