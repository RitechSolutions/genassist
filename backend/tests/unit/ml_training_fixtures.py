"""Helpers for tests that run TrainModelNode on real files.

Training only reads files inside the data volume and saves every model under
DATA_VOLUME/ml_models. ``training_sandbox`` points the data volume at pytest's
own temp folder for the test, so the CSVs the test writes are readable and the
trained models land there too. Nothing touches the real data volume, and pytest
cleans the folder up, even after a run that was killed mid-test.

Registering the model (the file manager upload and the ml_models row) is
skipped, so a run against a real database adds no rows either.

Call it from a test, or wire it up for a whole module:

    @pytest.fixture(autouse=True)
    def _training_sandbox(monkeypatch, tmp_path):
        training_sandbox(monkeypatch, tmp_path)
"""

import inspect
import os
import sys
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


def training_sandbox(monkeypatch, root: Path) -> Path:
    """Use ``root`` as the data volume until the test ends."""
    # The models folder check compares real paths (macOS temp folders are symlinks).
    root = Path(os.path.realpath(root))
    original = project_path.DATA_VOLUME
    # Modules bind DATA_VOLUME at import, test modules included, so patch every
    # copy. project_path itself is left alone: a module first imported during
    # the test must bind the real path, not this test's temp folder, which is
    # gone after the test while the module keeps the binding.
    for module in list(sys.modules.values()):
        if module is project_path:
            continue
        if getattr(module, "__dict__", {}).get("DATA_VOLUME") is original:
            monkeypatch.setattr(module, "DATA_VOLUME", root)
    models_dir = str(root / "ml_models")
    monkeypatch.setattr(model_validator, "ML_MODELS_DIR", models_dir)
    monkeypatch.setattr(ml_model_manager, "ML_MODELS_UPLOAD_DIR", models_dir)
    _skip_registration(monkeypatch)
    return root
