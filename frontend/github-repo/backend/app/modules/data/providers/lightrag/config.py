from pathlib import Path
from typing import Final, Any

from pydantic import BaseModel, Field

from ...schema_utils import LIGHTRAG_DEFAULTS


# Default embedding function name
DEFAULT_EMBEDDING_FUNC: Final[str] = "openai_embed"

# Default LLM model function name
DEFAULT_LLM_MODEL_FUNC: Final[str] = "gpt_4o_mini_complete"

# Default search mode
DEFAULT_SEARCH_MODE: Final[str] = "mix"

# Default chunk token size
DEFAULT_CHUNK_TOKEN_SIZE: Final[int] = 512

# Default chunk overlap token size
DEFAULT_CHUNK_OVERLAP_TOKEN_SIZE: Final[int] = 50

# Default vector storage type
DEFAULT_VECTOR_STORAGE: Final[str] = "ChromaVectorDBStorage"

# Default embedding batch number
DEFAULT_EMBEDDING_BATCH_NUM: Final[int] = 32

# Path to a cache directory (for embeddings, indexes, etc.)
CACHE_DIR: Final[Path] = Path(".cache/lightrag")

# Ensure CACHE_DIR exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class LightRAGConfig(BaseModel):
    """Configuration for LightRAG provider"""

    enabled: bool = Field(
        default=False, description="Whether LightRAG is enabled")

    # Core settings
    working_dir: str = Field(default=LIGHTRAG_DEFAULTS["working_directory"],
                             description="Working directory for LightRAG data")
    embedding_func_name: str = Field(
        default=LIGHTRAG_DEFAULTS["embedding_func_name"], description="Embedding function name")
    llm_model_func_name: str = Field(
        default=LIGHTRAG_DEFAULTS["llm_model_func_name"], description="LLM model function name")
    search_mode: str = Field(default=LIGHTRAG_DEFAULTS["search_mode"],
                             description="Search mode (local, global, mix)")

    # Chunking settings
    chunk_token_size: int = Field(
        default=LIGHTRAG_DEFAULTS["chunk_token_size"], description="Chunk token size")
    chunk_overlap_token_size: int = Field(
        default=LIGHTRAG_DEFAULTS["chunk_overlap_token_size"], description="Chunk overlap token size")

    # Vector storage settings
    vector_storage: str = Field(
        default=LIGHTRAG_DEFAULTS["vector_storage"], description="Vector storage type")
    log_level: str = Field(default="DEBUG", description="Log level")
    embedding_batch_num: int = Field(
        default=LIGHTRAG_DEFAULTS["embedding_batch_num"], description="Embedding batch number")

    # Vector DB storage settings
    vector_db_storage_cls_kwargs: dict[str, Any] = Field(
        default_factory=lambda: {
            "collection_settings": {
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 128,
                "hnsw:search_ef": 128,
                "hnsw:M": 16,
                "hnsw:batch_size": 100,
                "hnsw:sync_threshold": 1000,
            }
        },
        description="Vector database storage class kwargs"
    )

    # Query parameters
    top_k: int = Field(
        default=LIGHTRAG_DEFAULTS["top_k"], description="Top K results to return")
    response_type: str = Field(
        default=LIGHTRAG_DEFAULTS["response_type"], description="Response type for queries")

    class Config:
        extra = "allow"

    @staticmethod
    def from_rag_config(data: dict) -> "LightRAGConfig":
        if data is None or data.get("enabled", False) is False:
            return LightRAGConfig()

        if data.get("enabled", False) is False:
            return LightRAGConfig()
        return LightRAGConfig(**data)
