import pytest
from unittest.mock import Mock, patch

from app.modules.filemanager.providers.s3.provider import S3StorageProvider


# ==================== Fixtures ====================

@pytest.fixture
def s3_config():
    """Create a test S3 configuration matching the provider's expected keys."""
    return {
        "AWS_BUCKET_NAME": "test-bucket",
        "AWS_ACCESS_KEY_ID": "test-access-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        "AWS_REGION": "us-east-1",
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
    @pytest.mark.parametrize("prefix,limit,expected_keys,expected_call_args", [
        (
            None, None,
            ["file1.txt", "file2.pdf", "folder1/file3.txt"],
            {"prefix": "", "max_keys": 1000},
        ),
        (
            "folder1/", None,
            ["folder1/file1.txt", "folder1/file2.pdf"],
            {"prefix": "folder1/", "max_keys": 1000},
        ),
        (
            None, 2,
            ["file1.txt", "file2.pdf"],
            {"prefix": "", "max_keys": 2},
        ),
        (
            "folder1/", 1,
            ["folder1/file1.txt"],
            {"prefix": "folder1/", "max_keys": 1},
        ),
    ])
    async def test_list_files(self, s3_provider, mock_s3_client, prefix, limit, expected_keys, expected_call_args):
        """Test listing files with various prefix/limit combinations."""
        mock_s3_client.list_files.return_value = {
            "files": [{"key": k} for k in expected_keys]
        }

        kwargs = {}
        if prefix is not None:
            kwargs["prefix"] = prefix
        if limit is not None:
            kwargs["limit"] = limit

        result = await s3_provider.list_files(**kwargs)

        assert result == expected_keys
        mock_s3_client.list_files.assert_called_once_with(**expected_call_args)

    @pytest.mark.asyncio
    async def test_list_files_empty_result(self, s3_provider, mock_s3_client):
        """Test listing files when bucket is empty."""
        mock_s3_client.list_files.return_value = {"files": []}

        result = await s3_provider.list_files()

        assert result == []
        mock_s3_client.list_files.assert_called_once_with(prefix="", max_keys=1000)

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

    def test_initialization_with_partial_config_keeps_none_region(self, mock_s3_client):
        """Test provider initialization when region is not provided."""
        config = {
            "AWS_BUCKET_NAME": "test-bucket",
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        }

        with patch('app.modules.filemanager.providers.s3.provider.S3Client', return_value=mock_s3_client):
            provider = S3StorageProvider(config=config)

        assert provider.aws_bucket_name == "test-bucket"
        assert provider.aws_region_name is None
