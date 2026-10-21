"""Unit tests that CSV files are only read from inside the data volume or the configured storage folder."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.ml_utils import extra_csv_directories, load_csv_file, resolve_csv_file_path
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode

CSV_CONTENT = "a,b\n1,2\n"


@pytest.fixture
def folders(tmp_path, monkeypatch):
    data_volume = tmp_path / "datavolume"
    outside = tmp_path / "outside"
    storage = tmp_path / "storage"
    (data_volume / "train").mkdir(parents=True)
    outside.mkdir()
    storage.mkdir()
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", data_volume)
    monkeypatch.setattr(ml_utils, "extra_csv_directories", AsyncMock(return_value=[]))
    monkeypatch.chdir(tmp_path)
    return SimpleNamespace(volume=data_volume, train=data_volume / "train", outside=outside, storage=storage)


def _write_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CSV_CONTENT)
    return path


def _error_key(call):
    with pytest.raises(AppException) as raised:
        call()
    return raised.value.error_key


def _settings_service(values):
    setting = None if values is None else SimpleNamespace(values=values)
    return SimpleNamespace(get_by_type_and_name=AsyncMock(return_value=setting))


def test_an_absolute_path_inside_the_data_volume_is_resolved(folders):
    csv = _write_csv(folders.train / "data.csv")

    assert resolve_csv_file_path(str(csv)) == csv.resolve()


def test_a_relative_name_is_found_in_the_train_folder(folders):
    csv = _write_csv(folders.train / "data.csv")

    assert resolve_csv_file_path("data.csv") == csv.resolve()


def test_a_relative_name_is_found_in_the_thread_folder(folders):
    csv = _write_csv(folders.train / "thread-1" / "data.csv")

    assert resolve_csv_file_path("data.csv", thread_id="thread-1") == csv.resolve()


def test_a_relative_name_is_found_directly_in_the_data_volume(folders):
    csv = _write_csv(folders.volume / "data.csv")

    assert resolve_csv_file_path("data.csv") == csv.resolve()


def test_a_relative_name_is_found_in_the_current_folder_inside_the_data_volume(folders, monkeypatch):
    csv = _write_csv(folders.volume / "exports" / "data.csv")
    monkeypatch.chdir(csv.parent)

    assert resolve_csv_file_path("data.csv") == csv.resolve()


def test_a_file_name_containing_two_dots_is_allowed(folders):
    csv = _write_csv(folders.train / "sales..2024.csv")

    assert resolve_csv_file_path(str(csv)) == csv.resolve()


def test_a_csv_in_the_configured_storage_folder_is_allowed(folders):
    csv = _write_csv(folders.storage / "uploads" / "data.csv")

    assert _error_key(lambda: resolve_csv_file_path(str(csv))) == ErrorKey.FILE_NOT_FOUND
    assert resolve_csv_file_path(str(csv), allowed_directories=[folders.storage]) == csv.resolve()


@pytest.mark.parametrize("candidate", ["absolute_outside", "sibling_folder", "dot_dot_escape", "symlink_to_outside", "nul_byte"])
def test_paths_outside_the_data_volume_are_reported_as_not_found(folders, candidate):
    outside_csv = _write_csv(folders.outside / "secret.csv")
    link = folders.train / "link.csv"
    link.symlink_to(outside_csv)
    candidates = {
        "absolute_outside": str(outside_csv),
        "sibling_folder": str(_write_csv(folders.volume.parent / "datavolume2" / "secret.csv")),
        "dot_dot_escape": str(folders.train / ".." / ".." / "outside" / "secret.csv"),
        "symlink_to_outside": str(link),
        "nul_byte": str(folders.train / "data\x00.csv"),
    }

    assert _error_key(lambda: resolve_csv_file_path(candidates[candidate])) == ErrorKey.FILE_NOT_FOUND


def test_a_relative_name_cannot_escape_with_dot_dot(folders):
    _write_csv(folders.outside / "secret.csv")

    assert _error_key(lambda: resolve_csv_file_path("../outside/secret.csv")) == ErrorKey.FILE_NOT_FOUND


def test_a_thread_id_cannot_escape_the_data_volume(folders):
    _write_csv(folders.outside / "secret.csv")

    assert _error_key(lambda: resolve_csv_file_path("secret.csv", thread_id="../../outside")) == ErrorKey.FILE_NOT_FOUND


def test_a_storage_folder_does_not_open_the_rest_of_the_disk(folders):
    outside_csv = _write_csv(folders.outside / "secret.csv")

    assert _error_key(lambda: resolve_csv_file_path(str(outside_csv), allowed_directories=[folders.storage])) == ErrorKey.FILE_NOT_FOUND


def test_a_missing_file_is_reported_as_not_found(folders):
    assert _error_key(lambda: resolve_csv_file_path("missing.csv")) == ErrorKey.FILE_NOT_FOUND


def test_a_non_csv_file_inside_the_data_volume_is_refused(folders):
    text_file = folders.train / "notes.txt"
    text_file.write_text("hello")

    assert _error_key(lambda: resolve_csv_file_path(str(text_file))) == ErrorKey.INTERNAL_ERROR


def test_loading_a_csv_outside_the_data_volume_is_refused(folders):
    outside_csv = _write_csv(folders.outside / "secret.csv")

    assert _error_key(lambda: load_csv_file(str(outside_csv))) == ErrorKey.FILE_NOT_FOUND


def test_loading_a_csv_inside_the_data_volume_works(folders):
    _write_csv(folders.train / "data.csv")

    data, df = load_csv_file("data.csv")

    assert data == [{"a": 1, "b": 2}]
    assert len(df) == 1


@pytest.mark.asyncio
async def test_extra_csv_directories_is_the_local_storage_folder_when_one_is_set():
    service = _settings_service({"file_manager_provider": "local", "base_path": "/srv/genassist-files"})

    assert await extra_csv_directories(service) == [Path("/srv/genassist-files")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values",
    [
        None,
        {},
        {"file_manager_provider": "s3", "base_path": "/srv/genassist-files"},
        {"file_manager_provider": "local", "base_path": ""},
        {"file_manager_provider": "local", "base_path": 123},
    ],
)
async def test_extra_csv_directories_is_empty_without_a_local_storage_folder(values):
    assert await extra_csv_directories(_settings_service(values)) == []


@pytest.mark.asyncio
async def test_extra_csv_directories_is_empty_when_the_settings_cannot_be_read():
    service = SimpleNamespace(get_by_type_and_name=AsyncMock(side_effect=RuntimeError("database down")))

    assert await extra_csv_directories(service) == []


def _data_source_node():
    state = MagicMock()
    state.thread_id = "thread-1"
    return TrainDataSourceNode("ds1", {"type": "trainDataSourceNode", "data": {}}, state)


@pytest.mark.asyncio
async def test_train_data_source_node_refuses_a_file_outside_the_data_volume(folders):
    outside_csv = _write_csv(folders.outside / "secret.csv")

    with pytest.raises(AppException) as raised:
        await _data_source_node()._process_csv_source({"csvFilePath": str(outside_csv)})

    assert raised.value.error_key == ErrorKey.FILE_NOT_FOUND


@pytest.mark.asyncio
async def test_train_data_source_node_reads_a_file_inside_the_data_volume(folders):
    csv = _write_csv(folders.train / "data.csv")

    result = await _data_source_node()._process_csv_source({"csvFilePath": str(csv)})

    assert result["success"] is True
    assert result["metadata"]["rowCount"] == 1
    assert result["metadata"]["columns"] == ["a", "b"]


@pytest.mark.asyncio
async def test_train_data_source_node_reads_a_file_in_the_configured_storage_folder(folders, monkeypatch):
    csv = _write_csv(folders.storage / "uploads" / "data.csv")
    monkeypatch.setattr(ml_utils, "extra_csv_directories", AsyncMock(return_value=[folders.storage]))

    result = await _data_source_node()._process_csv_source({"csvFilePath": str(csv)})

    assert result["success"] is True
    assert result["metadata"]["rowCount"] == 1
