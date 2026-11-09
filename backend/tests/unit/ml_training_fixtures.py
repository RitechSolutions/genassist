"""Helpers for tests that run TrainModelNode on real files.

Training only reads files inside the data volume, so these tests need a temp
folder there; and every trained model is saved under DATA_VOLUME/ml_models,
so the files are removed again after each test. Registering the model (the
file manager upload and the ml_models row) is skipped, so a run against a
real database adds no rows either. A run killed mid-test can still leave its
temp folder (swept on a later run) and its model file behind. Each test
module wires them up as its own fixtures:

    @pytest.fixture
    def tmp_path():
        with training_tmp_dir() as path:
            yield path

    @pytest.fixture(autouse=True)
    def _remove_trained_models(monkeypatch):
        with removing_trained_models(monkeypatch):
            yield
"""

import inspect
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode


_TMP_ROOT = DATA_VOLUME / "_pytest_ml"
# Folders older than this were left by a run that was killed before cleanup.
_STALE_AFTER_SECONDS = 6 * 60 * 60
_stale_dirs_removed = False


def _remove_stale_tmp_dirs():
    """Once per test run, remove temp folders a killed run left behind."""
    global _stale_dirs_removed
    if _stale_dirs_removed:
        return
    _stale_dirs_removed = True
    cutoff = time.time() - _STALE_AFTER_SECONDS
    try:
        folders = list(_TMP_ROOT.iterdir())
    except OSError:
        return  # no temp folders yet
    for folder in folders:
        try:
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass  # removed by another run meanwhile


@contextmanager
def training_tmp_dir():
    """A temp folder inside the data volume, removed afterwards."""
    _remove_stale_tmp_dirs()
    path = _TMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        # _TMP_ROOT itself stays: removing it could race with another run
        # (sharing the data volume) that is creating its folder inside it.
        shutil.rmtree(path, ignore_errors=True)


@contextmanager
def removing_trained_models(monkeypatch):
    """Delete the model files TrainModelNode saves while the block runs.

    Registration is skipped: it would upload another copy of the model and
    create an ml_models row that nothing removes afterwards.
    """
    saved: list[Path] = []
    save_model = TrainModelNode._save_model

    async def recording_save_model(self, *args, **kwargs):
        result = await save_model(self, *args, **kwargs)
        saved.append(Path(result["model_file_path"]))
        return result

    register_signature = inspect.signature(TrainModelNode._register_trained_model)

    async def skip_registration(self, *args, **kwargs):
        # Still fail on a call that no longer matches the real method.
        register_signature.bind(self, *args, **kwargs)
        return None, None, None, []

    monkeypatch.setattr(TrainModelNode, "_save_model", recording_save_model)
    monkeypatch.setattr(TrainModelNode, "_register_trained_model", skip_registration)
    try:
        yield
    finally:
        for file in saved:
            file.unlink(missing_ok=True)
            try:
                file.parent.rmdir()
            except OSError:
                pass  # the folder holds other files
