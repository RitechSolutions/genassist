import unittest
import uuid
from typing import List
import pytest
from app.services.chunk_service import ChunkService, ChunkingMethod, TextChunk




# Test Fixtures
@pytest.fixture
def chunk_service():
    """Fixture to provide ChunkService instance"""
    return ChunkService()


@pytest.fixture
def test_doc_id():
    """Fixture to provide consistent test document ID"""
    return "test_document_123"


@pytest.fixture
def simple_text():
    """Fixture for simple test text content"""
    return "This is a test. It has multiple sentences! Some end with question marks?"


@pytest.fixture
def markdown_content():
    """Fixture for markdown test content"""
    return """# Main Title
This is the introduction content.
It spans multiple lines.

## Section 1
Content for section 1.
More content here.

### Subsection 1.1
Detailed content in subsection.

## Section 2
Content for section 2."""


@pytest.fixture
def html_content():
    """Fixture for HTML test content"""
    return """
    <html>
        <body>
            <h1>Main Title</h1>
            <p>Introduction paragraph</p>
            <h2>Section 1</h2>
            <p>Section 1 content</p>
            <div>Some div content</div>
            <h2>Section 2</h2>
            <p>Section 2 content</p>
        </body>
    </html>
    """


@pytest.fixture
def unicode_content():
    """Fixture for unicode test content"""
    return "Hello 世界! Это тест. 🌟 Special chars: àáâãäå"


# Helper Functions
def assert_chunk_properties(chunk: TextChunk, doc_id: str, method: ChunkingMethod):
    """Helper function to assert basic chunk properties"""
    assert isinstance(chunk, TextChunk)
    assert isinstance(chunk.id, str)
    
    # Validate UUID format
    try:
        uuid.UUID(chunk.id)
    except ValueError:
        pytest.fail(f"Chunk ID {chunk.id} is not a valid UUID")
    
    assert chunk.doc_id == doc_id
    assert isinstance(chunk.sequence_no, int)
    assert chunk.sequence_no > 0
    assert isinstance(chunk.chunk_content, str)
    assert chunk.chunking_method == method


def assert_chunks_sequential(chunks: List[TextChunk]):
    """Helper function to assert chunks have sequential numbering"""
    for i, chunk in enumerate(chunks, 1):
        assert chunk.sequence_no == i


@pytest.mark.asyncio
async def test_fixed_rolling_text_split_basic(chunk_service: ChunkService, test_doc_id, simple_text):
        """Test basic fixed rolling text split functionality"""
        chunks = chunk_service.fixed_rolling_text_split(
            doc_id=test_doc_id,
            content=simple_text,
            chunk_size=20,
            overlap_size=5
        )

        assert isinstance(chunks, list)
        assert len(chunks) > 1
        
        for chunk in chunks:
            assert_chunk_properties(chunk, test_doc_id, ChunkingMethod.FIXED_ROLLING)
            assert len(chunk.chunk_content) <= 20

        assert_chunks_sequential(chunks)

@pytest.mark.asyncio
async def test_fixed_rolling_text_split_no_overlap(chunk_service: ChunkService, test_doc_id, simple_text):
    """Test fixed rolling text split with no overlap"""
    chunks = chunk_service.fixed_rolling_text_split(
        doc_id=test_doc_id,
        content=simple_text,
        chunk_size=25,
        overlap_size=0
    )

    assert len(chunks) > 1
    
    # Verify no overlap by checking that concatenated chunks equal original
    concatenated = ''.join(chunk.chunk_content for chunk in chunks)
    assert concatenated == simple_text

@pytest.mark.asyncio
async def test_fixed_rolling_text_split_invalid_overlap(chunk_service: ChunkService, test_doc_id, simple_text):
    """Test that invalid overlap size raises ValueError"""
    with pytest.raises(ValueError, match=f"Overlap size: {10} must be smaller than chunk size: {10}"):
        chunk_service.fixed_rolling_text_split(
            doc_id=test_doc_id,
            content=simple_text,
            chunk_size=10,
            overlap_size=10
        )

@pytest.mark.asyncio
async def test_fixed_rolling_text_split_empty_content(chunk_service: ChunkService, test_doc_id):
    """Test fixed rolling split with empty content"""
    chunks = chunk_service.fixed_rolling_text_split(
        doc_id=test_doc_id,
        content="",
        chunk_size=10,
        overlap_size=2
    )

    assert len(chunks) == 0

