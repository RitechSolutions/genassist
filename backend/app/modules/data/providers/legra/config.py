from pathlib import Path
from typing import Final, Optional

from pydantic import BaseModel, Field

from ...schema_utils import LEGRA_DEFAULTS

# Default SentenceTransformer model name
DEFAULT_ST_MODEL: Final[str] = "sentence-transformers/all-MiniLM-L6-v2"

# Default number of neighbors for kNN graph
DEFAULT_N_NEIGHBORS: Final[int] = 10

# Default similarity metric for NearestNeighbors
DEFAULT_METRIC: Final[str] = "cosine"

# Default community‐detection resolution parameter
DEFAULT_RESOLUTION: Final[float] = 1.0

# Path to a cache directory (for embeddings, indexes, etc.)
CACHE_DIR: Final[Path] = Path(".cache/graphrag")

# Ensure CACHE_DIR exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class LegraConfig(BaseModel):
    """Configuration for LEGRA provider"""
    enabled: bool = Field(
        default=False, description="Whether LEGRA is enabled")
    embedding_model: str = Field(
        default=LEGRA_DEFAULTS["embedding_model"], description="Embedding model name")
    cluster_resolution: float = Field(
        default=LEGRA_DEFAULTS["cluster_resolution"], description="Community detection resolution")
    generator_model_name: str = Field(
        default=LEGRA_DEFAULTS["generation_model"], description="Generator model name")
    use_gpu: bool = Field(
        default=LEGRA_DEFAULTS["generation_use_gpu"], description="Whether to use GPU acceleration")
    max_tokens: int = Field(
        default=LEGRA_DEFAULTS["generation_max_tokens"], description="Maximum tokens for generation")
    n_neighbors: int = Field(default=LEGRA_DEFAULTS["graph_n_neighbors"],
                             description="Number of neighbors for kNN graph")
    metric: str = Field(default=LEGRA_DEFAULTS["graph_distance_metric"],
                        description="Distance metric for similarity")
    min_sents: int = Field(
        default=LEGRA_DEFAULTS["chunk_min_sentences"], description="Minimum sentences per chunk")
    max_sents: int = Field(
        default=LEGRA_DEFAULTS["chunk_max_sentences"], description="Maximum sentences per chunk")
    min_sent_length: int = Field(
        default=LEGRA_DEFAULTS["chunk_min_sentence_length"], description="Minimum sentence length")
    working_dir: Optional[str] = Field(
        default=LEGRA_DEFAULTS["storage_working_directory"], description="Working directory for LEGRA data")

    def get_working_dir(self, kb_id: str) -> str:
        """Get the working directory for a specific knowledge base"""
        if self.working_dir:
            return self.working_dir
        return f"legra_data/{kb_id}"

    @staticmethod
    def from_rag_config(data: dict) -> "LegraConfig":
        if data is None or data.get("enabled", False) is False:
            return LegraConfig()

        if data.get("enabled", False) is False:
            return LegraConfig()
        return LegraConfig(**data)
