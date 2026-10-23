"""Tests for provider-backed File Manager downloads."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.exception_classes import AppException
from app.services.file_manager import FileManagerService


def _service(provider: MagicMock) -> FileManagerService:
    service = object.__new__(FileManagerService)
    service.repository = MagicMock()
    service.repository.get_file_by_id = AsyncMock(
        return_value=SimpleNamespace(
            path="uploads/training.csv",
            storage_provider="s3",
            storage_path="settings-bucket",
        )
    )
    service.storage_provider = provider
    service._initialize_storage_provider = AsyncMock(return_value=provider)
    return service


@pytest.mark.asyncio
async def test_s3_download_streams_to_destination(tmp_path):
    async def download(_source, local_path):
        Path(local_path).write_text("id\n1\n", encoding="utf-8")
        return True

    provider = MagicMock()
    provider.is_initialized.return_value = True
    provider.download_file_to_path = AsyncMock(side_effect=download)
    service = _service(provider)
    destination = tmp_path / "training.csv"

    await service.download_file_to_path("file-id", str(destination))

    service._initialize_storage_provider.assert_awaited_once_with(
        "s3",
        "settings-bucket",
    )
    provider.download_file_to_path.assert_awaited_once()
    source, partial_path = provider.download_file_to_path.await_args.args
    assert source == "uploads/training.csv"
    assert partial_path.endswith(".part")
    assert destination.read_text(encoding="utf-8") == "id\n1\n"
    assert not Path(partial_path).exists()


@pytest.mark.asyncio
async def test_failed_s3_download_removes_partial_file(tmp_path):
    destination = tmp_path / "training.csv"
    destination.write_bytes(b"existing")

    async def fail_download(_source, local_path):
        destination_path = Path(local_path)
        destination_path.write_bytes(b"partial")
        raise RuntimeError("AccessDenied: secret bucket details")

    provider = MagicMock()
    provider.is_initialized.return_value = True
    provider.download_file_to_path = AsyncMock(side_effect=fail_download)
    service = _service(provider)

    with pytest.raises(AppException):
        await service.download_file_to_path("file-id", str(destination))

    assert destination.read_bytes() == b"existing"
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.asyncio
async def test_s3_provider_uses_bucket_from_file_manager_record():
    provider = MagicMock()
    provider.name = "s3"
    provider.initialize = AsyncMock()
    provider.is_initialized.return_value = True
    provider.get_base_path.return_value = "settings-bucket"

    service = object.__new__(FileManagerService)
    service.storage_provider = None
    service.get_storage_provider_by_name = MagicMock(return_value=provider)

    await service._initialize_storage_provider("s3", "settings-bucket")

    config = service.get_storage_provider_by_name.call_args.kwargs["config"]
    assert config["AWS_BUCKET_NAME"] == "settings-bucket"
