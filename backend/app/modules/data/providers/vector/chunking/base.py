"""
Base chunking interface
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator

from ....schema_utils import VECTOR_DEFAULTS


class ChunkConfig(BaseModel):
    """Configuration for chunking strategy"""
    type: str = Field(default=VECTOR_DEFAULTS["chunk_strategy"],
                      description="Type of chunking strategy")
    chunk_size: int = Field(
        default=VECTOR_DEFAULTS["chunk_size"], description="Size of text chunks")
    chunk_overlap: int = Field(
        default=VECTOR_DEFAULTS["chunk_overlap"], description="Overlap between chunks")
    separators: Optional[List[str]] = Field(
        default_factory=lambda: (
            [s.strip()
             for s in VECTOR_DEFAULTS["chunk_separators"].split(",") if s.strip()]
            if VECTOR_DEFAULTS["chunk_separators"] and isinstance(VECTOR_DEFAULTS["chunk_separators"], str)
            else ["\n\n", "\n", " ", ""]
        ),
        description="Separators for text splitting")
    keep_separator: bool = Field(
        default=VECTOR_DEFAULTS["chunk_keep_separator"], description="Whether to keep separators in chunks")
    strip_whitespace: bool = Field(
        default=VECTOR_DEFAULTS["chunk_strip_whitespace"], description="Whether to strip whitespace from chunks")

    @field_validator('chunk_overlap')
    @classmethod
    def validate_chunk_overlap(cls, v, info):
        if info.data and 'chunk_size' in info.data and v >= info.data['chunk_size']:
            raise ValueError('chunk_overlap must be less than chunk_size')
        return v

    @field_validator('separators', mode='before')
    @classmethod
    def validate_separators(cls, v):
        if isinstance(v, str):
            # If it's a string, split by comma and clean up
            if v:
                return decode_separators(v.split(",") if v.split(",") else ["\n\n", "\n", " ", ""])
            else:
                # Use default separators if empty string
                return ["\n\n", "\n", " ", ""]
        elif isinstance(v, list):
            # If it's already a list, return as is
            return decode_separators(v)
        else:
            # Fallback to default separators
            return ["\n\n", "\n", " ", ""]

    def get(self) -> "BaseChunker":
        """Get the chunker based on the type"""
        if self.type == "recursive":
            from .recursive import RecursiveChunker
            return RecursiveChunker(self.model_copy())
        elif self.type == "semantic":
            from .semantic import SemanticChunker
            return SemanticChunker(self.model_copy())
        elif self.type == "simple":
            from .simple import SimpleChunker
            return SimpleChunker(self.model_copy())
        else:
            raise ValueError(f"Invalid chunker type: {self.type}")

    class Config:
        extra = "allow"


class Chunk(BaseModel):
    """Represents a text chunk with metadata"""
    content: str = Field(description="Text content of the chunk")
    index: int = Field(description="Index of the chunk in the sequence")
    start_char: int = Field(
        description="Starting character position in original text")
    end_char: int = Field(
        description="Ending character position in original text")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {}, description="Additional metadata for the chunk")

    @field_validator('metadata', mode='before')
    @classmethod
    def ensure_metadata_dict(cls, v):
        return v or {}

    @field_validator('end_char')
    @classmethod
    def validate_char_positions(cls, v, info):
        if info.data and 'start_char' in info.data and v <= info.data['start_char']:
            raise ValueError('end_char must be greater than start_char')
        return v

    class Config:
        extra = "allow"


class BaseChunker(ABC):
    """Base abstract class for text chunking strategies"""

    def __init__(self, config: ChunkConfig):
        self.config = config

    @abstractmethod
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """
        Split text into chunks

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of Chunk objects
        """
        raise NotImplementedError(
            "Subclasses must implement chunk_text method")

    def _create_chunk(self, content: str, index: int, start_char: int, metadata: Optional[Dict[str, Any]] = None) -> Chunk:
        """Create a chunk with proper metadata"""
        end_char = start_char + len(content)

        chunk_metadata = {
            "chunk_index": index,
            "start_char": start_char,
            "end_char": end_char,
            "chunk_size": len(content),
            **(metadata or {})
        }

        return Chunk(
            content=content,
            index=index,
            start_char=start_char,
            end_char=end_char,
            metadata=chunk_metadata
        )

def decode_separators(separators: List[str]) -> List[str]:
    """
    Decode escaped separator strings to actual characters

    Args:
        separators: List of separator strings that may contain escaped characters

    Returns:
        List of decoded separator strings
    """
    decoded_separators = []

    for separator in separators:
        if isinstance(separator, str):
            # Decode common escape sequences
            decoded = separator.replace('\\n', '\n')
            decoded = decoded.replace('\\t', '\t')
            decoded = decoded.replace('\\r', '\r')
            # Handle escaped backslashes
            decoded = decoded.replace('\\\\', '\\')
            decoded_separators.append(decoded)
        else:
            decoded_separators.append(separator)

    return decoded_separators
