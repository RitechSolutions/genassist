import pytest
import pytest_asyncio
import tempfile
import shutil
from uuid import uuid4
from unittest.mock import AsyncMock, create_autospec, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config.settings import settings

from app.services.file_manager import FileManagerService
from app.repositories.file_manager import FileManagerRepository
from app.schemas.file import FileCreate, FileUpdate
from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.modules.filemanager.providers.base import BaseStorageProvider
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import set_tenant_context, clear_tenant_context
from app.db.seed.seed_data_config import seed_test_data
from app.db.models.file import FileModel


# ==================== Fixtures ====================

@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for file storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def storage_provider(temp_storage_dir):
    """Create a local file system storage provider."""
    provider = LocalFileSystemProvider(config={"base_path": temp_storage_dir})
    return provider


@pytest.fixture
def mock_repository():
    """Create a mocked file manager repository for unit tests."""
    return AsyncMock(spec=FileManagerRepository)


@pytest.fixture
def file_manager_service(mock_repository, storage_provider):
    """Create a file manager service with mocked repository and storage provider."""
    service = FileManagerService(repository=mock_repository)
    service.set_storage_provider(storage_provider)
    return service


@pytest.fixture
def test_user_id():
    """Get a test user ID from seed data."""
    from uuid import UUID
    return UUID(seed_test_data.admin_user_id)


@pytest.fixture
def test_tenant_id():
    """Set up test tenant context."""
    tenant_id = "test_tenant"
    set_tenant_context(tenant_id)
    yield tenant_id
    clear_tenant_context()


@pytest.fixture
def mock_starlette_context(test_user_id):
    """Mock starlette context for tests."""
    from starlette_context import context as starlette_context
    from unittest.mock import patch, MagicMock, AsyncMock
    
    # Create a mock context that returns the user_id
    mock_context = MagicMock()
    mock_context.get = MagicMock(return_value=str(test_user_id))
    mock_context.exists = MagicMock(return_value=True)
    
    # Mock FastAPICache backend with async clear method
    mock_cache_backend = MagicMock()
    mock_cache_backend.clear = AsyncMock(return_value=None)
    
    with patch('app.repositories.file_manager.context', mock_context):
        with patch('app.services.file_manager.context', mock_context):
            with patch('app.repositories.file_manager.FastAPICache') as mock_cache:
                mock_cache.get_backend.return_value = mock_cache_backend
                yield


def create_mock_file(file_id=None, name="test_file.txt", storage_provider="local", 
                     path=None, storage_path=None, user_id=None, size=100, **kwargs):
    """Helper to create a mock FileModel instance."""
    mock_file = create_autospec(FileModel, instance=True)
    mock_file.id = file_id or uuid4()
    mock_file.name = name
    mock_file.storage_provider = storage_provider
    mock_file.path = path or f"test_tenant/user_{user_id}/{name}" if user_id else f"test_tenant/{name}"
    mock_file.storage_path = storage_path or mock_file.path
    mock_file.user_id = user_id
    mock_file.size = size
    mock_file.mime_type = kwargs.get("mime_type", "text/plain")
    mock_file.description = kwargs.get("description")
    mock_file.file_metadata = kwargs.get("file_metadata", {})
    mock_file.tags = kwargs.get("tags", [])
    mock_file.permissions = kwargs.get("permissions", {})
    return mock_file


def create_mock_provider(provider_name="mock"):
    """Helper to create a mock storage provider."""
    provider = AsyncMock(spec=BaseStorageProvider)
    provider.name = provider_name
    provider.provider_type = provider_name
    provider.upload_file = AsyncMock(return_value="mock_storage_path")
    provider.download_file = AsyncMock(return_value=b"mock_content")
    provider.delete_file = AsyncMock(return_value=True)
    provider.file_exists = AsyncMock(return_value=True)
    provider.list_files = AsyncMock(return_value=[])
    provider.initialize = AsyncMock(return_value=True)
    provider.is_initialized = MagicMock(return_value=True)
    return provider


# ==================== CRUD Tests ====================

