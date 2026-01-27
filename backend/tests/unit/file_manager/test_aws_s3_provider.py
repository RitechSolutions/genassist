import pytest
from unittest.mock import Mock, patch

from app.modules.filemanager.providers.s3.provider import S3StorageProvider


# ==================== Fixtures ====================

@pytest.fixture
def s3_config():
    """Create a test S3 configuration."""
    return {
        "aws_bucket_name": "test-bucket",
        "aws_access_key_id": "test-access-key",
        "aws_secret_access_key": "test-secret-key",
        "aws_region_name": "us-east-1"
    }


@pytest.fixture
def mock_s3_client():
    """Create a mocked S3Client."""
    mock_client = Mock()
    return mock_client


@pytest.fixture
def s3_provider(s3_config, mock_s3_client):
    """Create an S3StorageProvider with mocked S3Client."""
    # Patch S3Client during provider initialization
    with patch('app.modules.filemanager.providers.s3.provider.S3Client', return_value=mock_s3_client):
        provider = S3StorageProvider(config=s3_config)
    # Ensure the mock is set (in case patch didn't work as expected)
    provider.s3_client = mock_s3_client
    return provider


# ==================== Unit Tests ====================

class TestS3StorageProvider:
    """Test S3 storage provider with mocked S3Client."""

    @pytest.mark.asyncio
    async def test_list_files_without_prefix_or_limit(self, s3_provider, mock_s3_client):
        """Test listing files without prefix or limit."""
        # Setup mock response
        mock_s3_client.list_files.return_value = [
            "file1.txt",
            "file2.pdf",
            "folder1/file3.txt"
        ]
        
        # Call the method
        result = await s3_provider.list_files()
        
        # Verify results
        assert result == ["file1.txt", "file2.pdf", "folder1/file3.txt"]
        mock_s3_client.list_files.assert_called_once_with(prefix=None, limit=None)

    @pytest.mark.asyncio
    async def test_list_files_with_prefix(self, s3_provider, mock_s3_client):
        """Test listing files with a prefix filter."""
        # Setup mock response
        mock_s3_client.list_files.return_value = [
            "folder1/file1.txt",
            "folder1/file2.pdf"
        ]
        
        # Call the method
        result = await s3_provider.list_files(prefix="folder1/")
        
        # Verify results
        assert result == ["folder1/file1.txt", "folder1/file2.pdf"]
        mock_s3_client.list_files.assert_called_once_with(prefix="folder1/", limit=None)

    @pytest.mark.asyncio
    async def test_list_files_with_limit(self, s3_provider, mock_s3_client):
        """Test listing files with a limit."""
        # Setup mock response
        mock_s3_client.list_files.return_value = [
            "file1.txt",
            "file2.pdf"
        ]
        
        # Call the method
        result = await s3_provider.list_files(limit=2)
        
        # Verify results
        assert result == ["file1.txt", "file2.pdf"]
        mock_s3_client.list_files.assert_called_once_with(prefix=None, limit=2)

    @pytest.mark.asyncio
    async def test_list_files_with_prefix_and_limit(self, s3_provider, mock_s3_client):
        """Test listing files with both prefix and limit."""
        # Setup mock response
        mock_s3_client.list_files.return_value = [
            "folder1/file1.txt"
        ]
        
        # Call the method
        result = await s3_provider.list_files(prefix="folder1/", limit=1)
        
        # Verify results
        assert result == ["folder1/file1.txt"]
        mock_s3_client.list_files.assert_called_once_with(prefix="folder1/", limit=1)

    @pytest.mark.asyncio
    async def test_list_files_empty_result(self, s3_provider, mock_s3_client):
        """Test listing files when bucket is empty."""
        # Setup mock response
        mock_s3_client.list_files.return_value = []
        
        # Call the method
        result = await s3_provider.list_files()
        
        # Verify results
        assert result == []
        mock_s3_client.list_files.assert_called_once_with(prefix=None, limit=None)

    def test_get_base_path(self, s3_provider):
        """Test getting the base path returns bucket name."""
        assert s3_provider.get_base_path() == "test-bucket"

    def test_get_stats(self, s3_provider):
        """Test getting provider statistics."""
        stats = s3_provider.get_stats()
        
        assert stats["provider_type"] == "s3"
        assert stats["bucket_name"] == "test-bucket"
        assert stats["initialized"] == False
        assert stats["status"] == "stub - not implemented"

    def test_initialization_with_config(self, s3_config, mock_s3_client):
        """Test provider initialization with configuration."""
        with patch('app.modules.filemanager.providers.s3.provider.S3Client', return_value=mock_s3_client):
            provider = S3StorageProvider(config=s3_config)
            
            assert provider.aws_bucket_name == "test-bucket"
            assert provider.aws_access_key_id == "test-access-key"
            assert provider.aws_secret_access_key == "test-secret-key"
            assert provider.aws_region_name == "us-east-1"
            assert provider.s3_client == mock_s3_client

    def test_initialization_with_default_region(self, mock_s3_client):
        """Test provider initialization with default region."""
        config = {
            "aws_bucket_name": "test-bucket",
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key"
        }
        
        with patch('app.modules.filemanager.providers.s3.provider.S3Client', return_value=mock_s3_client):
            provider = S3StorageProvider(config=config)
            
            assert provider.aws_region_name == "us-east-1"  # Default value
