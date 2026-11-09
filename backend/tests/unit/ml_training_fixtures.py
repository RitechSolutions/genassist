"""Helpers for tests that run TrainModelNode on real files.

Training only reads files inside the data volume, so these tests need a temp
folder there; and every trained model is saved under DATA_VOLUME/ml_models,
so the files are removed again after each test. Registering the model (the
file manager upload and the ml_models row) is skipped, so a run against a
real database leaves nothing behind either. Each test module wires them up
as its own fixtures:

    @pytest.fixture
    def tmp_path():
        with training_tmp_dir() as path:
            yield path

    @pytest.fixture(autouse=True)
    def _remove_trained_models(monkeypatch):
        with removing_trained_models(monkeypatch):
            yield
"""

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


def _remove_stale_tmp_dirs():
    if not _TMP_ROOT.is_dir():
        return
    cutoff = time.time() - _STALE_AFTER_SECONDS
    for folder in _TMP_ROOT.iterdir():
        try:
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass  # removed by another test meanwhile


@contextmanager
def training_tmp_dir():
    """A temp folder inside the data volume, removed afterwards."""
    _remove_stale_tmp_dirs()
    path = _TMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass  # another test's folder is still there


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

    async def skip_registration(self, *args, **kwargs):
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
