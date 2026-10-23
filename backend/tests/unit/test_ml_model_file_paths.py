"""Unit tests that ML model files are only read from inside the ML models folder."""

from __future__ import annotations

import os
import pickle
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.exception_classes import AppException
from app.core.utils import model_validator
from app.core.utils.model_validator import get_model_info, resolve_model_path, validate_pickle_file_safe
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import MLModelInferenceNode
from app.services import ml_model_manager
from app.services.ml_model_manager import _load_pickle_sync, download_model_file


@pytest.fixture
def folders(tmp_path, monkeypatch):
    models_dir = tmp_path / "datavolume" / "ml_models"
    outside_dir = tmp_path / "outside"
    models_dir.mkdir(parents=True)
    outside_dir.mkdir()
    monkeypatch.setattr(model_validator, "ML_MODELS_DIR", os.path.realpath(models_dir))
    monkeypatch.setattr(ml_model_manager, "ML_MODELS_UPLOAD_DIR", str(models_dir))
    return SimpleNamespace(models=models_dir, outside=outside_dir, root=tmp_path)


@pytest.fixture
def downloads(monkeypatch):
    requested_paths = []

    async def fake_download(file_id, destination_path):
        requested_paths.append(destination_path)
        return _write_pickle(Path(destination_path), {"file_id": file_id})

    monkeypatch.setattr(ml_model_manager, "download_pkl_file", fake_download)
    return requested_paths


def _write_pickle(path: Path, payload=None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(payload if payload is not None else {"weights": [1, 2, 3]}))
    return str(path)


def _model(pkl_file=None, pkl_file_id=None, name="model"):
    return SimpleNamespace(id=uuid.uuid4(), name=name, pkl_file=pkl_file, pkl_file_id=pkl_file_id)


def _node():
    return MLModelInferenceNode("ml1", {"type": "mlModelInferenceNode", "data": {}}, MagicMock())


def test_resolve_model_path_accepts_a_file_inside_the_models_folder(folders):
    inside_file = _write_pickle(folders.models / "model.pkl")

    assert resolve_model_path(inside_file) == os.path.realpath(inside_file)


@pytest.mark.parametrize(
    "candidate",
    ["dot_dot_escape", "absolute_outside", "look_alike_folder", "symlink_to_outside", "empty", "none"],
)
def test_resolve_model_path_rejects_paths_outside_the_models_folder(folders, candidate):
    outside_file = _write_pickle(folders.outside / "secret.pkl")
    look_alike_file = _write_pickle(folders.root / "datavolume" / "ml_models_evil" / "model.pkl")
    symlink = folders.models / "link.pkl"
    symlink.symlink_to(outside_file)
    candidates = {
        "dot_dot_escape": str(folders.models / ".." / ".." / "outside" / "secret.pkl"),
        "absolute_outside": outside_file,
        "look_alike_folder": look_alike_file,
        "symlink_to_outside": str(symlink),
        "empty": "",
        "none": None,
    }

    assert resolve_model_path(candidates[candidate]) is None


def test_validator_refuses_a_file_outside_the_models_folder_without_naming_it(folders):
    outside_file = _write_pickle(folders.outside / "secret.pkl")

    assert validate_pickle_file_safe(outside_file) == (False, "Model file is not inside the ML models folder")


def test_validator_accepts_a_pickle_inside_the_models_folder(folders):
    inside_file = _write_pickle(folders.models / "model.pkl")

    assert validate_pickle_file_safe(inside_file) == (True, None)


def test_validator_treats_a_folder_as_a_missing_file(folders):
    (folders.models / "thread-1").mkdir()

    assert validate_pickle_file_safe(str(folders.models / "thread-1")) == (False, "Model file not found")


def test_model_info_reveals_nothing_about_files_outside_the_models_folder(folders):
    info = get_model_info(_write_pickle(folders.outside / "secret.pkl"))

    assert info["file_exists"] is False
    assert info["file_size"] == 0
    assert info["is_valid"] is False
    assert info["error"] == "Model file is not inside the ML models folder"


def test_unpickling_refuses_a_file_outside_the_models_folder(folders):
    with pytest.raises(ValueError, match="not inside the ML models folder"):
        _load_pickle_sync(_write_pickle(folders.outside / "secret.pkl"))


@pytest.mark.asyncio
async def test_download_writes_a_temporary_file_then_renames_it_into_the_folder(folders, downloads):
    model_id = uuid.uuid4()

    path = await download_model_file(model_id, "file-1")

    assert Path(path).parent == folders.models
    assert Path(path).name.startswith(f"{model_id}_")
    assert os.path.isfile(path)
    assert len(downloads) == 1
    assert downloads[0].endswith(".part")
    assert not list(folders.models.glob("*.part"))


@pytest.mark.asyncio
async def test_download_reuses_a_file_that_is_already_in_the_folder(folders, downloads):
    model_id = uuid.uuid4()

    first = await download_model_file(model_id, "file-1")
    second = await download_model_file(model_id, "file-1")

    assert first == second
    assert len(downloads) == 1


@pytest.mark.asyncio
async def test_a_reuploaded_file_gets_a_new_name(folders, downloads):
    model_id = uuid.uuid4()

    first = await download_model_file(model_id, "file-1")
    second = await download_model_file(model_id, "file-2")

    assert first != second
    assert len(downloads) == 2


@pytest.mark.asyncio
async def test_a_failed_download_leaves_no_partial_file(folders, monkeypatch):
    async def failing_download(file_id, destination_path):
        Path(destination_path).write_bytes(b"half")
        raise ConnectionError("storage unavailable")

    monkeypatch.setattr(ml_model_manager, "download_pkl_file", failing_download)

    with pytest.raises(ConnectionError):
        await download_model_file(uuid.uuid4(), "file-1")

    assert list(folders.models.iterdir()) == []


