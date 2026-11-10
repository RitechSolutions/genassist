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

import app
from app.core import project_path
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode

# The backend folder: only modules loaded from it (app code and tests) are
# redirected, never the standard library or installed packages.
_BACKEND_DIR = os.path.realpath(Path(app.__file__).parent.parent)


def _skip_registration(monkeypatch):
    register_signature = inspect.signature(TrainModelNode._register_trained_model)

    async def skip_registration(self, *args, **kwargs):
        # Still fail on a call that no longer matches the real method.
        register_signature.bind(self, *args, **kwargs)
        return None, None, None, []

    monkeypatch.setattr(TrainModelNode, "_register_trained_model", skip_registration)


def _redirected(value, data_volumes: tuple[str, ...], root: Path):
    """``value`` moved from the real data volume to ``root``, or None if it isn't a path in it."""
    if not isinstance(value, (str, Path)):
        return None
    text = str(value)
    for volume in data_volumes:
        if text == volume or text.startswith(volume + os.sep):
            target = root / text[len(volume):].lstrip(os.sep)
            return target if isinstance(value, Path) else str(target)
    return None


def _backend_modules():
    for module in list(sys.modules.values()):
        module_file = getattr(module, "__file__", None)
        if module_file and os.path.realpath(module_file).startswith(_BACKEND_DIR + os.sep):
            yield module


def training_sandbox(monkeypatch, root: Path) -> Path:
    """Use ``root`` as the data volume until the test ends."""
    # The models folder check compares real paths (macOS temp folders are symlinks).
    root = Path(os.path.realpath(root))
    original = project_path.DATA_VOLUME
    data_volumes = tuple(dict.fromkeys([str(original), os.path.realpath(original)]))
    # Modules bind DATA_VOLUME, and paths built from it (ML_MODELS_DIR,
    # ML_MODELS_UPLOAD_DIR and copies of those), when they are imported - test
    # modules included. Every such module-level value is redirected, found by
    # its value rather than a list of names, so a path added later is covered
    # too. project_path itself is left alone: a module first imported during
    # the test must bind the real path, not this test's temp folder, which is
    # gone after the test while the module keeps the binding.
    for module in _backend_modules():
        if module is project_path:
            continue
        for name, value in list(vars(module).items()):
            if name.startswith("__"):
                continue
            target = _redirected(value, data_volumes, root)
            if target is not None:
                monkeypatch.setattr(module, name, target)
    _skip_registration(monkeypatch)
    return root
