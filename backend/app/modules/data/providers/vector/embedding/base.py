"""
Base embedding interface
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import numpy as np

from ....schema_utils import VECTOR_DEFAULTS
from app.constants.embedding_models import ALLOWED_MODEL_NAMES


class EmbeddingConfig(BaseModel):
    """Configuration for embedding provider"""
    type: str = Field(default="bedrock",
                      description="Type of embedding provider")
    model_name: str = Field(default=VECTOR_DEFAULTS["embedding_model_name"],
                            description="Name of the embedding model")
    batch_size: int = Field(
        default=VECTOR_DEFAULTS["embedding_batch_size"], description="Batch size for processing texts")
    max_length: Optional[int] = Field(
        default=None, description="Maximum sequence length")
    normalize_embeddings: bool = Field(
        default=VECTOR_DEFAULTS["embedding_normalize_embeddings"], description="Whether to normalize embeddings")
    device: str = Field(
        default=VECTOR_DEFAULTS["embedding_device_type"], description="Device to run the model on")
    api_key: Optional[str] = Field(
        default=None, description="API key for external services")
    base_url: Optional[str] = Field(
        default=None, description="Base URL for API endpoints")
    model_id: Optional[str] = Field(
        default=None, description="Model ID for AWS Bedrock")
    region_name: Optional[str] = Field(
        default=None, description="AWS region for Bedrock service")

    @field_validator('model_name')
    @classmethod
    def validate_model_name(cls, v, info):
        # Only validate HuggingFace model names
        if info.data.get('type') == 'huggingface':
            if v not in ALLOWED_MODEL_NAMES:
                raise ValueError(f'model_name must be one of {ALLOWED_MODEL_NAMES}')
        return v

    @field_validator('batch_size')
    @classmethod
    def validate_batch_size(cls, v):
        if v < 1:
            raise ValueError('batch_size must be at least 1')
        return v

    @field_validator('max_length')
    @classmethod
    def validate_max_length(cls, v):
        if v is not None and v < 1:
            raise ValueError('max_length must be at least 1')
        return v

    @field_validator('device')
    @classmethod
    def validate_device(cls, v):
        allowed_devices = ['cpu', 'cuda', 'mps']
        if v not in allowed_devices:
            raise ValueError(f'device must be one of {allowed_devices}')
        return v

    def get(self):
        if self.type == "bedrock":
            from .bedrock import BedrockEmbedder
            return BedrockEmbedder(self.model_copy())
        elif self.type == "huggingface":
            from .huggingface import HuggingFaceEmbedder
            return HuggingFaceEmbedder(self.model_copy())
        elif self.type == "openai":
            from .openai import OpenAIEmbedder
            return OpenAIEmbedder(self.model_copy())
        else:
            raise ValueError(f"Invalid embedding type: {self.type}")

    class Config:
        extra = "allow"


class BaseEmbedder(ABC):
    """Base abstract class for text embedding providers"""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model = None
        self._dimension = None

    @abstractmethod
    async def get_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        raise NotImplementedError

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the embedding model"""
        raise NotImplementedError

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        raise NotImplementedError

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []

    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query (may use different prompt/processing)

        Args:
            query: Query text to embed

        Returns:
            Embedding vector
        """
        # Default implementation is the same as embed_text
        return await self.embed_text(query)

    def _normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """Normalize embeddings to unit vectors"""
        if self.config.normalize_embeddings:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
            return embeddings / norms
        return embeddings

    def _batch_texts(self, texts: List[str]) -> List[List[str]]:
        """Split texts into batches for processing"""
        batch_size = self.config.batch_size
        return [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
