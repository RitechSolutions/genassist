"""
Database Module

Provides different vector database providers for storage and retrieval.
"""

import importlib as _importlib
from typing import TYPE_CHECKING

from .base import BaseVectorDB, VectorDBConfig, SearchResult

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .chroma import ChromaVectorDB
    from .faiss import FaissVectorDB
    from .pgvector import PgVectorDB
    from .qdrant import QdrantVectorDB

# Concrete DB backends are loaded lazily (PEP 562). FaissVectorDB pulls faiss (native
# OpenMP threads — a fork hazard); the others (chroma/qdrant clients, pgvector) are
# light but loaded lazily too for uniformity. This keeps importing the package — and
# the lightweight VectorDBConfig used by vector/config.py — ML-free; backends
# materialize on first use (runtime, in a prefork child).
_LAZY = {
    "ChromaVectorDB": ".chroma",
    "FaissVectorDB": ".faiss",
    "PgVectorDB": ".pgvector",
    "QdrantVectorDB": ".qdrant",
}


def __getattr__(name):
    if name in _LAZY:
        return getattr(_importlib.import_module(_LAZY[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BaseVectorDB", "VectorDBConfig", "SearchResult", "ChromaVectorDB", "FaissVectorDB", "PgVectorDB", "QdrantVectorDB"]
