"""
Base vector database interface
"""
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from app.core.tenant_scope import get_tenant_context

from ....schema_utils import VECTOR_DEFAULTS

DEFAULT_HOST = os.getenv("CHROMA_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("CHROMA_PORT", 8005))


class VectorDBConfig(BaseModel):
    """Configuration for vector database"""
    type: str = Field(default=VECTOR_DEFAULTS["vector_db_type"], description="Type of vector database")
    collection_name: str = Field(
        default_factory=lambda: VECTOR_DEFAULTS["vector_db_collection_name"] or "default", description="Name of the vector collection")
    persist_directory: Optional[str] = Field(
        default=None, description="Directory for data persistence")
    host: Optional[str] = Field(
        default=DEFAULT_HOST, description="Database host")
    port: Optional[int] = Field(
        default=DEFAULT_PORT, description="Database port")
    distance_metric: str = Field(
        default="cosine", description="Distance metric (cosine, euclidean, dot_product)")
    index_type: str = Field(
        default="hnsw", description="Index type (hnsw, flat, ivf)")

    # HNSW specific parameters
    hnsw_m: int = Field(default=16, description="HNSW M parameter")
    hnsw_ef_construction: int = Field(
        default=200, description="HNSW ef_construction parameter")
    hnsw_ef_search: int = Field(
        default=100, description="HNSW ef_search parameter")

    # Additional database-specific parameters
    extra_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional database-specific parameters")

    @model_validator(mode='after')
    def add_tenant_prefix(self):
        """Add tenant prefix to collection name for multi-tenant isolation"""
        tenant_id = get_tenant_context()
        if tenant_id and not self.collection_name.startswith(f"tenant_{tenant_id}_"):
            self.collection_name = f"tenant_{tenant_id}_{self.collection_name}"
        return self

    @field_validator('extra_params', mode='before')
    @classmethod
    def ensure_extra_params_dict(cls, v):
        return v or {}

    @field_validator('distance_metric')
    @classmethod
    def validate_distance_metric(cls, v):
        allowed_metrics = ['cosine', 'euclidean', 'dot_product']
        if v not in allowed_metrics:
            raise ValueError(
                f'distance_metric must be one of {allowed_metrics}')
        return v

    @field_validator('index_type')
    @classmethod
    def validate_index_type(cls, v):
        allowed_types = ['hnsw', 'flat', 'ivf']
        if v not in allowed_types:
            raise ValueError(f'index_type must be one of {allowed_types}')
        return v

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if v is not None and (v < 1 or v > 65535):
            raise ValueError('port must be between 1 and 65535')
        return v

    def get(self):
        if self.type == "chroma":
            from .chroma import ChromaVectorDB
            return ChromaVectorDB(self.model_copy())
        elif self.type == "faiss":
            from .faiss import FaissVectorDB
            return FaissVectorDB(self.model_copy())
        else:
            raise ValueError(f"Invalid vector database type: {self.type}")

    class Config:
        extra = "allow"


class SearchResult(BaseModel):
    """Result from vector search"""
    id: str = Field(description="Document/chunk identifier")
    content: str = Field(description="Text content")
    metadata: Dict[str, Any] = Field(description="Associated metadata")
    score: float = Field(description="Relevance score")
    distance: Optional[float] = Field(
        default=None, description="Distance from query vector")

    @field_validator('score')
    @classmethod
    def validate_score(cls, v):
        if v < 0 or v > 1:
            raise ValueError('score must be between 0 and 1')
        return v

    @field_validator('distance')
    @classmethod
    def validate_distance(cls, v):
        if v is not None and v < 0:
            raise ValueError('distance must be non-negative')
        return v

    def __init__(self, **data):
        # Convert distance to score if not provided
        if 'distance' in data and data.get('distance') is not None and ('score' not in data or data.get('score') is None):
            distance = data['distance']
            if distance == 0:
                data['score'] = 1.0
            else:
                data['score'] = 1.0 / (1.0 + distance)
        super().__init__(**data)

    class Config:
        extra = "allow"


class BaseVectorDB(ABC):
    """Base abstract class for vector database providers"""

    def __init__(self, config: VectorDBConfig):
        self.config = config
        self.client = None
        self.collection = None

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the vector database connection"""
        raise NotImplementedError

    @abstractmethod
    async def create_collection(self, dimension: int) -> bool:
        """
        Create a new collection

        Args:
            dimension: Vector dimension

        Returns:
            Success status
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_collection(self) -> bool:
        """Delete the collection"""
        raise NotImplementedError

    @abstractmethod
    async def add_vectors(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]],
        contents: List[str]
    ) -> bool:
        """
        Add vectors to the collection

        Args:
            ids: List of document IDs
            vectors: List of embedding vectors
            metadatas: List of metadata dictionaries
            contents: List of text contents

        Returns:
            Success status
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_vectors(self, ids: List[str]) -> bool:
        """
        Delete vectors by IDs

        Args:
            ids: List of document IDs to delete

        Returns:
            Success status
        """
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        filter_dict: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        Search for similar vectors

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            filter_dict: Optional metadata filters

        Returns:
            List of search results
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """
        Get vectors by their IDs

        Args:
            ids: List of document IDs

        Returns:
            List of results
        """
        raise NotImplementedError

    @abstractmethod
    async def get_all_ids(self, filter_dict: Dict[str, Any] = None) -> List[str]:
        """
        Get all document IDs in the collection

        Args:
            filter_dict: Optional metadata filters

        Returns:
            List of document IDs
        """
        raise NotImplementedError

    @abstractmethod
    async def count(self, filter_dict: Dict[str, Any] = None) -> int:
        """
        Count documents in the collection

        Args:
            filter_dict: Optional metadata filters

        Returns:
            Document count
        """
        raise NotImplementedError

    def close(self):
        """Close the database connection"""
        # Default implementation does nothing
        # Subclasses can override if cleanup is needed
        pass
