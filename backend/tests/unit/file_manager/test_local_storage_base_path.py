"""Local File Manager files are read from the folder they were saved under (MLP-11)."""

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile

from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.schemas.file import FileBase
from app.services.file_manager import FileManagerService


@pytest.fixture
def settings_folder(monkeypatch):
    """The File Manager Settings base_path the service looks up; a test sets .value."""
    holder = SimpleNamespace(value=None)

    async def lookup(_self):
        return holder.value

    monkeypatch.setattr(FileManagerService, "_settings_base_path", lookup)
    return holder


@pytest.fixture
def folders(tmp_path, monkeypatch, settings_folder):
    default = tmp_path / "data_volume"
    custom = tmp_path / "custom"
    monkeypatch.setattr(LocalFileSystemProvider, "tmp_folder", str(default))
    settings_folder.value = str(custom)
    return default, custom


def _service() -> FileManagerService:
    repository = AsyncMock()
    repository.create_file.side_effect = lambda file_data: file_data
    repository.is_path_shared = AsyncMock(return_value=False)
    return FileManagerService(repository)


async def _service_at(base_path: str) -> FileManagerService:
    """A service set up the way upload routes do it: provider built from File Manager Settings."""
    service = _service()
    settings = SimpleNamespace(values={"file_manager_provider": "local", "base_path": base_path})
    await service.initialize(
        base_url="http://test", base_path=LocalFileSystemProvider.tmp_folder, app_settings=settings
    )
    return service


async def _save(service: FileManagerService, content: bytes, storage_path: str | None = None, name="model.pkl"):
    return await service.create_file(
        UploadFile(filename=name, file=io.BytesIO(content)),
        FileBase(
            name=name,
            path="ml_models",
            storage_provider="local",
            storage_path=storage_path if storage_path is not None else service.storage_provider.get_base_path(),
        ),
    )


@pytest.mark.asyncio
async def test_file_saved_under_custom_base_path_reads_back(folders):
    _default, custom = folders
    record = await _save(await _service_at(str(custom)), b"custom-bytes")
    assert (custom / record.path).is_file()

    # A read runs in a fresh request, with no provider set up from settings.
    assert await _service().get_file_content(record) == b"custom-bytes"


@pytest.mark.asyncio
async def test_file_saved_under_custom_base_path_downloads_to_path(folders, tmp_path):
    _default, custom = folders
    record = await _save(await _service_at(str(custom)), b"custom-bytes")
    reader = _service()
    reader.repository.get_file_by_id = AsyncMock(return_value=record)
    destination = tmp_path / "out" / "model.pkl"

    await reader.download_file_to_path("file-id", str(destination))

    assert destination.read_bytes() == b"custom-bytes"


@pytest.mark.asyncio
async def test_default_base_path_reads_as_before(folders):
    default, _custom = folders
    record = await _save(await _service_at(str(default)), b"default-bytes")
    assert (default / record.path).is_file()

    assert await _service().get_file_content(record) == b"default-bytes"


