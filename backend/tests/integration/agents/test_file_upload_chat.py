"""
Integration tests for file upload to chat with OpenAI file_id support.
"""
import pytest
import tempfile
import os
import logging
from unittest.mock import patch, AsyncMock, MagicMock

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
@patch('app.services.open_ai_fine_tuning.OpenAIFineTuningService.upload_file_for_chat')
async def test_upload_pdf_file_to_chat_with_openai(
    mock_upload_openai,
    authorized_client,
    sample_pdf_file
):
    """Test uploading a PDF file to chat with OpenAI file_id."""
    # Mock OpenAI upload to return a file_id
    mock_upload_openai.return_value = "file-test123"
    
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
    assert "openai_file_id" in data
    assert data["openai_file_id"] == "file-test123"
    assert data["original_filename"] == "test.pdf"
    
    # Verify OpenAI upload was called
    mock_upload_openai.assert_called_once()


@pytest.mark.asyncio
@patch('app.services.open_ai_fine_tuning.OpenAIFineTuningService.upload_file_for_chat')
async def test_upload_txt_file_to_chat_no_openai(
    mock_upload_openai,
    authorized_client,
    sample_txt_file
):
    """Test uploading a non-PDF file doesn't trigger OpenAI upload."""
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
    assert "openai_file_id" in data
    assert data["openai_file_id"] is None  # Should be None for non-PDF
    assert data["original_filename"] == "test.txt"
    
    # Verify OpenAI upload was NOT called for non-PDF
    mock_upload_openai.assert_not_called()


@pytest.mark.asyncio
@patch('app.services.open_ai_fine_tuning.OpenAIFineTuningService.upload_file_for_chat')
async def test_upload_pdf_openai_failure_continues(
    mock_upload_openai,
    authorized_client,
    sample_pdf_file
):
    """Test that OpenAI upload failure doesn't break file upload."""
    # Make OpenAI upload fail
    mock_upload_openai.side_effect = Exception("OpenAI API error")
    
    # Upload should still succeed
    with open(sample_pdf_file, 'rb') as f:
        response = authorized_client.post(
            "/api/genagent/knowledge/upload-chat-file",
            data={"chat_id": "test-chat-123"},
            files=[("file", ("test.pdf", f, "application/pdf"))]
        )
    
    assert response.status_code == 200
    data = response.json()
    
    # File should still be uploaded locally
    assert "file_id" in data
    assert data["openai_file_id"] is None  # Should be None on failure
    assert data["original_filename"] == "test.pdf"


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
