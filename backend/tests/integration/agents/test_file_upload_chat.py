"""
Integration tests for file upload to chat.
"""
import pytest
import tempfile
import os
import logging

logger = logging.getLogger(__name__)


@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    # Create a minimal PDF file (just for testing, not a real PDF)
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pdf') as f:
        # Write minimal PDF header
        f.write(b"%PDF-1.4\n")
        f.write(b"1 0 obj\n")
        f.write(b"<< /Type /Catalog >>\n")
        f.write(b"endobj\n")
        f.write(b"xref\n")
        f.write(b"trailer\n")
        f.write(b"%%EOF\n")
        temp_file_path = f.name

    yield temp_file_path

    # Cleanup
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)


@pytest.fixture
def sample_txt_file():
    """Create a sample text file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("This is a test text file content.")
        temp_file_path = f.name

    yield temp_file_path

    # Cleanup
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)


@pytest.mark.asyncio
async def test_upload_pdf_file_to_chat(
    authorized_client,
    sample_pdf_file
):
    """Test uploading a PDF file to chat."""
    # Upload file
    with open(sample_pdf_file, 'rb') as f:
        response = authorized_client.post(
            "/api/genagent/knowledge/upload-chat-file",
            data={"chat_id": "test-chat-123"},
            files=[("file", ("test.pdf", f, "application/pdf"))]
        )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "file_id" in data
    assert "filename" in data
    assert "file_path" in data
    assert "file_url" in data
    assert "original_filename" in data
    assert "storage_path" in data
    assert data["original_filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_upload_txt_file_to_chat(
    authorized_client,
    sample_txt_file
):
    """Test uploading a text file to chat."""
    # Upload file
    with open(sample_txt_file, 'rb') as f:
        response = authorized_client.post(
            "/api/genagent/knowledge/upload-chat-file",
            data={"chat_id": "test-chat-123"},
            files=[("file", ("test.txt", f, "text/plain"))]
        )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "file_id" in data
    assert "filename" in data
    assert "file_path" in data
    assert "file_url" in data
    assert "original_filename" in data
    assert data["original_filename"] == "test.txt"


@pytest.mark.asyncio
async def test_upload_docx_file_to_chat(
    authorized_client,
):
    """Test uploading a DOCX file to chat."""
    # Create a minimal DOCX file (just for testing)
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.docx') as f:
        # Write minimal DOCX content (it's a zip file format)
        # This is a simplified test - actual DOCX is more complex
        f.write(b"PK\x03\x04")  # ZIP header
        temp_file_path = f.name

    try:
        with open(temp_file_path, 'rb') as f:
            response = authorized_client.post(
                "/api/genagent/knowledge/upload-chat-file",
                data={"chat_id": "test-chat-123"},
                files=[("file", ("test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
            )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "file_id" in data
        assert "original_filename" in data
        assert data["original_filename"] == "test.docx"
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@pytest.mark.asyncio
async def test_upload_file_to_chat_missing_chat_id(authorized_client, sample_pdf_file):
    """Test that missing chat_id returns error."""
    with open(sample_pdf_file, 'rb') as f:
        response = authorized_client.post(
            "/api/genagent/knowledge/upload-chat-file",
            files=[("file", ("test.pdf", f, "application/pdf"))]
        )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_upload_file_to_chat_invalid_file_type(authorized_client):
    """Test that invalid file types are rejected."""
    # Create a file with unsupported extension
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.exe') as f:
        f.write(b"binary content")
        temp_file_path = f.name

    try:
        with open(temp_file_path, 'rb') as f:
            response = authorized_client.post(
                "/api/genagent/knowledge/upload-chat-file",
                data={"chat_id": "test-chat-123"},
                files=[("file", ("test.exe", f, "application/x-msdownload"))]
            )

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
