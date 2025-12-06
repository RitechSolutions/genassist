import uuid
import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from bs4 import BeautifulSoup


class ChunkingMethod(Enum):
    FIXED_ROLLING = "FIXED_ROLLING"
    SENTENCE = "SENTENCE"
    CUSTOM = "CUSTOM"
    SEMANTIC_MD = "SEMANTIC_MD"
    SEMANTIC_HTML = "SEMANTIC_HTML"

@dataclass
class TextChunk:
    """Data class representing a text chunk"""
    id: str
    doc_id: str
    sequence_no: int
    chunk_content: str
    chunking_method: ChunkingMethod

class ChunkService():
    # Should it be a class or just the methods ? -- if we keep the args, we use them in methods
    def __init__(self, chunk_size:int = 500, overlap_size: int=100,
                        custom_sentence_endings: Optional[List[str]] = None,
                        delimiters: List[str] = [],
                        heading_levels: Optional[List[int]] = None,
                        tags:Optional[List[str]] = None
                        ):
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.custom_sentence_endings = custom_sentence_endings
        self.delimiters = delimiters
        self.heading_levels = heading_levels
        self.tags = tags

    def fixed_rolling_text_split(self, doc_id: str, content: str, chunk_size:Optional[int]=None, overlap_size:Optional[int]=None) -> List[TextChunk]:
        """
        Split text into fixed-size chunks with optional overlap
        Args:
            doc_id: Document identifier
            content: Text content to split
            chunk_size: Size of each chunk
            overlap_size: Size of overlap between chunks
            
        Returns:
            List of TextChunk objects
        """
        chunk_size = chunk_size or self.chunk_size
        overlap_size = overlap_size if overlap_size is not None else self.overlap_size
        if overlap_size >= chunk_size:
            raise ValueError(f"Overlap size: {overlap_size} must be smaller than chunk size: {chunk_size}")
        
        chunks = []
        sequence_no = 1
        start_index = 0
        step = chunk_size - overlap_size
        
        while start_index < len(content):
            end_index = min(start_index + chunk_size, len(content))
            chunk_content = content[start_index:end_index]
            
            if chunk_content.strip():
                chunks.append(TextChunk(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    sequence_no=sequence_no,
                    chunk_content=chunk_content,
                    chunking_method=ChunkingMethod.FIXED_ROLLING
                ))
                sequence_no += 1
            
            start_index += step
            if start_index >= len(content):
                break      
        return chunks

    def sentence_text_split(self, doc_id: str, content: str, custom_sentence_endings: Optional[List[str]] = None) -> List[TextChunk]:
        """
        Split text based on sentence endings
        
        Args:
            doc_id: Document identifier
            content: Text content to split
            custom_sentence_endings: Custom sentence ending characters
            
        Returns:
            List of TextChunk objects
        """
        chunks = []
        sequence_no = 1

        default_endings = ['.', ';', ':', '\n', '!', '?']
        custom_sentence_endings = custom_sentence_endings or self.custom_sentence_endings
        sentence_endings = custom_sentence_endings or default_endings
        
        # Create regex pattern for sentence endings
        escaped_endings = [re.escape(ending) for ending in sentence_endings]
        pattern = f"([{''.join(escaped_endings)}])"
        
        # Split on sentence endings and keep the delimiters
        parts = re.split(pattern, content)
        current_chunk = ""
        
        for i, part in enumerate(parts):
            if part in sentence_endings:
                # This is a delimiter, add it to current chunk and finalize
                current_chunk += part
                if current_chunk.strip():
                    chunks.append(TextChunk(
                        id=str(uuid.uuid4()),
                        doc_id=doc_id,
                        sequence_no=sequence_no,
                        chunk_content=current_chunk.strip(),
                        chunking_method=ChunkingMethod.SENTENCE
                    ))
                    sequence_no += 1
                    current_chunk = ""
            else:
                # This is content, add to current chunk
                current_chunk += part
        
        # Handle any remaining content
        if current_chunk.strip():
            chunks.append(TextChunk(
                id=str(uuid.uuid4()),
                doc_id=doc_id,
                sequence_no=sequence_no,
                chunk_content=current_chunk.strip(),
                chunking_method=ChunkingMethod.SENTENCE
            ))
        
        return chunks

    def custom_text_split(self, doc_id: str, content: str, delimiters: List[str], preserve_delimiters: bool = True) -> List[TextChunk]:
        """
        Split text based on custom delimiters
        
        Args:
            doc_id: Document identifier
            content: Text content to split
            delimiters: List of delimiter strings
            preserve_delimiters: Whether to preserve delimiters in chunks
            
        Returns:
            List of TextChunk objects
        """
        chunks = []
        sequence_no = 1
        delimiters = delimiters or self.delimiters
        if not delimiters:
            # No delimiters provided, return entire content as one chunk
            chunks.append(TextChunk(
                id=str(uuid.uuid4()),
                doc_id=doc_id,
                sequence_no=1,
                chunk_content=content,
                chunking_method=ChunkingMethod.CUSTOM
            ))
            return chunks
        
        # Sort delimiters by length (longest first) to handle overlapping delimiters
        sorted_delimiters = sorted(delimiters, key=len, reverse=True)
        
        # Create regex pattern for all delimiters
        escaped_delimiters = [re.escape(delimiter) for delimiter in sorted_delimiters]
        pattern = f"({'|'.join(escaped_delimiters)})"
        
        if preserve_delimiters:
            # Split and keep delimiters
            parts = re.split(f"({pattern})", content)
            current_chunk = ""
            
            for part in parts:
                if part in delimiters:
                    # This is a delimiter
                    if preserve_delimiters and current_chunk.strip():
                        # Add previous chunk
                        chunks.append(TextChunk(
                            id=str(uuid.uuid4()),
                            doc_id=doc_id,
                            sequence_no=sequence_no,
                            chunk_content=current_chunk.strip(),
                            chunking_method=ChunkingMethod.CUSTOM
                        ))
                        sequence_no += 1
                    current_chunk = part  # Start new chunk with delimiter
                else:
                    current_chunk += part
            
            # Add final chunk
            if current_chunk.strip():
                chunks.append(TextChunk(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    sequence_no=sequence_no,
                    chunk_content=current_chunk.strip(),
                    chunking_method=ChunkingMethod.CUSTOM
                ))
        else:
            # Split without preserving delimiters
            parts = re.split(pattern, content)
            for part in parts:
                if part not in delimiters and part.strip():
                    chunks.append(TextChunk(
                        id=str(uuid.uuid4()),
                        doc_id=doc_id,
                        sequence_no=sequence_no,
                        chunk_content=part.strip(),
                        chunking_method=ChunkingMethod.CUSTOM
                    ))
                    sequence_no += 1
        
        return chunks

    def semantic_md_document_split(self, doc_id: str, content: str, heading_levels: Optional[List[int]] = None, include_headings: bool = True) -> List[TextChunk]:
        """
        Split Markdown content based on headings
        
        Args:
            doc_id: Document identifier
            content: Markdown content to split
            heading_levels: List of heading levels to split on 1 to 6
            include_headings: Whether to include heading text in chunks
            
        Returns:
            List of TextChunk objects
        """
        chunks = []
        sequence_no = 1
        
        # Default to all heading levels
        heading_levels = heading_levels or self.heading_levels
        levels = heading_levels or [1, 2, 3, 4, 5, 6]
        
        # Create regex pattern for markdown headings
        heading_pattern = r'^(#{1,6})\s+(.+)$'
        
        lines = content.split('\n')
        current_chunk_lines = []
        
        for line in lines:
            heading_match = re.match(heading_pattern, line)
            
            if heading_match:
                heading_level = len(heading_match.group(1))
                heading_text = heading_match.group(2)
                
                if heading_level in levels:
                    # Save previous chunk if it has content
                    if current_chunk_lines:
                        chunk_content = '\n'.join(current_chunk_lines).strip()
                        if chunk_content:
                            chunks.append(TextChunk(
                                id=str(uuid.uuid4()),
                                doc_id=doc_id,
                                sequence_no=sequence_no,
                                chunk_content=chunk_content,
                                chunking_method=ChunkingMethod.SEMANTIC_MD
                            ))
                            sequence_no += 1
                    
                    # Start new chunk
                    current_chunk_lines = []
                    
                    if include_headings:
                        current_chunk_lines.append(line)
                else:
                    # Heading level not in our target levels, add to current chunk
                    current_chunk_lines.append(line)
            else:
                # Regular content line
                current_chunk_lines.append(line)
        
        # Handle final chunk
        if current_chunk_lines:
            chunk_content = '\n'.join(current_chunk_lines).strip()
            if chunk_content:
                chunks.append(TextChunk(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    sequence_no=sequence_no,
                    chunk_content=chunk_content,
                    chunking_method=ChunkingMethod.SEMANTIC_MD
                ))
        
        return chunks

    def semantic_html_document_split(self, doc_id: str, content: str, tags: List[str], include_opening_tags: bool = False) -> List[TextChunk]:
        """
        Split HTML content based on specified tags
        
        Args:
            doc_id: Document identifier
            content: HTML content to split
            tags: List of HTML tags to split on (e.g., ['h1', 'h2', 'div'])
            include_opening_tags: Whether to include opening tags in chunks
            
        Returns:
            List of TextChunk objects
        """
        chunks = []
        sequence_no = 1
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            tags = tags or self.tags
            # Find all elements with the specified tags
            target_elements = soup.find_all(tags)
            
            if not target_elements:
                # No target elements found, return entire content as one chunk
                chunks.append(TextChunk(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    sequence_no=1,
                    chunk_content=content,
                    chunking_method=ChunkingMethod.SEMANTIC_HTML
                ))
                return chunks
            
            # Process each target element
            for element in target_elements:
                chunk_content = ""
                
                if include_opening_tags:
                    # Include the opening tag
                    chunk_content = str(element)
                else:
                    # Just the text content
                    chunk_content = element.get_text(strip=True)
                    
                    # If the element has child elements that aren't in our target tags,
                    # include their HTML
                    children = element.find_all()
                    if children:
                        # Get inner HTML while preserving structure
                        inner_elements = []
                        for child in element.children:
                            if hasattr(child, 'name') and child.name not in tags:
                                inner_elements.append(str(child))
                            elif isinstance(child, str):
                                inner_elements.append(child)
                        
                        if inner_elements:
                            chunk_content = ''.join(inner_elements).strip()
                
                if chunk_content.strip():
                    chunks.append(TextChunk(
                        id=str(uuid.uuid4()),
                        doc_id=doc_id,
                        sequence_no=sequence_no,
                        chunk_content=chunk_content.strip(),
                        chunking_method=ChunkingMethod.SEMANTIC_HTML
                    ))
                    sequence_no += 1
                    
        except Exception as e:
            chunks.append(TextChunk(
                id=str(uuid.uuid4()),
                doc_id=doc_id,
                sequence_no=1,
                chunk_content=content,
                chunking_method=ChunkingMethod.SEMANTIC_HTML
            ))
        
        return chunks