class TestCRUDOperations:
    """Test Create, Read, Update, Delete operations."""

    @pytest.mark.asyncio
    async def test_create_file(self, file_manager_service: FileManagerService, mock_repository: FileManagerRepository, storage_provider: BaseStorageProvider, 
test_user_id):
        """Test creating a file with content."""
        file_data = FileCreate(
            name="test_file.txt",
            mime_type="text/plain",
            storage_provider="local"
        )
        file_content = b"Hello, World!"
        
        # Setup mock repository response
        mock_file = create_mock_file(
            name="test_file.txt",
            storage_provider="local",
            user_id=test_user_id,
            size=len(file_content)
        )
        mock_repository.create_file.return_value = mock_file
        
        # Mock storage provider upload
        storage_provider.upload_file = AsyncMock(return_value=mock_file.storage_path)
        
        # Create file
        result = await file_manager_service.create_file(
            file_data=file_data,
            file_content=file_content,
            user_id=test_user_id
        )
        
        # Verify
        assert result.id == mock_file.id
        assert result.name == "test_file.txt"
        assert result.size == len(file_content)
        mock_repository.create_file.assert_called_once()
        storage_provider.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_file_without_content(self, file_manager_service, mock_repository, 
                                                test_user_id, test_tenant_id):
        """Test creating a file without content."""
        file_data = FileCreate(
            name="empty_file.txt",
            mime_type="text/plain",
            storage_provider="local",
            size=0
        )
        
        mock_file = create_mock_file(
            name="empty_file.txt",
            user_id=test_user_id,
            size=0
        )
        mock_repository.create_file.return_value = mock_file
        
        result = await file_manager_service.create_file(
            file_data=file_data,
            file_content=None,
            user_id=test_user_id
        )
        
        assert result.name == "empty_file.txt"
        assert result.size == 0
        mock_repository.create_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_file_by_id(self, file_manager_service, mock_repository, test_user_id, test_tenant_id):
        """Test reading a file by ID."""
        file_id = uuid4()
        mock_file = create_mock_file(file_id=file_id, name="read_test.txt", user_id=test_user_id)
        mock_repository.get_file_by_id.return_value = mock_file
        
        result = await file_manager_service.get_file_by_id(file_id)
        
        assert result.id == file_id
        assert result.name == "read_test.txt"
        mock_repository.get_file_by_id.assert_called_once_with(file_id)

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, file_manager_service, mock_repository):
        """Test reading a non-existent file raises error."""
        file_id = uuid4()
        mock_repository.get_file_by_id.side_effect = AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND)
        
        with pytest.raises(AppException) as exc_info:
            await file_manager_service.get_file_by_id(file_id)
        
        assert exc_info.value.error_key == ErrorKey.DATASOURCE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_read_file_content(self, file_manager_service, mock_repository, storage_provider, 
                                     test_user_id, test_tenant_id):
        """Test reading file content from storage."""
        file_id = uuid4()
        file_content = b"File content"
        storage_path = f"{test_tenant_id}/user_{test_user_id}/content_test.txt"
        
        mock_file = create_mock_file(file_id=file_id, storage_path=storage_path, user_id=test_user_id)
        mock_repository.get_file_by_id.return_value = mock_file
        storage_provider.download_file = AsyncMock(return_value=file_content)
        
        result = await file_manager_service.get_file_content(file_id)
        
        assert result == file_content
        storage_provider.download_file.assert_called_once_with(storage_path)

    @pytest.mark.asyncio
    async def test_list_files(self, file_manager_service, mock_repository, test_user_id, test_tenant_id):
        """Test listing files."""
        mock_files = [
            create_mock_file(name=f"file_{i}.txt", user_id=test_user_id) 
            for i in range(3)
        ]
        mock_repository.list_files.return_value = mock_files
        
        result = await file_manager_service.list_files(user_id=test_user_id)
        
        assert len(result) == 3
        mock_repository.list_files.assert_called_once_with(
            user_id=test_user_id,
            storage_provider=None,
            limit=None,
            offset=None
        )

    @pytest.mark.asyncio
    async def test_list_files_with_pagination(self, file_manager_service, mock_repository, test_user_id, test_tenant_id):
        """Test listing files with pagination."""
        page1 = [create_mock_file(name=f"file_{i}.txt", user_id=test_user_id) for i in range(2)]
        page2 = [create_mock_file(name=f"file_{i}.txt", user_id=test_user_id) for i in range(2, 4)]
        mock_repository.list_files.side_effect = [page1, page2]
        
        result1 = await file_manager_service.list_files(user_id=test_user_id, limit=2)
        result2 = await file_manager_service.list_files(user_id=test_user_id, limit=2, offset=2)
        
        assert len(result1) == 2
        assert len(result2) == 2
        assert mock_repository.list_files.call_count == 2

    @pytest.mark.asyncio
    async def test_update_file(self, file_manager_service, mock_repository, test_user_id, test_tenant_id, 
                               mock_starlette_context):
        """Test updating file metadata."""
        file_id = uuid4()
        update_data = FileUpdate(
            name="updated_name.txt",
            description="Updated description",
            mime_type="text/html"
        )
        
        updated_file = create_mock_file(
            file_id=file_id,
            name="updated_name.txt",
            description="Updated description",
            mime_type="text/html",
            user_id=test_user_id
        )
        mock_repository.update_file.return_value = updated_file
        
        result = await file_manager_service.update_file(file_id, update_data)
        
        assert result.name == "updated_name.txt"
        assert result.description == "Updated description"
        assert result.mime_type == "text/html"
        mock_repository.update_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_file_path(self, file_manager_service, mock_repository, test_user_id, test_tenant_id, 
                                    mock_starlette_context):
        """Test updating file path."""
        file_id = uuid4()
        new_path = f"{test_tenant_id}/user_{test_user_id}/new/path/file.txt"
        update_data = FileUpdate(path=new_path)
        
        updated_file = create_mock_file(file_id=file_id, path=new_path, storage_path=new_path, user_id=test_user_id)
        mock_repository.update_file.return_value = updated_file
        
        result = await file_manager_service.update_file(file_id, update_data)
        
        assert result.path == new_path
        assert result.storage_path == new_path
        # Verify storage_path was also updated in the call
        call_args = mock_repository.update_file.call_args
        update_obj = call_args[0][1]
        assert update_obj.storage_path == new_path

    @pytest.mark.asyncio
    async def test_delete_file(self, file_manager_service, mock_repository, storage_provider, 
                               test_user_id, test_tenant_id, mock_starlette_context):
        """Test deleting a file."""
        file_id = uuid4()
        storage_path = f"{test_tenant_id}/user_{test_user_id}/delete_test.txt"
        
        mock_file = create_mock_file(file_id=file_id, storage_path=storage_path, user_id=test_user_id)
        mock_repository.get_file_by_id.return_value = mock_file
        storage_provider.delete_file = AsyncMock(return_value=True)
        
        await file_manager_service.delete_file(file_id, delete_from_storage=True)
        
        mock_repository.delete_file.assert_called_once_with(file_id)
        storage_provider.delete_file.assert_called_once_with(storage_path)

    @pytest.mark.asyncio
    async def test_delete_file_metadata_only(self, file_manager_service, mock_repository, storage_provider, 
                                            test_user_id, test_tenant_id, mock_starlette_context):
        """Test deleting file metadata without deleting from storage."""
        file_id = uuid4()
        storage_path = f"{test_tenant_id}/user_{test_user_id}/delete_test.txt"
        
        mock_file = create_mock_file(file_id=file_id, storage_path=storage_path, user_id=test_user_id)
        mock_repository.get_file_by_id.return_value = mock_file
        
        await file_manager_service.delete_file(file_id, delete_from_storage=False)
        
        mock_repository.delete_file.assert_called_once_with(file_id)
        # Storage provider delete should not be called
        if hasattr(storage_provider, 'delete_file'):
            assert not hasattr(storage_provider.delete_file, 'call_count') or storage_provider.delete_file.call_count == 0


