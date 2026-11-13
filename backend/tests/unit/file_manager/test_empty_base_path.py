"""A cleared File Manager Base Path means the default folder, not the working folder (MLP-15)."""

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import UploadFile

from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.schemas.file import FileBase
from app.core.utils.storage_path import configured_base_path
from app.modules.workflow.engine.nodes.ml.ml_utils import extra_csv_directories
from app.services.file_manager import FileManagerService


@pytest.mark.parametrize(
    "values",
    [
        {"base_path": ""},
        {"base_path": "   "},
        {"base_path": None},
        {},
        None,
        "not-a-dict",
    ],
)
def test_configured_base_path_treats_empty_as_unset(values):
    assert configured_base_path(values) is None


def test_configured_base_path_keeps_a_real_folder_as_stored():
    # Not trimmed: files already saved under a padded folder stay where they are.
    assert configured_base_path({"base_path": "/srv/files "}) == "/srv/files "
    assert configured_base_path({"base_path": "relative-store"}) == "relative-store"


@pytest.mark.parametrize("base_path", ["", "   ", None])
def test_local_provider_with_empty_base_path_uses_default_folder(tmp_path, monkeypatch, base_path):
    default = tmp_path / "data_volume"
    monkeypatch.setattr(LocalFileSystemProvider, "tmp_folder", str(default))
    monkeypatch.chdir(tmp_path)

    provider = LocalFileSystemProvider({"base_path": base_path})

    assert Path(provider.get_base_path()) == default


@pytest.fixture
def empty_settings(tmp_path, monkeypatch):
    """Default folder, a separate working folder, and File Manager Settings with Base Path cleared."""
    from app.dependencies import injector as injector_module
    from app.services.app_settings import AppSettingsService

    default = tmp_path / "data_volume"
    workdir = tmp_path / "backend"
    workdir.mkdir()
    monkeypatch.setattr(LocalFileSystemProvider, "tmp_folder", str(default))
    monkeypatch.chdir(workdir)
    row = SimpleNamespace(values={"file_manager_provider": "local", "base_path": ""})

    class FakeSettings:
        async def get_by_type_and_name(self, _type, _name):
            return row

    real_get = injector_module.injector.get
    monkeypatch.setattr(
        injector_module.injector,
        "get",
        lambda cls, *a, **kw: FakeSettings() if cls is AppSettingsService else real_get(cls, *a, **kw),
    )
    return default, workdir, row


def _service() -> FileManagerService:
    repository = AsyncMock()
    repository.create_file.side_effect = lambda file_data: file_data
    repository.is_path_shared = AsyncMock(return_value=False)
    return FileManagerService(repository)


async def _upload_model(row) -> object:
    """The model upload route: a provider built from File Manager Settings, then create_file."""
    service = _service()
    provider = await service.initialize(
        base_url="http://test", base_path=LocalFileSystemProvider.tmp_folder, app_settings=row
    )
    return await service.create_file(
        UploadFile(filename="model.pkl", file=io.BytesIO(b"model-bytes")),
        FileBase(
            name="model.pkl",
            path="ml_models",
            storage_provider="local",
            storage_path=provider.get_base_path(),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("base_path", ["", "   ", None])
async def test_upload_with_cleared_base_path_lands_in_default_folder(empty_settings, base_path):
    default, workdir, row = empty_settings
    row.values["base_path"] = base_path

    record = await _upload_model(row)

    assert (default / record.path).is_file()
    assert Path(record.storage_path) == default
    assert not (workdir / "ml_models").exists()


@pytest.mark.asyncio
async def test_cleared_base_path_upload_reads_downloads_and_deletes(empty_settings, tmp_path):
    default, workdir, row = empty_settings
    record = await _upload_model(row)
    stored = default / record.path

    # Register and predict read the model in a fresh request.
    assert await _service().get_file_content(record) == b"model-bytes"
    reader = _service()
    reader.repository.get_file_by_id = AsyncMock(return_value=record)
    destination = tmp_path / "out" / "model.pkl"
    await reader.download_file_to_path("file-id", str(destination))
    assert destination.read_bytes() == b"model-bytes"

    deleter = _service()
    deleter.repository.get_file_by_id = AsyncMock(return_value=record)
    deleter.repository.delete_file = AsyncMock()
    await deleter.delete_file("file-id")

    assert not stored.exists()
    deleter.repository.delete_file.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("base_path", ["", "   ", None])
async def test_training_csv_folders_ignore_a_cleared_base_path(base_path):
    settings = AsyncMock()
    settings.get_by_type_and_name.return_value = SimpleNamespace(
        values={"file_manager_provider": "local", "base_path": base_path}
    )

    assert await extra_csv_directories(settings) == []


@pytest.mark.asyncio
async def test_training_csv_folders_keep_a_real_base_path():
    settings = AsyncMock()
    settings.get_by_type_and_name.return_value = SimpleNamespace(
        values={"file_manager_provider": "local", "base_path": "/srv/files "}
    )

    assert await extra_csv_directories(settings) == [Path("/srv/files ")]
