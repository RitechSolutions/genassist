import pytest
import tempfile
import shutil
import logging
import io
import os
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from fastapi import UploadFile

from app.services.file_manager import FileManagerService
from app.repositories.file_manager import FileManagerRepository
from app.schemas.file import FileBase
from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.db.models.file import FileModel
from app.core.tenant_scope import set_tenant_context, clear_tenant_context
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

logger = logging.getLogger(__name__)


def create_mock_upload_file(filename: str = "test.txt", content: bytes = b"test content") -> MagicMock:
    """Helper to create a mock UploadFile."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.file = io.BytesIO(content)
    # One chunk, then b"" to end the stream (a constant return value never ends it).
    mock_file.read = AsyncMock(side_effect=[content, b""])
    mock_file.seek = AsyncMock()
    return mock_file


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


def create_mock_file_model(
    file_id=None,
    name="test_file.txt",
    storage_provider="local",
    storage_path=None,
    user_id=None,
    size=100,
    mime_type="text/plain",
    path=None,
    file_extension=None,
):
    """Helper to create a mock FileModel instance."""
    mock_file = create_autospec(FileModel, instance=True)
    mock_file.id = file_id or uuid4()
    mock_file.name = name
    mock_file.storage_provider = storage_provider
    mock_file.storage_path = storage_path or f"test_tenant/user_{user_id}/{name}"
    mock_file.user_id = user_id
    mock_file.size = size
    mock_file.mime_type = mime_type
    mock_file.path = path
    mock_file.file_extension = file_extension
    return mock_file


# ==================== Unit Tests ====================

class TestLocalProviderContainment:
    """Every provider operation stays inside base_path."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["../outside.txt", "a/../../outside.txt", "/etc/hosts"])
    async def test_operations_refuse_paths_outside_base(self, local_provider, temp_storage_dir, path):
        await local_provider.initialize()

        assert await local_provider.upload_file(b"x", path) is False
        assert await local_provider.delete_file(path) is False
        assert await local_provider.file_exists(path) is False
        with pytest.raises(ValueError):
            await local_provider.download_file(path)
        parent = os.path.dirname(os.path.abspath(temp_storage_dir))
        assert not os.path.exists(os.path.join(parent, "outside.txt"))

    @pytest.mark.asyncio
    async def test_absolute_path_inside_base_still_works(self, local_provider, temp_storage_dir):
        """get_file_content passes '<base>/<path>', which must keep working."""
        await local_provider.initialize()
        await local_provider.upload_file(b"inside", "docs/a.txt")

        assert await local_provider.download_file(os.path.join(temp_storage_dir, "docs", "a.txt")) == b"inside"


