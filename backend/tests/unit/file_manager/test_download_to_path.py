"""Copying a stored file to a local path without reading it into memory."""

from unittest.mock import Mock, patch

import pytest

from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.modules.filemanager.providers.s3.provider import S3StorageProvider


@pytest.mark.asyncio
async def test_local_provider_copies_the_file_without_read_bytes(tmp_path, monkeypatch):
    provider = LocalFileSystemProvider(config={"base_path": str(tmp_path / "store")})
    await provider.initialize()
    await provider.upload_file(b"a,b\n1,2\n", "train/data.csv")
    monkeypatch.setattr(
        provider, "download_file", Mock(side_effect=AssertionError("whole file read into memory"))
    )
    destination = tmp_path / "copy.csv"

    stored = f"{provider.get_base_path()}/train/data.csv"
    await provider.download_file_to_path(stored, str(destination))

    assert destination.read_bytes() == b"a,b\n1,2\n"


@pytest.mark.asyncio
async def test_local_provider_missing_file(tmp_path):
    provider = LocalFileSystemProvider(config={"base_path": str(tmp_path / "store")})
    await provider.initialize()
    with pytest.raises(FileNotFoundError):
        await provider.download_file_to_path(
            f"{provider.get_base_path()}/nope.csv", str(tmp_path / "copy.csv")
        )


def _s3_provider(client):
    config = {
        "AWS_BUCKET_NAME": "bucket",
        "AWS_ACCESS_KEY_ID": "k",
        "AWS_SECRET_ACCESS_KEY": "s",
        "AWS_REGION": "us-east-1",
    }
    with patch("app.modules.filemanager.providers.s3.provider.S3Client", return_value=client):
        provider = S3StorageProvider(config=config)
    provider.s3_client = client
    return provider


@pytest.mark.asyncio
async def test_s3_provider_streams_with_boto_download_file(tmp_path):
    client = Mock()
    client.download_file.return_value = True
    client.get_file_content.side_effect = AssertionError("whole object read into memory")
    provider = _s3_provider(client)

    await provider.download_file_to_path("train/data.parquet", str(tmp_path / "d.parquet"))

    client.download_file.assert_called_once_with("train/data.parquet", str(tmp_path / "d.parquet"))


@pytest.mark.asyncio
async def test_s3_provider_failed_download_returns_false(tmp_path):
    client = Mock()
    client.download_file.return_value = False
    provider = _s3_provider(client)
    assert await provider.download_file_to_path("train/x.csv", str(tmp_path / "x.csv")) is False