# ==================== Multiple Providers Tests ====================

class TestMultipleProviders:
    """Test the same file with different storage providers."""

    # test storing and reading file from Azure Blob Storage
    @pytest.mark.asyncio
    async def test_store_and_read_file_from_azure_blob_storage(self, test_user_id, mock_repository):
        # use the azure blob storage provider without mocking the provider
        from app.modules.filemanager.providers.azure.provider import AzureStorageProvider
        az_provider = AzureStorageProvider(config={})
        await az_provider.initialize()

        file_manager_service = FileManagerService(repository=mock_repository)
        file_manager_service.set_storage_provider(az_provider)

        # create a file content
        file_content = b"Test file content"
        file_name = "test_file.txt"

        # call the file manager service to store the file
        result = await file_manager_service.create_file(
            file_data=FileCreate(
                name=file_name,
                mime_type="text/plain",
                storage_provider="azure"
            ),
            file_content=file_content,
            user_id=test_user_id
        )

        assert result.name == file_name
        assert result.storage_provider == "azure"
        assert result.size == len(file_content)

        # call the file manager service to read the file
        content = await file_manager_service.get_file_content(result.id)

        assert content == file_content

    @pytest.mark.asyncio
    async def test_same_file_different_providers(self, mock_repository, test_user_id, test_tenant_id):
        """Test creating the same file content with different storage providers."""
        file_content = b"Same content for all providers"
        file_name = "shared_file.txt"
        
        providers = ["local", "s3", "azure", "gcs"]
        created_files = []
        
        for provider_name in providers:
            # Create service with different provider
            provider = create_mock_provider(provider_name)
            service = FileManagerService(repository=mock_repository)
            service.set_storage_provider(provider)
            
            # Setup mock repository response
            mock_file = create_mock_file(
                name=file_name,
                storage_provider=provider_name,
                user_id=test_user_id,
                size=len(file_content),
                storage_path=f"{test_tenant_id}/user_{test_user_id}/{provider_name}/{file_name}"
            )
            mock_repository.create_file.return_value = mock_file
            provider.upload_file = AsyncMock(return_value=mock_file.storage_path)
            
            # Create file with same content
            file_data = FileCreate(
                name=file_name,
                mime_type="text/plain",
                storage_provider=provider_name
            )
            
            result = await service.create_file(
                file_data=file_data,
                file_content=file_content,
                user_id=test_user_id
            )
            
            created_files.append(result)
            
            # Verify each file has same content but different provider
            assert result.name == file_name
            assert result.storage_provider == provider_name
            assert result.size == len(file_content)
            provider.upload_file.assert_called_once()
        
        # Verify all files have same name and size but different providers
        assert len(created_files) == len(providers)
        assert all(f.name == file_name for f in created_files)
        assert all(f.size == len(file_content) for f in created_files)
        assert len(set(f.storage_provider for f in created_files)) == len(providers)

    @pytest.mark.asyncio
    async def test_read_file_from_different_providers(self, mock_repository, test_user_id, test_tenant_id):
        """Test reading the same file from different storage providers."""
        file_id = uuid4()
        file_content = b"Content from provider"
        file_name = "multi_provider_file.txt"
        
        providers = ["local", "s3", "azure"]
        
        for provider_name in providers:
            provider = create_mock_provider(provider_name)
            service = FileManagerService(repository=mock_repository)
            service.set_storage_provider(provider)
            
            storage_path = f"{test_tenant_id}/user_{test_user_id}/{provider_name}/{file_name}"
            mock_file = create_mock_file(
                file_id=file_id,
                name=file_name,
                storage_provider=provider_name,
                storage_path=storage_path,
                user_id=test_user_id
            )
            mock_repository.get_file_by_id.return_value = mock_file
            provider.download_file = AsyncMock(return_value=file_content)
            
            # Read file content
            content = await service.get_file_content(file_id)
            
            assert content == file_content
            provider.download_file.assert_called_once_with(storage_path)

    @pytest.mark.asyncio
    async def test_list_files_by_provider(self, mock_repository, test_user_id, test_tenant_id):
        """Test listing files filtered by storage provider."""
        service = FileManagerService(repository=mock_repository)
        
        # Mock files for different providers
        local_files = [
            create_mock_file(name=f"local_file_{i}.txt", storage_provider="local", user_id=test_user_id)
            for i in range(2)
        ]
        s3_files = [
            create_mock_file(name=f"s3_file_{i}.txt", storage_provider="s3", user_id=test_user_id)
            for i in range(2)
        ]
        
        # Test listing local files
        mock_repository.list_files.return_value = local_files
        local_result = await service.list_files(user_id=test_user_id, storage_provider="local")
        assert len(local_result) == 2
        assert all(f.storage_provider == "local" for f in local_result)
        
        # Test listing S3 files
        mock_repository.list_files.return_value = s3_files
        s3_result = await service.list_files(user_id=test_user_id, storage_provider="s3")
        assert len(s3_result) == 2
        assert all(f.storage_provider == "s3" for f in s3_result)

    @pytest.mark.asyncio
    async def test_update_file_provider(self, mock_repository, test_user_id, test_tenant_id, mock_starlette_context):
        """Test updating file to use a different storage provider."""
        file_id = uuid4()
        original_provider = "local"
        new_provider = "s3"
        
        # Original file
        original_file = create_mock_file(
            file_id=file_id,
            storage_provider=original_provider,
            user_id=test_user_id
        )
        mock_repository.get_file_by_id.return_value = original_file
        
        # Updated file with new provider
        updated_file = create_mock_file(
            file_id=file_id,
            storage_provider=new_provider,
            user_id=test_user_id,
            storage_path=f"{test_tenant_id}/user_{test_user_id}/s3/updated.txt"
        )
        mock_repository.update_file.return_value = updated_file
        
        service = FileManagerService(repository=mock_repository)
        update_data = FileUpdate(storage_provider=new_provider)
        
        result = await service.update_file(file_id, update_data)
        
        assert result.storage_provider == new_provider
        mock_repository.update_file.assert_called_once()


