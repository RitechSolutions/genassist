"""training_sandbox redirects every models-folder path, not a hand-kept list."""

import os
from pathlib import Path

import pytest

from app.api.v1.routes import ml_models as ml_models_routes
from app.core import project_path
from app.core.utils import model_validator
from app.schemas import ml_model as ml_model_schema
from app.services import ml_model_manager
from app.services import ml_models as ml_models_service
from tests.unit.ml_training_fixtures import training_sandbox

MODELS_FOLDER_PATHS = [
    (model_validator, "ML_MODELS_DIR"),
    (ml_model_schema, "ML_MODELS_DIR"),
    (ml_model_manager, "ML_MODELS_UPLOAD_DIR"),
    (ml_models_service, "ML_MODELS_UPLOAD_DIR"),
    (ml_models_routes, "ML_MODELS_UPLOAD_DIR"),
]


@pytest.mark.parametrize("module, name", MODELS_FOLDER_PATHS)
def test_models_folder_paths_point_into_the_sandbox(monkeypatch, tmp_path, module, name):
    before = getattr(module, name)
    root = training_sandbox(monkeypatch, tmp_path)

    assert getattr(module, name) == str(root / "ml_models")
    monkeypatch.undo()
    assert getattr(module, name) == before


def test_data_volume_copies_keep_their_type(monkeypatch, tmp_path):
    root = training_sandbox(monkeypatch, tmp_path)

    assert ml_models_routes.DATA_VOLUME == root
    assert isinstance(ml_models_routes.DATA_VOLUME, Path)
    # project_path keeps the real path for modules imported during the test.
    assert project_path.DATA_VOLUME != root
    assert os.path.realpath(root) == str(root)
