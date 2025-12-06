"""
Chunking Module

Provides different text chunking strategies for document processing.
"""

from .base import BaseChunker, ChunkConfig
from .recursive import RecursiveChunker
from .semantic import SemanticChunker

__all__ = ["BaseChunker", "RecursiveChunker", "SemanticChunker", "ChunkConfig"]