@pytest.mark.asyncio
async def test_node_refetches_a_file_outside_the_folder_by_its_receipt(folders, downloads):
    ml_model = _model(pkl_file=_write_pickle(folders.outside / "secret.pkl"), pkl_file_id="file-1")
    ml_service = AsyncMock()

    await _node()._ensure_pkl_file(ml_model, ml_service)

    assert Path(ml_model.pkl_file).parent == folders.models
    assert ml_service.update.await_args.args[1].pkl_file == ml_model.pkl_file


@pytest.mark.asyncio
async def test_node_uses_a_file_inside_the_folder_as_is(folders, downloads):
    inside_file = _write_pickle(folders.models / "model.pkl")
    ml_model = _model(pkl_file=inside_file, pkl_file_id="file-1")

    await _node()._ensure_pkl_file(ml_model, AsyncMock())

    assert ml_model.pkl_file == inside_file
    assert downloads == []


@pytest.mark.asyncio
async def test_node_refuses_a_file_outside_the_folder_without_a_receipt(folders, downloads):
    ml_model = _model(pkl_file=_write_pickle(folders.outside / "secret.pkl"))

    with pytest.raises(AppException):
        await _node()._ensure_pkl_file(ml_model, AsyncMock())

    assert downloads == []


@pytest.mark.asyncio
async def test_a_model_name_with_dot_dot_cannot_move_the_download_outside_the_folder(folders, downloads):
    ml_model = _model(pkl_file="my-bucket/ml_models/remote.pkl", pkl_file_id="file-1", name="../../escape")

    await _node()._ensure_pkl_file(ml_model, AsyncMock())

    assert resolve_model_path(ml_model.pkl_file) is not None


def test_unpickling_loads_a_file_inside_the_models_folder(folders):
    assert _load_pickle_sync(_write_pickle(folders.models / "model.pkl", {"weights": [1]})) == {"weights": [1]}


def test_model_info_without_a_local_file_says_file_not_found(folders):
    assert get_model_info(None)["error"] == "File not found"


@pytest.mark.asyncio
async def test_download_removes_only_stale_partial_files(folders, downloads):
    model_id = uuid.uuid4()
    destination = ml_model_manager._downloaded_model_path(model_id, "file-1")
    stale_part = Path(f"{destination}.old.part")
    fresh_part = Path(f"{destination}.new.part")
    stale_part.write_bytes(b"old")
    fresh_part.write_bytes(b"new")
    two_hours_ago = time.time() - 7200
    os.utime(stale_part, (two_hours_ago, two_hours_ago))

    await download_model_file(model_id, "file-1")

    assert not stale_part.exists()
    assert fresh_part.exists()


@pytest.mark.asyncio
async def test_node_does_not_save_an_unchanged_path_again(folders, downloads):
    ml_model = _model(pkl_file_id="file-1")
    ml_model.pkl_file = ml_model_manager._downloaded_model_path(ml_model.id, "file-1")
    ml_service = AsyncMock()

    await _node()._ensure_pkl_file(ml_model, ml_service)

    assert os.path.isfile(ml_model.pkl_file)
    ml_service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_rejects_a_model_id_that_is_not_a_uuid(folders, downloads):
    with pytest.raises(ValueError):
        await download_model_file("../../escape", "file-1")

    assert downloads == []


@pytest.mark.asyncio
async def test_node_downloads_again_when_the_receipt_changed_but_an_old_copy_is_in_the_folder(folders, downloads):
    ml_model = _model(pkl_file_id="file-2")
    old_copy = _write_pickle(Path(ml_model_manager._downloaded_model_path(ml_model.id, "file-1")))
    ml_model.pkl_file = old_copy
    ml_service = AsyncMock()

    await _node()._ensure_pkl_file(ml_model, ml_service)

    assert ml_model.pkl_file == ml_model_manager._downloaded_model_path(ml_model.id, "file-2")
    assert len(downloads) == 1
    ml_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_node_keeps_a_direct_upload_even_when_a_receipt_is_present(folders, downloads):
    inside_file = _write_pickle(folders.models / f"{uuid.uuid4()}.pkl")
    ml_model = _model(pkl_file=inside_file, pkl_file_id="file-9")

    await _node()._ensure_pkl_file(ml_model, AsyncMock())

    assert ml_model.pkl_file == inside_file
    assert downloads == []


@pytest.mark.asyncio
async def test_a_model_stored_outside_validates_after_fetching_it_by_receipt(folders, downloads):
    ml_model = _model(pkl_file="my-bucket/ml_models/remote.pkl", pkl_file_id="file-1")

    local_path = await ml_model_manager.local_model_file(ml_model, AsyncMock())

    assert local_path is not None
    assert validate_pickle_file_safe(ml_model.pkl_file) == (True, None)
    assert get_model_info(ml_model.pkl_file)["is_valid"] is True


@pytest.mark.asyncio
async def test_node_replaces_a_copy_downloaded_by_an_older_release_when_the_receipt_changed(folders, downloads):
    ml_model = _model(pkl_file_id="file-2")
    ml_model.pkl_file = _write_pickle(folders.models / f"{ml_model.name}_{ml_model.id}.pkl")

    await _node()._ensure_pkl_file(ml_model, AsyncMock())

    assert ml_model.pkl_file == ml_model_manager._downloaded_model_path(ml_model.id, "file-2")
    assert len(downloads) == 1
