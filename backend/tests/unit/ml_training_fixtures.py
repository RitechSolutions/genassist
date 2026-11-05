"""Helpers for tests that run TrainModelNode on real files.

Training only reads files inside the data volume, so these tests need a temp
folder there; and every trained model is saved under DATA_VOLUME/ml_models,
so the files are removed again after each test. Each test module wires them up
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
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode


@contextmanager
def training_tmp_dir():
    """A temp folder inside the data volume, removed afterwards."""
    path = DATA_VOLUME / "_pytest_ml" / uuid.uuid4().hex
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
    """Delete the model files TrainModelNode saves while the block runs."""
    saved: list[Path] = []
    save_model = TrainModelNode._save_model

    async def recording_save_model(self, *args, **kwargs):
        result = await save_model(self, *args, **kwargs)
        saved.append(Path(result["model_file_path"]))
        return result

    monkeypatch.setattr(TrainModelNode, "_save_model", recording_save_model)
    try:
        yield
    finally:
        for file in saved:
            file.unlink(missing_ok=True)
            try:
                file.parent.rmdir()
            except OSError:
                pass  # the folder holds other files
