"""
Vector Provider System

A clean, modular vector provider system that separates concerns:
- chunking: Text splitting strategies
- embedding: Text embedding providers  
- db: Vector database providers
- orchestrator: Coordinates all components based on configuration
"""

from .provider import VectorProvider
from .config import ChunkConfig, EmbeddingConfig, VectorDBConfig, VectorConfig

__all__ = ["VectorProvider", "ChunkConfig",
           "EmbeddingConfig", "VectorDBConfig", "VectorConfig"]
