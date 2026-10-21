import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import ml_model as ml_model_schema
from app.schemas.ml_model import MLModelCreate, MLModelRead, MLModelUpdate, is_in_ml_models_dir
from app.core.exceptions.exception_classes import AppException
from app.services.ml_models import MLModelsService


@pytest.fixture
def ml_models_dir(tmp_path, monkeypatch):
    models_dir = tmp_path / "ml_models"
    models_dir.mkdir()
    monkeypatch.setattr(ml_model_schema, "ML_MODELS_DIR", str(models_dir))
    return models_dir


class TestIsInMlModelsDir:
    def test_file_inside(self, ml_models_dir):
        assert is_in_ml_models_dir(str(ml_models_dir / "model.pkl"))

    def test_file_in_subfolder(self, ml_models_dir):
        assert is_in_ml_models_dir(str(ml_models_dir / "thread" / "model.pkl"))

    def test_dot_dot_escape(self, ml_models_dir):
        assert not is_in_ml_models_dir(str(ml_models_dir / ".." / "secret.txt"))

    def test_absolute_path_outside(self, ml_models_dir):
        assert not is_in_ml_models_dir("/etc/passwd")

    def test_sibling_folder_with_same_prefix(self, ml_models_dir):
        assert not is_in_ml_models_dir(str(ml_models_dir) + "_other/model.pkl")

    def test_folder_itself(self, ml_models_dir):
        assert not is_in_ml_models_dir(str(ml_models_dir))

    def test_symlink_pointing_outside(self, ml_models_dir, tmp_path):
        target = tmp_path / "secret.txt"
        target.write_text("x")
        link = ml_models_dir / "link.pkl"
        os.symlink(target, link)
        assert not is_in_ml_models_dir(str(link))


class TestCreateValidator:
    def _create(self, pkl_file):
        return MLModelCreate(
            name="m", description="d", model_type="other", features=["a"],
            target_variable="t", pkl_file=pkl_file,
        )

    def test_accepts_path_inside(self, ml_models_dir):
        path = str(ml_models_dir / "model.pkl")
        assert self._create(path).pkl_file == path

    def test_accepts_none(self, ml_models_dir):
        assert self._create(None).pkl_file is None

    def test_rejects_path_outside(self, ml_models_dir):
        with pytest.raises(ValidationError):
            self._create("/etc/passwd")

    def test_rejects_dot_dot_escape(self, ml_models_dir):
        with pytest.raises(ValidationError):
            self._create(str(ml_models_dir / ".." / ".." / "app.db"))

    def test_read_accepts_stored_path_outside(self, ml_models_dir):
        # rows saved before the check, or by another deployment, must still list
        now = datetime.now()
        model = MLModelRead(id=uuid4(), created_at=now, updated_at=now, pkl_file="/src/datavolume/ml_models/x.pkl")
        assert model.pkl_file == "/src/datavolume/ml_models/x.pkl"


class TestUpdatePklFile:
    async def _update(self, stored_pkl_file, new_pkl_file):
        repository = AsyncMock()
        repository.get_by_name.return_value = None
        repository.get_by_id.return_value = SimpleNamespace(id=uuid4(), pkl_file=stored_pkl_file)
        await MLModelsService(repository).update(uuid4(), MLModelUpdate(pkl_file=new_pkl_file, description="new"))
        return repository

    @pytest.mark.asyncio
    async def test_accepts_new_path_inside(self, ml_models_dir):
        repository = await self._update(None, str(ml_models_dir / "model.pkl"))
        repository.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_new_path_outside(self, ml_models_dir):
        with pytest.raises(AppException):
            await self._update(str(ml_models_dir / "model.pkl"), "/etc/passwd")

    @pytest.mark.asyncio
    async def test_rejects_dot_dot_escape(self, ml_models_dir):
        with pytest.raises(AppException):
            await self._update(None, str(ml_models_dir / ".." / ".." / "app.db"))

    @pytest.mark.asyncio
    async def test_accepts_unchanged_stored_path_outside(self, ml_models_dir):
        # the edit form sends an older model's stored path back with a description change
        repository = await self._update("/src/datavolume/ml_models/x.pkl", "/src/datavolume/ml_models/x.pkl")
        repository.update.assert_awaited_once()


class TestDeleteKeepsFilesOutsideMlModelsDir:
    @pytest.mark.asyncio
    async def test_does_not_remove_file_outside(self, ml_models_dir, tmp_path):
        outside = tmp_path / "keep.txt"
        outside.write_text("x")
        repository = AsyncMock()
        # a row stored before pkl_file was validated
        repository.get_by_id.return_value = SimpleNamespace(pkl_file=str(outside), pkl_file_id=None)

        await MLModelsService(repository).delete(uuid4())

        assert outside.exists()
        repository.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_removes_file_inside(self, ml_models_dir):
        inside = ml_models_dir / "model.pkl"
        inside.write_text("x")
        repository = AsyncMock()
        repository.get_by_id.return_value = SimpleNamespace(pkl_file=str(inside), pkl_file_id=None)

        await MLModelsService(repository).delete(uuid4())

        assert not inside.exists()
        repository.delete.assert_awaited_once()


class TestUploadFilePath:
    async def _upload(self, base_path):
        from app.api.v1.routes.ml_models import upload_pkl_file

        storage_provider = SimpleNamespace(name="local", get_base_path=lambda: str(base_path))
        file_manager_service = AsyncMock()
        file_manager_service.initialize.return_value = storage_provider
        file_manager_service.create_file.return_value = SimpleNamespace(
            id=uuid4(), path="ml_models/abc.pkl", storage_provider="local"
        )
        file_manager_service.get_file_source_url.return_value = "http://test/file"
        request = SimpleNamespace(base_url="http://test/")
        upload = SimpleNamespace(filename="model.pkl", content_type="application/octet-stream")

        return await upload_pkl_file(
            request=request,
            file=upload,
            file_manager_service=file_manager_service,
            app_settings_svc=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_returns_file_path_inside_ml_models_dir(self, ml_models_dir):
        response = await self._upload(ml_models_dir.parent)
        assert response.file_path == f"{ml_models_dir.parent}/ml_models/abc.pkl"

    @pytest.mark.asyncio
    async def test_copies_file_outside_ml_models_dir_into_it(self, ml_models_dir, tmp_path, monkeypatch):
        # a custom file manager folder: the model gets a copy inside the ML models folder
        from app.api.v1.routes import ml_models as ml_models_routes

        monkeypatch.setattr(ml_models_routes, "ML_MODELS_UPLOAD_DIR", str(ml_models_dir))
        custom = tmp_path / "custom"
        (custom / "ml_models").mkdir(parents=True)
        (custom / "ml_models" / "abc.pkl").write_bytes(b"model")

        response = await self._upload(custom)

        assert response.file_path == str(ml_models_dir / f"{response.file_id}.pkl")
        assert (ml_models_dir / f"{response.file_id}.pkl").read_bytes() == b"model"
        assert is_in_ml_models_dir(response.file_path)
