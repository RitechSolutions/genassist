"""
Embedding Module

Provides different text embedding providers for vector generation.
"""

from .base import BaseEmbedder, EmbeddingConfig
from .bedrock import BedrockEmbedder
from .huggingface import HuggingFaceEmbedder
from .openai import OpenAIEmbedder

__all__ = ["BaseEmbedder", "EmbeddingConfig", "BedrockEmbedder", "HuggingFaceEmbedder", "OpenAIEmbedder"]
