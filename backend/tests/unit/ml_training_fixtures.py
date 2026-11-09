"""Helpers for tests that run TrainModelNode on real files.

Training only reads files inside the data volume and saves every model under
DATA_VOLUME/ml_models. ``training_sandbox`` points the data volume at pytest's
own temp folder for the test, so the CSVs the test writes are readable and the
trained models land there too. Nothing touches the real data volume, and pytest
cleans the folder up, even after a run that was killed mid-test.

Registering the model (the file manager upload and the ml_models row) is
skipped, so a run against a real database adds no rows either.

Each test module wires it up as an autouse fixture:

    @pytest.fixture(autouse=True)
    def _training_sandbox(monkeypatch, tmp_path):
        with training_sandbox(monkeypatch, tmp_path):
            yield
"""

import inspect
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from app.core import project_path
from app.core.utils import model_validator
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.services import ml_model_manager


def _skip_registration(monkeypatch):
    register_signature = inspect.signature(TrainModelNode._register_trained_model)

    async def skip_registration(self, *args, **kwargs):
        # Still fail on a call that no longer matches the real method.
        register_signature.bind(self, *args, **kwargs)
        return None, None, None, []

    monkeypatch.setattr(TrainModelNode, "_register_trained_model", skip_registration)


@contextmanager
def training_sandbox(monkeypatch, root: Path):
    """Use ``root`` as the data volume while the block runs."""
    # The models folder check compares real paths (macOS temp folders are symlinks).
    root = Path(os.path.realpath(root))
    original = project_path.DATA_VOLUME
    # Modules bind DATA_VOLUME at import, test modules included, so patch every copy.
    for module in list(sys.modules.values()):
        if getattr(module, "__dict__", {}).get("DATA_VOLUME") is original:
            monkeypatch.setattr(module, "DATA_VOLUME", root)
    models_dir = str(root / "ml_models")
    monkeypatch.setattr(model_validator, "ML_MODELS_DIR", models_dir)
    monkeypatch.setattr(ml_model_manager, "ML_MODELS_UPLOAD_DIR", models_dir)
    _skip_registration(monkeypatch)
    yield root
