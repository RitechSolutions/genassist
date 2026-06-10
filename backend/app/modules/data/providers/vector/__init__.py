"""
Vector Provider System

A clean, modular vector provider system that separates concerns:
- chunking: Text splitting strategies
- embedding: Text embedding providers  
- db: Vector database providers
- orchestrator: Coordinates all components based on configuration
"""

import importlib as _importlib
from typing import TYPE_CHECKING

from .config import ChunkConfig, EmbeddingConfig, VectorDBConfig, VectorConfig

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .provider import VectorProvider

# VectorProvider (the orchestrator) imports the chunking/embedding/db backends, some of
# which pull torch/sentence_transformers/faiss. Resolve it lazily (PEP 562) so importing
# this package for its lightweight config classes stays ML-free; the provider
# materializes on first use (runtime, in a prefork child).


def __getattr__(name):
    if name == "VectorProvider":
        return getattr(_importlib.import_module(".provider", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["VectorProvider", "ChunkConfig",
           "EmbeddingConfig", "VectorDBConfig", "VectorConfig"]
