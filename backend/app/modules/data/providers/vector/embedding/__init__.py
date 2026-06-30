"""
Embedding Module

Provides different text embedding providers for vector generation.
"""

import importlib as _importlib
from typing import TYPE_CHECKING

from .base import BaseEmbedder, EmbeddingConfig

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .bedrock import BedrockEmbedder
    from .huggingface import HuggingFaceEmbedder
    from .openai import OpenAIEmbedder

# HuggingFaceEmbedder pulls sentence_transformers/torch at import. Resolve all embedder
# implementations lazily (PEP 562) so importing this package — and the lightweight
# EmbeddingConfig used by vector/config.py — stays ML-free; the embedder materializes
# on first use (runtime, in a prefork child).
_LAZY = {
    "BedrockEmbedder": ".bedrock",
    "HuggingFaceEmbedder": ".huggingface",
    "OpenAIEmbedder": ".openai",
}


def __getattr__(name):
    if name in _LAZY:
        return getattr(_importlib.import_module(_LAZY[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BaseEmbedder", "EmbeddingConfig", "BedrockEmbedder", "HuggingFaceEmbedder", "OpenAIEmbedder"]
