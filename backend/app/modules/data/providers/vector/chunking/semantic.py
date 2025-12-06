"""
Semantic text chunker implementation
"""

import re
from typing import List, Dict, Any, Optional
from .base import BaseChunker, ChunkConfig, Chunk


class SemanticChunker(BaseChunker):
    """Semantic text chunker that splits on sentence and paragraph boundaries"""
    
    def __init__(self, config: ChunkConfig):
        super().__init__(config)
        # Sentence boundary patterns
        self.sentence_endings = re.compile(r'[.!?]+\s+')
        self.paragraph_endings = re.compile(r'\n\s*\n')
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """
        Split text into chunks using semantic boundaries
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk
            
        Returns:
            List of Chunk objects
        """
        if not text.strip():
            return []
        
        # First try to split by paragraphs
        paragraphs = self.paragraph_endings.split(text)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # If adding this paragraph would exceed chunk size, finalize current chunk
            if (current_chunk and
                    len(current_chunk) + len(paragraph) > self.config.chunk_size):
                
                chunk = self._create_chunk(
                    content=current_chunk.strip(),
                    index=chunk_index,
                    start_char=current_start,
                    metadata=metadata
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + paragraph
                current_start = text.find(paragraph, current_start)
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
                    current_start = text.find(paragraph, current_start)
        
        # Add final chunk if it has content
        if current_chunk.strip():
            chunk = self._create_chunk(
                content=current_chunk.strip(),
                index=chunk_index,
                start_char=current_start,
                metadata=metadata
            )
            chunks.append(chunk)
        
        return chunks
    
    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text from the end of current chunk"""
        if len(text) <= self.config.chunk_overlap:
            return text
        
        # Try to find a sentence boundary for clean overlap
        sentences = self.sentence_endings.split(text)
        
        overlap_text = ""
        for sentence in reversed(sentences):
            if len(overlap_text) + len(sentence) <= self.config.chunk_overlap:
                overlap_text = sentence + " " + overlap_text
            else:
                break
        
        if not overlap_text.strip():
            # Fallback to character-based overlap
            overlap_text = text[-self.config.chunk_overlap:]
        
        return overlap_text.strip() + " " if overlap_text.strip() else ""
