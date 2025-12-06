from pathlib import Path
from typing import Final

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