class TestLocalFileManagerService:
    """Test file manager service with real local storage provider."""

    @pytest.mark.asyncio
    async def test_create_file_uploads_to_local_storage(
        self, mock_repository, local_provider, test_user_id, test_tenant_id, temp_storage_dir
    ):
        """Test creating a file uploads content to local storage."""
        file_content = b"Hello, World!"
        file_name = "test_file.txt"

        # Setup mock repository response
        mock_file = create_mock_file_model(
            name=file_name,
            user_id=test_user_id,
            size=len(file_content)
        )
        mock_repository.create_file.return_value = mock_file

        # Create service with real local provider
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)

        # Create mock upload file
        mock_upload_file = create_mock_upload_file(file_name, file_content)
        mock_upload_file.content_type = "text/plain"

        # Create file metadata payload – use a relative path so that the
        # LocalFileSystemProvider resolves paths correctly under its base_path.
        result = await service.create_file(
            file=mock_upload_file,
            file_base=FileBase(
                name=file_name,
                path="",
                storage_path=file_name,
                storage_provider="local",
                file_extension="txt"
            )
        )

        # Verify file was created in repository
        assert result.name == file_name
        mock_repository.create_file.assert_called_once()

        # Verify file was actually uploaded to storage
        # Stored under a uuid name, not the name from the request.
        created_file_data = mock_repository.create_file.call_args[0][0]
        stored_path = created_file_data.path
        assert stored_path != file_name and stored_path.endswith(".txt")

        assert await local_provider.file_exists(stored_path)
        stored_content = await local_provider.download_file(stored_path)
        assert stored_content == file_content

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["../../..", "a/../../b", "..\\..\\x"])
    async def test_create_file_rejects_path_traversal(
        self, mock_repository, local_provider, temp_storage_dir, path
    ):
        """A path that climbs out of the storage folder is rejected and nothing is written."""
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)

        with pytest.raises(AppException) as exc:
            await service.create_file(
                file=create_mock_upload_file("evil.txt", b"x"),
                file_base=FileBase(name="evil.txt", path=path, storage_path="", storage_provider="local"),
            )

        assert exc.value.error_key == ErrorKey.INVALID_FILE_PATH
        assert exc.value.status_code == 400
        mock_repository.create_file.assert_not_called()
        parent = os.path.dirname(os.path.abspath(temp_storage_dir))
        assert not os.path.exists(os.path.join(parent, "evil.txt"))

    @pytest.mark.asyncio
    async def test_create_file_ignores_name_and_cleans_folder(
        self, mock_repository, local_provider, temp_storage_dir
    ):
        """The request's name never becomes the stored file name; the folder is kept, cleaned."""
        mock_repository.create_file.side_effect = lambda data: data
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)

        upload = create_mock_upload_file("report.pdf", b"pdf")
        upload.content_type = "application/pdf"
        result = await service.create_file(
            file=upload,
            file_base=FileBase(
                name="../../outside.pdf", path="/docs//./2026/", storage_path="", storage_provider="local"
            ),
        )

        folder, stored_name = result.path.rsplit("/", 1)
        assert folder == "docs/2026"
        assert stored_name.endswith(".pdf") and "outside" not in stored_name
        assert result.name == "../../outside.pdf"  # kept only as the display name
        assert os.path.isfile(os.path.join(temp_storage_dir, "docs", "2026", stored_name))

    @pytest.mark.asyncio
    async def test_create_file_from_local_path_rejects_path_traversal(
        self, mock_repository, local_provider, temp_storage_dir
    ):
        """The chunked-upload path rejects a climbing folder and leaves the source file alone."""
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)
        source_dir = tempfile.mkdtemp()
        try:
            source = os.path.join(source_dir, "chunked.txt")
            with open(source, "wb") as handle:
                handle.write(b"x")

            with pytest.raises(AppException) as exc:
                await service.create_file_from_local_path(
                    source,
                    FileBase(name="evil.txt", path="../../..", storage_path="", storage_provider="local"),
                    original_filename="evil.txt",
                )

            assert exc.value.error_key == ErrorKey.INVALID_FILE_PATH
            mock_repository.create_file.assert_not_called()
            assert os.path.isfile(source)
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_create_file_from_local_path_stores_uuid_name_in_folder(
        self, mock_repository, local_provider, temp_storage_dir
    ):
        """The copy lands in the cleaned folder under a uuid name."""
        mock_repository.create_file.side_effect = lambda data: data
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)
        source_dir = tempfile.mkdtemp()
        try:
            source = os.path.join(source_dir, "chunked.png")
            with open(source, "wb") as handle:
                handle.write(b"png")

            result = await service.create_file_from_local_path(
                source,
                FileBase(name="../shot.png", path="./shots/", storage_path="", storage_provider="local"),
                original_filename="shot.png",
            )

            folder, stored_name = result.path.rsplit("/", 1)
            assert folder == "shots"
            assert stored_name.endswith(".png") and "shot" not in stored_name
            assert os.path.isfile(os.path.join(temp_storage_dir, "shots", stored_name))
            assert not os.path.exists(source)  # delete_source defaults to True
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    @pytest.mark.parametrize(
        "filename, expected",
        [("a.PDF", "pdf"), ("noext", "txt"), (None, "txt"), ("x.b/../../y", "txt"), ("x.p/df", "txt"), ("a.t-x_t", "txt")],
    )
    def test_clean_file_extension(self, filename, expected):
        assert FileManagerService._clean_file_extension(filename) == expected

    @pytest.mark.asyncio
    async def test_get_file_content_reads_from_local_storage(
        self, mock_repository, temp_storage_dir
    ):
        """Test reading file content from local storage."""
        file_content = b"Content to read"
        file_id = uuid4()
        storage_path = "read_test.txt"

        # Pre-upload file to storage using a real local provider
        preupload_provider = LocalFileSystemProvider(config={"base_path": temp_storage_dir})
        await preupload_provider.initialize()
        await preupload_provider.upload_file(file_content, storage_path)

        # Setup mock repository to return file metadata
        mock_file = create_mock_file_model(
            file_id=file_id,
            storage_provider="local",
            storage_path=storage_path,
            path=storage_path,
        )

        # Create service bound to the same local provider
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(preupload_provider)

        # Read content
        result = await service.get_file_content(mock_file)

        assert result == file_content

    @pytest.mark.asyncio
    async def test_download_file_fetches_metadata_and_content(
        self, mock_repository, temp_storage_dir
    ):
        """Test download_file returns both metadata and content."""
        file_content = b"Downloaded content"
        file_id = uuid4()
        storage_path = "download_test.txt"

        # Pre-upload file to storage
        preupload_provider = LocalFileSystemProvider(config={"base_path": temp_storage_dir})
        await preupload_provider.initialize()
        await preupload_provider.upload_file(file_content, storage_path)

        # Setup mock repository to return file metadata
        mock_file = create_mock_file_model(
            file_id=file_id,
            storage_provider="local",
            storage_path=storage_path,
            path=storage_path,
        )
        mock_repository.get_file_by_id.return_value = mock_file

        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(preupload_provider)

        db_file, content = await service.download_file(file_id)

        assert db_file == mock_file
        assert content == file_content
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
            storage_provider="local",
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


