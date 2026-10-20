"""Unit tests that CSV files are only read from inside the data volume."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.ml_utils import load_csv_file, resolve_csv_file_path
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode

CSV_CONTENT = "a,b\n1,2\n"


@pytest.fixture
def folders(tmp_path, monkeypatch):
    data_volume = tmp_path / "datavolume"
    outside = tmp_path / "outside"
    (data_volume / "train").mkdir(parents=True)
    outside.mkdir()
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", data_volume)
    monkeypatch.chdir(tmp_path)
    return SimpleNamespace(volume=data_volume, train=data_volume / "train", outside=outside)


def _write_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CSV_CONTENT)
    return path


def _error_key(call):
    with pytest.raises(AppException) as raised:
        call()
    return raised.value.error_key


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


@pytest.mark.parametrize("candidate", ["absolute_outside", "dot_dot_escape", "symlink_to_outside", "nul_byte"])
def test_paths_outside_the_data_volume_are_reported_as_not_found(folders, candidate):
    outside_csv = _write_csv(folders.outside / "secret.csv")
    link = folders.train / "link.csv"
    link.symlink_to(outside_csv)
    candidates = {
        "absolute_outside": str(outside_csv),
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