@pytest.mark.asyncio
async def test_relative_base_path_reads_back(folders, settings_folder, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings_folder.value = "relative-store"
    writer = await _service_at("relative-store")
    record = await _save(writer, b"relative-bytes")
    assert (tmp_path / "relative-store" / record.path).is_file()

    # In a fresh request, and in the same request that saved it.
    assert await _service().get_file_content(record) == b"relative-bytes"
    assert await writer.get_file_content(record) == b"relative-bytes"


@pytest.mark.asyncio
async def test_new_local_upload_records_the_folder_it_wrote_to(folders):
    # The File Manager page sends the settings folder as storage_path, but a
    # service with no settings provider writes to the default folder.
    default, custom = folders
    custom.mkdir(parents=True)
    record = await _save(_service(), b"page-upload", storage_path=str(custom), name="notes.txt")

    assert (default / record.path).is_file()
    assert Path(record.storage_path).resolve() == default.resolve()
    assert await _service().get_file_content(record) == b"page-upload"


@pytest.mark.asyncio
async def test_legacy_record_naming_an_existing_folder_without_the_bytes_reads_from_default(folders):
    # Records written before this fix by the File Manager page name the
    # settings folder while the bytes sit in the default folder.
    default, custom = folders
    custom.mkdir(parents=True)
    record = await _save(_service(), b"legacy", storage_path="", name="notes.txt")
    record.storage_path = str(custom)
    assert (default / record.path).is_file()

    assert await _service().get_file_content(record) == b"legacy"
    # Also when the service was already set up at the settings folder.
    assert await (await _service_at(str(custom))).get_file_content(record) == b"legacy"


@pytest.mark.asyncio
async def test_reading_a_file_from_another_folder_does_not_move_later_writes(folders):
    # A file in the default folder is read by a request that writes to the
    # settings folder.
    default, custom = folders
    elsewhere = await _save(await _service_at(str(default)), b"other-bytes")

    service = await _service_at(str(custom))
    provider = service.storage_provider
    assert await service.get_file_content(elsewhere) == b"other-bytes"

    assert service.storage_provider is provider
    assert service.storage_provider.config.get("base_url") == "http://test"
    written = await _save(service, b"after-read", name="after.pkl")
    assert (custom / written.path).is_file()
    assert written.storage_path == provider.get_base_path()


@pytest.mark.asyncio
async def test_record_path_cannot_leave_its_folder(folders, tmp_path):
    _default, custom = folders
    custom.mkdir(parents=True)
    (tmp_path / "secret.txt").write_bytes(b"secret")
    record = SimpleNamespace(storage_provider="local", storage_path=str(custom), path="../secret.txt")

    with pytest.raises(ValueError, match="outside the storage folder"):
        await _service().get_file_content(record)


@pytest.mark.asyncio
async def test_record_naming_an_unknown_folder_is_not_read_or_deleted(folders, tmp_path):
    # Records once took storage_path and path from the request, so a record
    # can name any folder. Only known storage folders are used.
    host = tmp_path / "host"
    (host / "etc").mkdir(parents=True)
    secret = host / "etc" / "secret.txt"
    secret.write_bytes(b"host-secret")
    record = SimpleNamespace(id="x", storage_provider="local", storage_path=str(host), path="etc/secret.txt")

    with pytest.raises(FileNotFoundError):
        await _service().get_file_content(record)

    deleter = _service()
    deleter.repository.get_file_by_id = AsyncMock(return_value=record)
    deleter.repository.delete_file = AsyncMock()
    await deleter.delete_file("x")
    assert secret.read_bytes() == b"host-secret"


@pytest.mark.asyncio
async def test_delete_removes_file_from_custom_base_path(folders):
    _default, custom = folders
    record = await _save(await _service_at(str(custom)), b"custom-bytes")
    stored = custom / record.path
    deleter = _service()
    deleter.repository.get_file_by_id = AsyncMock(return_value=record)
    deleter.repository.delete_file = AsyncMock()

    await deleter.delete_file("file-id")

    assert not stored.exists()


@pytest.mark.asyncio
async def test_s3_reads_still_use_the_record_bucket():
    provider = MagicMock()
    provider.name = "s3"
    provider.initialize = AsyncMock()
    provider.is_initialized.return_value = True
    service = object.__new__(FileManagerService)
    service.storage_provider = None
    service.get_storage_provider_by_name = MagicMock(return_value=provider)
    record = SimpleNamespace(storage_provider="s3", storage_path="settings-bucket", path="a/b.csv")

    assert await service._provider_for_stored_file(record) is provider

    config = service.get_storage_provider_by_name.call_args.kwargs["config"]
    assert config["AWS_BUCKET_NAME"] == "settings-bucket"
    assert "base_path" not in config


# ---- The real File Manager Settings lookup (no stub of _settings_base_path) ----

@pytest.fixture
def real_lookup(tmp_path, monkeypatch):
    """Folders plus a fake AppSettingsService handed out by the injector."""
    from app.dependencies import injector as injector_module
    from app.services.app_settings import AppSettingsService

    default = tmp_path / "data_volume"
    custom = tmp_path / "custom"
    monkeypatch.setattr(LocalFileSystemProvider, "tmp_folder", str(default))
    state = SimpleNamespace(row=SimpleNamespace(values={"base_path": str(custom)}), error=None, calls=0)

    class FakeSettings:
        async def get_by_type_and_name(self, type_, name):
            state.calls += 1
            assert (type_, name) == ("FileManagerSettings", "File Manager Settings")
            if state.error:
                raise state.error
            return state.row

    real_get = injector_module.injector.get

    def fake_get(cls, *args, **kwargs):
        if cls is AppSettingsService:
            if state.error == "no-scope":
                raise RuntimeError("no request scope")
            return FakeSettings()
        return real_get(cls, *args, **kwargs)

    monkeypatch.setattr(injector_module.injector, "get", fake_get)
    return default, custom, state


async def _custom_record(custom: Path):
    service = _service()
    service.storage_provider = LocalFileSystemProvider({"base_path": str(custom)})
    await service.storage_provider.initialize()
    return await _save(service, b"custom-bytes")


@pytest.mark.asyncio
async def test_real_lookup_reads_from_the_settings_folder(real_lookup):
    _default, custom, state = real_lookup
    record = await _custom_record(custom)

    assert await _service().get_file_content(record) == b"custom-bytes"
    assert state.calls == 1


@pytest.mark.asyncio
async def test_real_lookup_without_a_settings_row_does_not_trust_the_folder(real_lookup):
    _default, custom, state = real_lookup
    record = await _custom_record(custom)
    state.row = None

    with pytest.raises(FileNotFoundError):
        await _service().get_file_content(record)


@pytest.mark.asyncio
async def test_real_lookup_ignores_values_that_are_not_a_folder(real_lookup):
    _default, custom, state = real_lookup
    record = await _custom_record(custom)
    state.row = SimpleNamespace(values="not-a-dict")

    with pytest.raises(FileNotFoundError):
        await _service().get_file_content(record)


@pytest.mark.asyncio
async def test_no_settings_service_falls_back_without_error(real_lookup):
    default, custom, state = real_lookup
    record = await _custom_record(custom)
    state.error = "no-scope"

    with pytest.raises(FileNotFoundError):
        await _service().get_file_content(record)
    # A file in the default folder still reads.
    default_record = await _save(_service(), b"default-bytes", storage_path="")
    assert await _service().get_file_content(default_record) == b"default-bytes"


@pytest.mark.asyncio
async def test_a_failed_settings_query_is_not_swallowed(real_lookup):
    _default, custom, state = real_lookup
    record = await _custom_record(custom)
    state.error = ConnectionError("database went away")

    with pytest.raises(ConnectionError):
        await _service().get_file_content(record)


@pytest.mark.asyncio
async def test_settings_are_not_queried_for_default_folder_records(real_lookup):
    _default, _custom, state = real_lookup
    record = await _save(_service(), b"default-bytes", storage_path="")

    assert await _service().get_file_content(record) == b"default-bytes"
    assert state.calls == 0


@pytest.mark.asyncio
async def test_without_a_usable_record_folder_the_request_folder_comes_before_default(real_lookup):
    # The order reads used before: the request's own folder, then the default.
    default, custom, _state = real_lookup
    for folder, content in ((default, b"in-default"), (custom, b"in-request-folder")):
        (folder / "uploads").mkdir(parents=True)
        (folder / "uploads" / "report.pdf").write_bytes(content)
    record = SimpleNamespace(storage_provider="local", storage_path="", path="uploads/report.pdf")

    service = await _service_at(str(custom))
    assert await service.get_file_content(record) == b"in-request-folder"
    assert await _service().get_file_content(record) == b"in-default"


@pytest.mark.asyncio
async def test_unusable_record_folder_falls_back_instead_of_raising(real_lookup):
    default, _custom, _state = real_lookup
    record = await _save(_service(), b"default-bytes", storage_path="")
    record.storage_path = "bad\0folder"

    assert await _service().get_file_content(record) == b"default-bytes"


@pytest.mark.asyncio
async def test_legacy_record_with_a_leading_slash_reads_and_deletes(folders):
    # The File Manager page once sent the folder as typed ('/docs'); the file
    # was written under the base folder and the record kept the slash.
    default, _custom = folders
    (default / "docs").mkdir(parents=True)
    stored = default / "docs" / "report.pdf"
    stored.write_bytes(b"legacy-slash")
    record = SimpleNamespace(id="x", storage_provider="local", storage_path=str(default), path="/docs/report.pdf")

    assert await _service().get_file_content(record) == b"legacy-slash"

    deleter = _service()
    deleter.repository.get_file_by_id = AsyncMock(return_value=record)
    deleter.repository.delete_file = AsyncMock()
    await deleter.delete_file("x")
    assert not stored.exists()


@pytest.mark.asyncio
async def test_local_path_upload_records_the_folder_it_wrote_to(folders, tmp_path):
    # The chunked-upload path (create_file_from_local_path) follows the same rule as create_file.
    default, custom = folders
    custom.mkdir(parents=True)
    source = tmp_path / "upload.csv"
    source.write_bytes(b"a,b\n1,2\n")

    record = await _service().create_file_from_local_path(
        str(source),
        FileBase(name="upload.csv", path="uploads", storage_provider="local", storage_path=str(custom)),
        original_filename="upload.csv",
        delete_source=False,
    )

    assert (default / record.path).is_file()
    assert Path(record.storage_path).resolve() == default.resolve()


@pytest.mark.asyncio
async def test_delete_stops_when_the_settings_lookup_fails(real_lookup):
    _default, custom, state = real_lookup
    record = await _custom_record(custom)
    stored = custom / record.path
    state.error = ConnectionError("database went away")
    deleter = _service()
    deleter.repository.get_file_by_id = AsyncMock(return_value=record)
    deleter.repository.delete_file = AsyncMock()

    with pytest.raises(ConnectionError):
        await deleter.delete_file("x")

    deleter.repository.delete_file.assert_not_awaited()
    assert stored.is_file()


@pytest.mark.asyncio
async def test_delete_keeps_bytes_shared_under_the_other_path_spelling(folders):
    # Two older records name one stored object, one with a leading '/'.
    default, _custom = folders
    (default / "docs").mkdir(parents=True)
    stored = default / "docs" / "a.pdf"
    stored.write_bytes(b"shared")
    record = SimpleNamespace(id="x", storage_provider="local", storage_path=str(default), path="/docs/a.pdf")
    deleter = _service()
    deleter.repository.get_file_by_id = AsyncMock(return_value=record)
    deleter.repository.delete_file = AsyncMock()
    deleter.repository.is_path_shared = AsyncMock(side_effect=lambda _id, _prov, path: path == "docs/a.pdf")

    await deleter.delete_file("x")

    assert stored.read_bytes() == b"shared"
    deleter.repository.delete_file.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_storage_setup_error_is_logged_and_the_record_still_deleted(folders, monkeypatch):
    default, _custom = folders
    record = await _save(_service(), b"default-bytes", storage_path="")
    deleter = _service()
    deleter.repository.get_file_by_id = AsyncMock(return_value=record)
    deleter.repository.delete_file = AsyncMock()

    async def broken(_self, _folder):
        raise PermissionError("read-only volume")

    monkeypatch.setattr(FileManagerService, "_local_provider_at", broken)
    await deleter.delete_file("x")

    deleter.repository.delete_file.assert_awaited_once()
    assert (default / record.path).is_file()


@pytest.mark.asyncio
async def test_settings_are_looked_up_once_per_service(real_lookup):
    _default, custom, state = real_lookup
    first = await _custom_record(custom)
    second = await _custom_record(custom)
    reader = _service()

    assert await reader.get_file_content(first) == b"custom-bytes"
    assert await reader.get_file_content(second) == b"custom-bytes"
    assert state.calls == 1