class TestFileManagerServiceBuildFileHeaders:
    """Test the build_file_headers method."""

    def test_build_file_headers_basic(self, mock_repository):
        """Test building headers with basic file info."""
        mock_file = create_mock_file_model(
            name="test.txt",
            mime_type="text/plain",
            size=100
        )

        service = FileManagerService(repository=mock_repository)
        headers, media_type = service.build_file_headers(mock_file)

        assert media_type == "text/plain"
        assert headers["content-type"] == "text/plain"
        assert "content-disposition" in headers
        assert 'filename="test.txt"' in headers["content-disposition"]
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["cache-control"] == "public, max-age=31536000"

    def test_build_file_headers_with_content(self, mock_repository):
        """Test building headers with content provided."""
        mock_file = create_mock_file_model(
            name="test.txt",
            mime_type="text/plain",
            size=100
        )
        content = b"Hello, World!"

        service = FileManagerService(repository=mock_repository)
        headers, media_type = service.build_file_headers(mock_file, content=content)

        assert headers["content-length"] == str(len(content))

    @pytest.mark.parametrize("disposition_type", ["attachment", "inline"])
    def test_build_file_headers_disposition_type(self, mock_repository, disposition_type):
        """Test building headers with different disposition types."""
        mock_file = create_mock_file_model(
            name="test_file.pdf",
            mime_type="application/pdf",
            size=1000
        )

        service = FileManagerService(repository=mock_repository)
        headers, media_type = service.build_file_headers(
            mock_file, disposition_type=disposition_type
        )

        assert disposition_type in headers["content-disposition"]

    def test_build_file_headers_unicode_filename(self, mock_repository):
        """Test building headers with unicode characters in filename."""
        mock_file = create_mock_file_model(
            name="文件测试.txt",
            mime_type="text/plain",
            size=100
        )

        service = FileManagerService(repository=mock_repository)
        headers, media_type = service.build_file_headers(mock_file)

        # Should contain UTF-8 encoded filename
        assert "filename*=UTF-8''" in headers["content-disposition"]

    def test_build_file_headers_no_mime_type(self, mock_repository):
        """Test building headers when mime_type is None."""
        mock_file = create_mock_file_model(
            name="unknown_file",
            mime_type=None,
            size=100
        )

        service = FileManagerService(repository=mock_repository)
        headers, media_type = service.build_file_headers(mock_file)

        assert media_type == "application/octet-stream"
        assert headers["content-type"] == "application/octet-stream"


class TestFileManagerServiceGetDefaultStorageProvider:
    """Test storage provider initialization helpers."""

    @pytest.mark.asyncio
    async def test_initialize_storage_provider_returns_existing_initialized_provider(
        self, mock_repository, local_provider
    ):
        """If a provider is already set and initialized, it should be reused."""
        service = FileManagerService(repository=mock_repository)
        await service.set_storage_provider(local_provider)

        # Should not attempt to create a new provider; just keep the existing one.
        result = await service._initialize_storage_provider(local_provider.name)

        assert result == local_provider
        assert service.storage_provider == local_provider
