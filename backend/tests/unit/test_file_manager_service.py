import pytest
import tempfile
import shutil
import logging
from uuid import uuid4
from unittest.mock import AsyncMock, create_autospec

from app.services.file_manager import FileManagerService
from app.repositories.file_manager import FileManagerRepository
from app.schemas.file import FileCreate
from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.db.models.file import FileModel
from app.core.tenant_scope import set_tenant_context, clear_tenant_context

logger = logging.getLogger(__name__)


# ==================== Fixtures ====================

@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for file storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def local_provider(temp_storage_dir):
    """Create a real local file system storage provider."""
    return LocalFileSystemProvider(config={"base_path": temp_storage_dir})


@pytest.fixture
def mock_repository():
    """Create a mocked file manager repository."""
    return AsyncMock(spec=FileManagerRepository)


@pytest.fixture
def test_user_id():
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def test_tenant_id():
    """Set up test tenant context."""
    tenant_id = "test_tenant"
    set_tenant_context(tenant_id)
    yield tenant_id
    clear_tenant_context()


def create_mock_file_model(file_id=None, name="test_file.txt", storage_provider="local",
                           storage_path=None, user_id=None, size=100, mime_type="text/plain"):
    """Helper to create a mock FileModel instance."""
    mock_file = create_autospec(FileModel, instance=True)
    mock_file.id = file_id or uuid4()
    mock_file.name = name
    mock_file.storage_provider = storage_provider
    mock_file.storage_path = storage_path or f"test_tenant/user_{user_id}/{name}"
    mock_file.user_id = user_id
    mock_file.size = size
    mock_file.mime_type = mime_type
    return mock_file


# ==================== Unit Tests ====================

class TestLocalFileManagerService:
    """Test file manager service with real local storage provider."""

    @pytest.mark.asyncio
    async def test_create_file_uploads_to_local_storage(
        self, mock_repository, local_provider, test_user_id, test_tenant_id
    ):
        """Test creating a file uploads content to local storage."""
        file_content = b"Hello, World!"
        file_name = "test_file.txt"
        expected_path = f"{test_tenant_id}/user_{test_user_id}/{file_name}"

        # Setup mock repository response
        mock_file = create_mock_file_model(
            name=file_name,
            storage_path=expected_path,
            user_id=test_user_id,
            size=len(file_content)
        )
        mock_repository.create_file.return_value = mock_file

        # Create service with real local provider
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)

        file_data = FileCreate(
            name=file_name,
            mime_type="text/plain",
            storage_provider="local"
        )

        result = await service.create_file(
            file_data=file_data,
            file_content=file_content,
            user_id=test_user_id
        )

        # Log the file path for debugging
        full_path = local_provider._resolve_path(expected_path)
        logger.info(f"File saved to: {full_path}")
        logger.info(f"Base path: {local_provider.base_path}")
        logger.info(f"Storage path (relative): {expected_path}")

        # Verify file was created in repository
        assert result.name == file_name
        mock_repository.create_file.assert_called_once()

        # Verify file actually exists on disk
        assert await local_provider.file_exists(expected_path)
        stored_content = await local_provider.download_file(expected_path)
        assert stored_content == file_content

    @pytest.mark.asyncio
    async def test_get_file_content_reads_from_local_storage(
        self, mock_repository, local_provider, test_user_id, test_tenant_id
    ):
        """Test reading file content from local storage."""
        file_content = b"Content to read"
        file_id = uuid4()
        storage_path = f"{test_tenant_id}/user_{test_user_id}/read_test.txt"

        # Pre-upload file to storage
        await local_provider.initialize()
        await local_provider.upload_file(file_content, storage_path)

        # Setup mock repository to return file metadata
        mock_file = create_mock_file_model(
            file_id=file_id,
            storage_path=storage_path,
            user_id=test_user_id
        )
        mock_repository.get_file_by_id.return_value = mock_file

        # Create service
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)

        # Read content
        result = await service.get_file_content(file_id)

        assert result == file_content
        mock_repository.get_file_by_id.assert_called_once_with(file_id)

    @pytest.mark.asyncio
    async def test_delete_file_removes_from_local_storage(
        self, mock_repository, local_provider, test_user_id, test_tenant_id
    ):
        """Test deleting a file removes it from local storage."""
        file_content = b"Content to delete"
        file_id = uuid4()
        storage_path = f"{test_tenant_id}/user_{test_user_id}/delete_test.txt"

        # Pre-upload file to storage
        await local_provider.initialize()
        await local_provider.upload_file(file_content, storage_path)
        assert await local_provider.file_exists(storage_path)

        # Setup mock repository
        mock_file = create_mock_file_model(
            file_id=file_id,
            storage_path=storage_path,
            user_id=test_user_id
        )
        mock_repository.get_file_by_id.return_value = mock_file

        # Create service
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)

        # Delete file
        await service.delete_file(file_id, delete_from_storage=True)

        # Verify file removed from storage
        assert not await local_provider.file_exists(storage_path)
        mock_repository.delete_file.assert_called_once_with(file_id)

    @pytest.mark.asyncio
    async def test_create_file_without_content_skips_upload(
        self, mock_repository, local_provider, test_user_id, test_tenant_id
    ):
        """Test creating a file without content only creates metadata."""
        file_name = "metadata_only.txt"
        storage_path = f"{test_tenant_id}/user_{test_user_id}/{file_name}"

        mock_file = create_mock_file_model(
            name=file_name,
            storage_path=storage_path,
            user_id=test_user_id,
            size=0
        )
        mock_repository.create_file.return_value = mock_file

        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)

        file_data = FileCreate(
            name=file_name,
            mime_type="text/plain",
            storage_provider="local",
            size=0
        )

        result = await service.create_file(
            file_data=file_data,
            file_content=None,
            user_id=test_user_id
        )

        assert result.name == file_name
        mock_repository.create_file.assert_called_once()
        # File should not exist on disk since no content was uploaded
        assert not await local_provider.file_exists(storage_path)
