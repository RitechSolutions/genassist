"""
Unit tests for OpenAI file upload functionality.
"""
import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock
from app.services.open_ai_fine_tuning import OpenAIFineTuningService
from app.repositories.openai_fine_tuning import FineTuningRepository
from app.services.fine_tuning_event import FineTuningEventService
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException


@pytest.fixture
def mock_repository():
    """Create a mocked repository."""
    return AsyncMock(spec=FineTuningRepository)


@pytest.fixture
def mock_event_service():
    """Create a mocked event service."""
    return AsyncMock(spec=FineTuningEventService)


@pytest.fixture
def mock_openai_client():
    """Create a mocked OpenAI client."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_response.id = "file-abc123"
    mock_response.filename = "test.pdf"
    mock_response.purpose = "user_data"
    mock_response.bytes = 1024
    client.files.create = AsyncMock(return_value=mock_response)
    return client


@pytest.fixture
def openai_service(mock_repository, mock_event_service, mock_openai_client):
    """Create OpenAIFineTuningService with mocked dependencies."""
    service = OpenAIFineTuningService(
        repository=mock_repository,
        event_service=mock_event_service
    )
    service.client = mock_openai_client
    return service


@pytest.fixture
def temp_pdf_file():
    """Create a temporary PDF file for testing."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pdf') as f:
        f.write(b"Test PDF content")
        path = f.name
    yield path
    os.unlink(path)


@pytest.mark.asyncio
async def test_upload_file_for_chat_success(openai_service, mock_repository, mock_openai_client, temp_pdf_file):
    """Test successful file upload to OpenAI for chat."""
    file_id = await openai_service.upload_file_for_chat(
        file_path=temp_pdf_file,
        filename="test.pdf",
        purpose="user_data"
    )

    assert file_id == "file-abc123"
    mock_openai_client.files.create.assert_called_once()
    call_kwargs = mock_openai_client.files.create.call_args.kwargs
    assert call_kwargs["purpose"] == "user_data"
    assert call_kwargs["file"][0] == "test.pdf"
    mock_repository.create_file_record.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_for_chat_db_error_continues(openai_service, mock_repository, mock_openai_client, temp_pdf_file):
    """Test that DB errors don't fail the upload."""
    mock_repository.create_file_record.side_effect = Exception("DB error")

    file_id = await openai_service.upload_file_for_chat(
        file_path=temp_pdf_file,
        filename="test.pdf",
        purpose="user_data"
    )

    assert file_id == "file-abc123"
    mock_openai_client.files.create.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_for_chat_openai_error_raises(openai_service, mock_openai_client, temp_pdf_file):
    """Test that OpenAI errors are properly raised."""
    mock_openai_client.files.create.side_effect = Exception("OpenAI API error")

    with pytest.raises(AppException) as exc_info:
        await openai_service.upload_file_for_chat(
            file_path=temp_pdf_file,
            filename="test.pdf",
            purpose="user_data"
        )

    assert exc_info.value.error_key == ErrorKey.ERROR_UPLOAD_FILE_OPEN_AI


@pytest.mark.asyncio
async def test_upload_file_for_chat_file_not_found(openai_service):
    """Test that file not found raises error."""
    with pytest.raises(AppException) as exc_info:
        await openai_service.upload_file_for_chat(
            file_path="/nonexistent/file.pdf",
            filename="test.pdf",
            purpose="user_data"
        )

    assert exc_info.value.error_key == ErrorKey.ERROR_UPLOAD_FILE_OPEN_AI
