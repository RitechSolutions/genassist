"""
Configuration schemas for the data module service
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from .providers import VectorConfig, LegraConfig, LightRAGConfig
from .providers.vector import ChunkConfig, EmbeddingConfig, VectorDBConfig
from .schema_utils import get_schema_default


class AgentRAGConfig(BaseModel):
    """Complete configuration for the data service"""
    knowledge_base_id: str = Field(description="Knowledge base identifier")
    vector_config: Optional[VectorConfig] = Field(
        default=None, description="Vector system configuration")
    legra_config: Optional[LegraConfig] = Field(
        default=None, description="LEGRA system configuration")
    lightrag_config: Optional[LightRAGConfig] = Field(
        default=None, description="LightRAG system configuration")

    class Config:
        extra = "allow"  # Allow additional fields for extensibility

    def get_vector_config(self) -> Optional[VectorConfig]:
        """Get vector configuration with defaults applied"""
        if self.vector_config is None:
            return None
        if not self.vector_config.enabled:
            return None

        return self.vector_config

    def get_legra_config(self) -> Optional[LegraConfig]:
        """Get LEGRA configuration with defaults applied"""
        if self.legra_config is None:
            return None
        if not self.legra_config.enabled:
            return None

        return self.legra_config

    def get_lightrag_config(self) -> Optional[LightRAGConfig]:
        """Get LightRAG configuration with defaults applied"""
        if self.lightrag_config is None:
            return None
        if not self.lightrag_config.enabled:
            return None

        return self.lightrag_config


class KbRAGConfig(BaseModel):
    """Configuration for Knowledge Base RAG systems based on form schema"""
    enabled: bool = Field(default=False, description="Whether RAG is enabled")
    # Vector configuration
    vector: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Vector database configuration"
    )

    # LEGRA configuration
    legra: Optional[Dict[str, Any]] = Field(
        default=None,
        description="LEGRA system configuration"
    )

    # LightRAG configuration
    lightrag: Optional[Dict[str, Any]] = Field(
        default=None,
        description="LightRAG system configuration"
    )

    class Config:
        extra = "allow"  # Allow additional fields for extensibility

    def get_vector_config(self) -> Optional[VectorConfig]:
        """Convert vector dict to VectorConfig object"""
        if not self.vector or not self.vector.get("enabled", False):
            return None

        # Map the flat structure to nested VectorConfig
        vector_data = self.vector.copy()

        # Extract chunking config with schema defaults
        chunking_data = {
            "chunk_size": vector_data.get("chunk_size", get_schema_default("vector", "chunk_size", 1000)),
            "chunk_overlap": vector_data.get("chunk_overlap", get_schema_default("vector", "chunk_overlap", 200)),
            "type": vector_data.get("chunk_strategy", get_schema_default("vector", "chunk_strategy", "recursive")),
            "separators": vector_data.get("chunk_separators", get_schema_default("vector", "chunk_separators", "")),
            "keep_separator": vector_data.get("chunk_keep_separator", get_schema_default("vector", "chunk_keep_separator", True)),
            "strip_whitespace": vector_data.get("chunk_strip_whitespace", get_schema_default("vector", "chunk_strip_whitespace", True))
        }

        # Extract embedding config with schema defaults
        embedding_data = {
            "model_name": vector_data.get("embedding_model_name", get_schema_default("vector", "embedding_model_name", "all-MiniLM-L6-v2")),
            "device": vector_data.get("embedding_device_type", get_schema_default("vector", "embedding_device_type", "cpu")),
            "batch_size": vector_data.get("embedding_batch_size", get_schema_default("vector", "embedding_batch_size", 32)),
            "normalize_embeddings": vector_data.get("embedding_normalize_embeddings", get_schema_default("vector", "embedding_normalize_embeddings", True))
        }

        # Extract vector_db config with schema defaults
        vector_db_data = {
            "type": vector_data.get("vector_db_type", get_schema_default("vector", "vector_db_type", "chroma")),
            "collection_name": vector_data.get("vector_db_collection_name", get_schema_default("vector", "vector_db_collection_name", ""))
        }

        return VectorConfig(
            enabled=True,
            chunking=ChunkConfig(**chunking_data),
            embedding=EmbeddingConfig(**embedding_data),
            vector_db=VectorDBConfig(**vector_db_data)
        )

    def get_legra_config(self) -> Optional[LegraConfig]:
        """Convert legra dict to LegraConfig object"""
        if not self.legra or not self.legra.get("enabled", False):
            return None

        legra_data = self.legra.copy()

        # Map the flat structure to LegraConfig fields with schema defaults
        return LegraConfig(
            enabled=True,
            embedding_model=legra_data.get(
                "embedding_model", get_schema_default("legra", "embedding_model", "sentence-transformers/all-MiniLM-L6-v2")),
            cluster_resolution=legra_data.get(
                "cluster_resolution", get_schema_default("legra", "cluster_resolution", 0.5)),
            generator_model_name=legra_data.get(
                "generation_model", get_schema_default("legra", "generation_model", "gpt2")),
            use_gpu=legra_data.get("generation_use_gpu", get_schema_default(
                "legra", "generation_use_gpu", False)),
            max_tokens=legra_data.get("generation_max_tokens", get_schema_default(
                "legra", "generation_max_tokens", 1024)),
            n_neighbors=legra_data.get("graph_n_neighbors", get_schema_default(
                "legra", "graph_n_neighbors", 10)),
            metric=legra_data.get("graph_distance_metric", get_schema_default(
                "legra", "graph_distance_metric", "cosine")),
            min_sents=legra_data.get("chunk_min_sentences", get_schema_default(
                "legra", "chunk_min_sentences", 1)),
            max_sents=legra_data.get("chunk_max_sentences", get_schema_default(
                "legra", "chunk_max_sentences", 30)),
            min_sent_length=legra_data.get("chunk_min_sentence_length", get_schema_default(
                "legra", "chunk_min_sentence_length", 32)),
            working_dir=legra_data.get("storage_working_directory", get_schema_default(
                "legra", "storage_working_directory", None))
        )

    def get_lightrag_config(self) -> Optional[LightRAGConfig]:
        """Convert lightrag dict to LightRAGConfig object"""
        if not self.lightrag or not self.lightrag.get("enabled", False):
            return None

        lightrag_data = self.lightrag.copy()

        # Map the flat structure to LightRAGConfig fields with schema defaults
        return LightRAGConfig(
            enabled=True,
            working_dir=lightrag_data.get(
                "working_directory", get_schema_default("lightrag", "working_directory", "lightrag_data")),
            embedding_func_name=lightrag_data.get(
                "embedding_func_name", get_schema_default("lightrag", "embedding_func_name", "openai_embed")),
            llm_model_func_name=lightrag_data.get(
                "llm_model_func_name", get_schema_default("lightrag", "llm_model_func_name", "gpt_4o_mini_complete")),
            search_mode=lightrag_data.get(
                "search_mode", get_schema_default("lightrag", "search_mode", "mix")),
            chunk_token_size=lightrag_data.get(
                "chunk_token_size", get_schema_default("lightrag", "chunk_token_size", 512)),
            chunk_overlap_token_size=lightrag_data.get(
                "chunk_overlap_token_size", get_schema_default("lightrag", "chunk_overlap_token_size", 50)),
            vector_storage=lightrag_data.get(
                "vector_storage", get_schema_default("lightrag", "vector_storage", "ChromaVectorDBStorage")),
            embedding_batch_num=lightrag_data.get(
                "embedding_batch_num", get_schema_default("lightrag", "embedding_batch_num", 32)),
            top_k=lightrag_data.get(
                "top_k", get_schema_default("lightrag", "top_k", 5)),
            response_type=lightrag_data.get(
                "response_type", get_schema_default("lightrag", "response_type", "Single Paragraph"))
        )
