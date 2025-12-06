"""
Recursive character text splitter implementation
"""

from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .base import BaseChunker, ChunkConfig, Chunk


class RecursiveChunker(BaseChunker):
    """Recursive character text chunker using LangChain"""
    
    def __init__(self, config: ChunkConfig):
        super().__init__(config)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators,
            keep_separator=config.keep_separator,
            strip_whitespace=config.strip_whitespace,
            length_function=len,
        )
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        Split text into chunks using recursive character splitting
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk
            
        Returns:
            List of Chunk objects
        """
        if not text.strip():
            return []
        
        # Use LangChain splitter to get text chunks
        text_chunks = self.splitter.split_text(text)
        
        chunks = []
        current_position = 0
        
        for i, chunk_text in enumerate(text_chunks):
            # Find the position of this chunk in the original text
            start_pos = text.find(chunk_text, current_position)
            if start_pos == -1:
                # Fallback if exact match not found
                start_pos = current_position
            
            chunk = self._create_chunk(
                content=chunk_text,
                index=i,
                start_char=start_pos,
                metadata=metadata
            )
            chunks.append(chunk)
            
            # Update position for next search
            current_position = start_pos + len(chunk_text)
        
        return chunks