@pytest.mark.asyncio
async def test_fixed_rolling_text_split_content_smaller_than_chunk(chunk_service: ChunkService, test_doc_id):
    """Test when content is smaller than chunk size"""
    short_content = "Short"
    chunks = chunk_service.fixed_rolling_text_split(
        doc_id=test_doc_id,
        content=short_content,
        chunk_size=100,
        overlap_size=10
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_content == short_content

@pytest.mark.asyncio
async def test_sentence_text_split_basic(chunk_service: ChunkService, test_doc_id, simple_text):
        """Test basic sentence text split functionality"""
        chunks = chunk_service.sentence_text_split(
            doc_id=test_doc_id,
            content=simple_text
        )

        assert isinstance(chunks, list)
        assert len(chunks) > 1
        
        for chunk in chunks:
            assert_chunk_properties(chunk, test_doc_id, ChunkingMethod.SENTENCE)

        assert_chunks_sequential(chunks)

@pytest.mark.asyncio
async def test_sentence_text_split_custom_endings(chunk_service: ChunkService, test_doc_id):
    """Test sentence split with custom endings"""
    custom_content = "First part|Second part|Third part"
    chunks = chunk_service.sentence_text_split(
        doc_id=test_doc_id,
        content=custom_content,
        custom_sentence_endings=["|"]
    )
    assert len(chunks) == 3
    assert chunks[0].chunk_content.endswith("|")

@pytest.mark.asyncio
async def test_sentence_text_split_no_sentence_endings(chunk_service: ChunkService, test_doc_id):
    """Test sentence split with content that has no sentence endings"""
    content = "This is a single sentence with no endings"
    chunks = chunk_service.sentence_text_split(
        doc_id=test_doc_id,
        content=content
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_content == content

@pytest.mark.asyncio
async def test_sentence_text_split_empty_content(chunk_service: ChunkService, test_doc_id):
    """Test sentence split with empty content"""
    chunks = chunk_service.sentence_text_split(
        doc_id=test_doc_id,
        content=""
    )

    assert len(chunks) == 0

@pytest.mark.asyncio
async def test_custom_text_split_basic(chunk_service: ChunkService, test_doc_id):
        """Test basic custom text split functionality"""
        content = "Q1: What is AI?\nQ2: How does it work?\nQ3: What are the benefits?"
        delimiters = ["\nQ"]
        
        chunks = chunk_service.custom_text_split(
            doc_id=test_doc_id,
            content=content,
            delimiters=delimiters
        )

        assert isinstance(chunks, list)
        assert len(chunks) > 1
        
        for chunk in chunks:
            assert_chunk_properties(chunk, test_doc_id, ChunkingMethod.CUSTOM)

        assert_chunks_sequential(chunks)

@pytest.mark.asyncio
async def test_custom_text_split_preserve_delimiters_false(chunk_service: ChunkService, test_doc_id):
    """Test custom split without preserving delimiters"""
    content = "Part1|Part2|Part3"
    delimiters = ["|"]
    
    chunks = chunk_service.custom_text_split(
        doc_id=test_doc_id,
        content=content,
        delimiters=delimiters,
        preserve_delimiters=False
    )

    assert len(chunks) == 3
    for chunk in chunks:
        assert "|" not in chunk.chunk_content

@pytest.mark.asyncio
async def test_custom_text_split_no_delimiters_found(chunk_service: ChunkService, test_doc_id):
    """Test custom split when delimiters are not found in content"""
    content = "This content has no specified delimiters"
    delimiters = ["|||"]
    
    chunks = chunk_service.custom_text_split(
        doc_id=test_doc_id,
        content=content,
        delimiters=delimiters
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_content == content

@pytest.mark.asyncio
async def test_custom_text_split_empty_delimiters(chunk_service: ChunkService, test_doc_id, simple_text):
    """Test custom split with empty delimiters list"""
    chunks = chunk_service.custom_text_split(
        doc_id=test_doc_id,
        content=simple_text,
        delimiters=[]
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_content == simple_text

@pytest.mark.asyncio
async def test_custom_text_split_overlapping_delimiters(chunk_service: ChunkService, test_doc_id):
    """Test custom split with overlapping delimiters"""
    content = "Start\nQ1: Question 1\nQ2: Question 2"
    delimiters = ["\nQ", "\nQ1:", "\nQ2:"]
    
    chunks = chunk_service.custom_text_split(
        doc_id=test_doc_id,
        content=content,
        delimiters=delimiters
    )

    assert len(chunks) > 1

@pytest.mark.asyncio
async def test_semantic_md_document_split_basic(chunk_service: ChunkService, test_doc_id, markdown_content):
        """Test basic semantic MD document split functionality"""
        chunks = chunk_service.semantic_md_document_split(
            doc_id=test_doc_id,
            content=markdown_content
        )
        assert isinstance(chunks, list)
        assert len(chunks) > 1
        
        for chunk in chunks:
            assert_chunk_properties(chunk, test_doc_id, ChunkingMethod.SEMANTIC_MD)

        assert_chunks_sequential(chunks)

@pytest.mark.asyncio
async def test_semantic_md_document_split_specific_levels(chunk_service: ChunkService, test_doc_id, markdown_content):
    """Test MD split with specific heading levels"""
    chunks = chunk_service.semantic_md_document_split(
        doc_id=test_doc_id,
        content=markdown_content,
        heading_levels=[1, 2]
    )

    # Should split on h1 and h2 but not h3
    assert len(chunks) > 1
    
    # Check that h3 content is included in parent section
    found_subsection_content = any(
        "Detailed content in subsection" in chunk.chunk_content 
        for chunk in chunks
    )
    assert found_subsection_content

@pytest.mark.asyncio
async def test_semantic_md_document_split_exclude_headings(chunk_service: ChunkService, test_doc_id, markdown_content):
    """Test MD split excluding headings from chunks"""
    chunks = chunk_service.semantic_md_document_split(
        doc_id=test_doc_id,
        content=markdown_content,
        include_headings=False
    )

    for chunk in chunks:
        # Should not contain heading markers at start of lines
        lines = chunk.chunk_content.split('\n')
        for line in lines:
            if line.strip():
                assert not line.strip().startswith('#')

@pytest.mark.asyncio
async def test_semantic_md_document_split_no_headings(chunk_service: ChunkService, test_doc_id):
    """Test MD split with content that has no headings"""
    content = "This is just plain text content.\nNo headings here.\nJust paragraphs."
    chunks = chunk_service.semantic_md_document_split(
        doc_id=test_doc_id,
        content=content
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_content == content

@pytest.mark.asyncio
async def test_semantic_html_document_split_basic(chunk_service: ChunkService, test_doc_id, html_content):
        """Test basic semantic HTML document split functionality"""
        chunks = chunk_service.semantic_html_document_split(
            doc_id=test_doc_id,
            content=html_content,
            tags=['h1', 'h2']
        )

        assert isinstance(chunks, list)
        assert len(chunks) > 1
        
        for chunk in chunks:
            assert_chunk_properties(chunk, test_doc_id, ChunkingMethod.SEMANTIC_HTML)

        assert_chunks_sequential(chunks)

@pytest.mark.asyncio
async def test_semantic_html_document_split_include_tags(chunk_service: ChunkService, test_doc_id, html_content):
    """Test HTML split including opening tags"""
    chunks = chunk_service.semantic_html_document_split(
        doc_id=test_doc_id,
        content=html_content,
        tags=['h1'],
        include_opening_tags=True
    )

    # Should include HTML tags in output
    found_html_tag = any(
        '<h1>' in chunk.chunk_content 
        for chunk in chunks
    )
    assert found_html_tag

@pytest.mark.asyncio
async def test_semantic_html_document_split_invalid_html(chunk_service: ChunkService, test_doc_id):
    """Test HTML split with invalid HTML (should not crash)"""
    invalid_html = "<html><body><h1>Title</h1><p>Content<body></html>"  # Missing closing p tag
    chunks = chunk_service.semantic_html_document_split(
        doc_id=test_doc_id,
        content=invalid_html,
        tags=['h1']
    )

    # Should handle gracefully and return at least one chunk
    assert len(chunks) > 0

@pytest.mark.asyncio
async def test_semantic_html_document_split_no_target_tags(chunk_service: ChunkService, test_doc_id, html_content):
    """Test HTML split when no target tags are found"""
    chunks = chunk_service.semantic_html_document_split(
        doc_id=test_doc_id,
        content=html_content,
        tags=['article']  # Tag that doesn't exist in content
    )

    # Should return entire content as single chunk
    assert len(chunks) == 1

@pytest.mark.asyncio
async def test_semantic_html_document_split_empty_html(chunk_service: ChunkService, test_doc_id):
    """Test HTML split with empty content"""
    chunks = chunk_service.semantic_html_document_split(
        doc_id=test_doc_id,
        content="",
        tags=['h1']
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_content == ""