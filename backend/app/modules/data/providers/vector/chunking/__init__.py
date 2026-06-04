"""
Chunking Module

Provides different text chunking strategies for document processing.
"""

import importlib as _importlib
from typing import TYPE_CHECKING

from .base import BaseChunker, ChunkConfig

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .recursive import RecursiveChunker
    from .semantic import SemanticChunker

# RecursiveChunker (langchain_text_splitters) and SemanticChunker (sentence_transformers)
# pull torch/transformers at import. Resolve lazily (PEP 562) so importing this package
# — and thus the lightweight ChunkConfig used by vector/config.py — stays ML-free; the
# chunker materializes on first use (runtime, in a prefork child).
_LAZY = {"RecursiveChunker": ".recursive", "SemanticChunker": ".semantic"}


def __getattr__(name):
    if name in _LAZY:
        return getattr(_importlib.import_module(_LAZY[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BaseChunker", "RecursiveChunker", "SemanticChunker", "ChunkConfig"]