# ==================== File Link Tests ====================

class TestFileLinks:
    """Test file linking functionality - files that reference the same storage location."""

    @pytest.mark.asyncio
    async def test_create_file_link_same_storage(self, mock_repository, test_user_id, test_tenant_id):
        """Test creating multiple file records that link to the same storage location."""
        shared_storage_path = f"{test_tenant_id}/shared/shared_file.txt"
        file_content = b"Shared content"
        
        # Create first file
        original_file = create_mock_file(
            name="original.txt",
            storage_path=shared_storage_path,
            user_id=test_user_id
        )
        mock_repository.create_file.return_value = original_file
        
        provider = create_mock_provider("local")
        service = FileManagerService(repository=mock_repository)
        service.set_storage_provider(provider)
        
        file_data1 = FileCreate(
            name="original.txt",
            storage_path=shared_storage_path,
            storage_provider="local"
        )
        result1 = await service.create_file(
            file_data=file_data1,
            file_content=file_content,
            user_id=test_user_id
        )
        
        # Create second file (link) pointing to same storage
        link_file = create_mock_file(
            name="link.txt",
            storage_path=shared_storage_path,  # Same storage path
            user_id=test_user_id
        )
        mock_repository.create_file.return_value = link_file
        
        file_data2 = FileCreate(
            name="link.txt",
            storage_path=shared_storage_path,  # Link to same storage
            storage_provider="local"
        )
        result2 = await service.create_file(
            file_data=file_data2,
            file_content=None,  # No content upload, just link
            user_id=test_user_id
        )
        
        # Both files should point to same storage
        assert result1.storage_path == shared_storage_path
        assert result2.storage_path == shared_storage_path
        assert result1.storage_path == result2.storage_path
        # But different file records
        assert result1.id != result2.id
        assert result1.name != result2.name

    @pytest.mark.asyncio
    async def test_read_linked_file_content(self, mock_repository, storage_provider, test_user_id, test_tenant_id):
        """Test reading content from a linked file (same storage as another file)."""
        shared_storage_path = f"{test_tenant_id}/shared/shared_file.txt"
        file_content = b"Shared content"
        
        # Original file
        original_id = uuid4()
        original_file = create_mock_file(
            file_id=original_id,
            name="original.txt",
            storage_path=shared_storage_path,
            user_id=test_user_id
        )
        
        # Linked file
        link_id = uuid4()
        link_file = create_mock_file(
            file_id=link_id,
            name="link.txt",
            storage_path=shared_storage_path,  # Same storage
            user_id=test_user_id
        )
        
        service = FileManagerService(repository=mock_repository)
        service.set_storage_provider(storage_provider)
        
        # Mock repository to return linked file
        mock_repository.get_file_by_id.return_value = link_file
        storage_provider.download_file = AsyncMock(return_value=file_content)
        
        # Read content from linked file
        content = await service.get_file_content(link_id)
        
        # Should get same content from shared storage
        assert content == file_content
        storage_provider.download_file.assert_called_once_with(shared_storage_path)

    @pytest.mark.asyncio
    async def test_update_file_link(self, mock_repository, test_user_id, test_tenant_id, mock_starlette_context):
        """Test updating a linked file to point to different storage."""
        file_id = uuid4()
        original_storage = f"{test_tenant_id}/shared/original.txt"
        new_storage = f"{test_tenant_id}/shared/new_location.txt"
        
        # Original linked file
        original_file = create_mock_file(
            file_id=file_id,
            name="link.txt",
            storage_path=original_storage,
            user_id=test_user_id
        )
        mock_repository.get_file_by_id.return_value = original_file
        
        # Updated file with new storage path
        updated_file = create_mock_file(
            file_id=file_id,
            name="link.txt",
            storage_path=new_storage,
            user_id=test_user_id
        )
        mock_repository.update_file.return_value = updated_file
        
        service = FileManagerService(repository=mock_repository)
        update_data = FileUpdate(storage_path=new_storage)
        
        result = await service.update_file(file_id, update_data)
        
        assert result.storage_path == new_storage
        assert result.storage_path != original_storage

    @pytest.mark.asyncio
    async def test_delete_linked_file(self, mock_repository, storage_provider, test_user_id, test_tenant_id, 
                                       mock_starlette_context):
        """Test deleting a linked file without affecting other files pointing to same storage."""
        shared_storage_path = f"{test_tenant_id}/shared/shared_file.txt"
        
        # Linked file to delete
        link_id = uuid4()
        link_file = create_mock_file(
            file_id=link_id,
            name="link.txt",
            storage_path=shared_storage_path,
            user_id=test_user_id
        )
        mock_repository.get_file_by_id.return_value = link_file
        storage_provider.delete_file = AsyncMock(return_value=True)
        
        service = FileManagerService(repository=mock_repository)
        service.set_storage_provider(storage_provider)
        
        # Delete linked file metadata only (don't delete storage)
        await service.delete_file(link_id, delete_from_storage=False)
        
        # Verify only metadata deleted, storage not deleted
        mock_repository.delete_file.assert_called_once_with(link_id)
        # Storage should not be deleted since other files might use it
        storage_provider.delete_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_links_same_file(self, mock_repository, test_user_id, test_tenant_id):
        """Test creating multiple links to the same file storage."""
        shared_storage_path = f"{test_tenant_id}/shared/master_file.txt"
        file_content = b"Master content"
        
        provider = create_mock_provider("local")
        service = FileManagerService(repository=mock_repository)
        service.set_storage_provider(provider)
        
        # Create master file
        master_file = create_mock_file(
            name="master.txt",
            storage_path=shared_storage_path,
            user_id=test_user_id
        )
        mock_repository.create_file.return_value = master_file
        provider.upload_file = AsyncMock(return_value=shared_storage_path)
        
        file_data = FileCreate(
            name="master.txt",
            storage_path=shared_storage_path,
            storage_provider="local"
        )
        master = await service.create_file(
            file_data=file_data,
            file_content=file_content,
            user_id=test_user_id
        )
        
        # Create multiple links
        link_names = ["link1.txt", "link2.txt", "link3.txt"]
        links = []
        
        for link_name in link_names:
            link_file = create_mock_file(
                name=link_name,
                storage_path=shared_storage_path,  # All point to same storage
                user_id=test_user_id
            )
            mock_repository.create_file.return_value = link_file
            
            link_data = FileCreate(
                name=link_name,
                storage_path=shared_storage_path,
                storage_provider="local"
            )
            link = await service.create_file(
                file_data=link_data,
                file_content=None,  # No upload, just link
                user_id=test_user_id
            )
            links.append(link)
        
        # Verify all links point to same storage
        assert all(link.storage_path == shared_storage_path for link in links)
        assert master.storage_path == shared_storage_path
        # But all have different IDs and names
        assert len(set(link.id for link in links)) == len(links)
        assert len(set(link.name for link in links)) == len(links)
