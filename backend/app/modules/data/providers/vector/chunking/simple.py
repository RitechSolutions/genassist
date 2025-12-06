"""
Simple text chunker implementation that splits text using separators
"""

from typing import List, Dict, Any, Optional
from .base import BaseChunker, ChunkConfig, Chunk, decode_separators


class SimpleChunker(BaseChunker):
    """Simple text chunker that splits text using provided separators"""

    def __init__(self, config: ChunkConfig):
        super().__init__(config)
        # Use separators from config, defaulting to common separators if none provided
        self.separators = config.separators or ["\n\n", "\n", " ", ""]

    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """
        Split text into chunks using simple separator-based splitting

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of Chunk objects
        """
        if not text.strip():
            return []

        # Split text using the first available separator
        chunks_text = self._split_text_with_separators(text)

        chunks = []
        current_position = 0

        for chunk_text in chunks_text:
            if not chunk_text.strip():
                continue

            # Find the position of this chunk in the original text
            start_pos = text.find(chunk_text, current_position)
            if start_pos == -1:
                # Fallback if exact match not found
                start_pos = current_position

            chunk = self._create_chunk(
                content=chunk_text.strip() if self.config.strip_whitespace else chunk_text,
                index=len(chunks),  # Use actual chunk count as index
                start_char=start_pos,
                metadata=metadata
            )
            chunks.append(chunk)

            # Update position for next search
            current_position = start_pos + len(chunk_text)

        return chunks

    def _split_text_with_separators(self, text: str) -> List[str]:
        """
        Split text using the configured separators in order of preference

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        return self._split_text_recursive(text, self.separators)

    def _split_text_recursive(self, text: str, separators: List[str]) -> List[str]:
        """
        Recursively split text using separators, similar to RecursiveCharacterTextSplitter

        Args:
            text: Text to split
            separators: List of separators to try in order

        Returns:
            List of text chunks
        """
        # if not separators:
        #     return [text] if text else []
        
        # recursivly no separators left → must hard-split if still too big
        if not separators:
            if len(text) <= self.config.chunk_size:
                return [text]
            else:
                # HARD SPLIT by chunk size
                return [
                    text[i: i + self.config.chunk_size]
                    for i in range(0, len(text), self.config.chunk_size)
                ]

        separator = separators[0]
        remaining_separators = separators[1:]

        # If separator is empty string, split by character
        if separator == "":
            return list(text)

        # Split by current separator
        if separator in text:
            splits = text.split(separator)

            # Add separator back if keep_separator is True
            if self.config.keep_separator and len(splits) > 1:
                # Add separator to all parts except the last one
                for i in range(len(splits) - 1):
                    splits[i] += separator

            # Recursively process each split if it's still too large
            chunks = []
        
            for split in splits:
                if len(split) > self.config.chunk_size:
                    # Still too big → use remaining separators or fallback
                    if remaining_separators:
                        chunks.extend(self._split_text_recursive(split, remaining_separators))
                    else:
                        # No separators left → fallback hard split
                        chunks.extend(
                            split[i: i + self.config.chunk_size]
                            for i in range(0, len(split), self.config.chunk_size)
                        )
                else:
                    if split:
                        chunks.append(split)

            return chunks

        # separator not found → try next one
        return self._split_text_recursive(text, remaining_separators)

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """
        Merge small chunks together to optimize chunk sizes

        Args:
            chunks: List of text chunks

        Returns:
            List of merged chunks
        """
        if not chunks:
            return []

        merged_chunks = []
        current_chunk = ""

        for chunk in chunks:
            chunk = chunk.strip() if self.config.strip_whitespace else chunk
            if not chunk:
                continue

            # If adding this chunk would exceed chunk_size, finalize current chunk
            if current_chunk and len(current_chunk) + len(chunk) > self.config.chunk_size:
                merged_chunks.append(current_chunk)
                current_chunk = chunk
            else:
                # Add chunk to current chunk
                if current_chunk:
                    # Use the first separator to join chunks
                    separator = self.separators[0] if self.separators else " "
                    current_chunk += separator + chunk
                else:
                    current_chunk = chunk

        # Add the final chunk if it has content
        if current_chunk:
            merged_chunks.append(current_chunk)

        return merged_chunks
