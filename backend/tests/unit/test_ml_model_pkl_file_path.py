import os
import re
import time
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


class TestUploadRemovesFileWhenItFailsAfterStoring:
    """The client never gets the id of a .pkl whose upload failed, so the route removes it."""

    def _file_manager(self, base_path, file_id):
        file_manager_service = AsyncMock()
        file_manager_service.initialize.return_value = SimpleNamespace(
            name="local", get_base_path=lambda: str(base_path)
        )
        file_manager_service.create_file.return_value = SimpleNamespace(
            id=file_id, path="ml_models/abc.pkl", storage_provider="local"
        )
        file_manager_service.get_file_source_url.return_value = "http://test/file"
        return file_manager_service

    async def _upload(self, file_manager_service):
        from app.api.v1.routes.ml_models import upload_pkl_file

        return await upload_pkl_file(
            request=SimpleNamespace(base_url="http://test/"),
            file=SimpleNamespace(filename="model.pkl", content_type="application/octet-stream"),
            file_manager_service=file_manager_service,
            app_settings_svc=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_source_url_failure_deletes_the_stored_file(self, ml_models_dir):
        from fastapi import HTTPException

        file_id = uuid4()
        file_manager_service = self._file_manager(ml_models_dir.parent, file_id)
        file_manager_service.get_file_source_url.side_effect = RuntimeError("storage not ready")

        with pytest.raises(HTTPException) as exc:
            await self._upload(file_manager_service)

        assert exc.value.status_code == 500
        file_manager_service.delete_file.assert_awaited_once_with(file_id)

    @pytest.mark.asyncio
    async def test_failed_copy_deletes_the_stored_file_and_the_partial_copy(
        self, ml_models_dir, tmp_path, monkeypatch
    ):
        from fastapi import HTTPException
        from app.api.v1.routes import ml_models as ml_models_routes

        monkeypatch.setattr(ml_models_routes, "ML_MODELS_UPLOAD_DIR", str(ml_models_dir))
        file_id = uuid4()
        copy_path = ml_models_dir / f"{file_id}.pkl"

        def failing_copy(src, dst):
            open(dst, "wb").close()  # a partial copy is left behind before the failure
            raise OSError("disk full")

        monkeypatch.setattr(ml_models_routes.shutil, "copyfile", failing_copy)
        # A custom File Manager folder, so the route copies the file into the ML models folder.
        file_manager_service = self._file_manager(tmp_path / "custom", file_id)

        with pytest.raises(HTTPException):
            await self._upload(file_manager_service)

        file_manager_service.delete_file.assert_awaited_once_with(file_id)
        assert not copy_path.exists()

    @pytest.mark.asyncio
    async def test_cancelled_request_still_deletes_the_stored_file(self, ml_models_dir):
        import asyncio

        file_id = uuid4()
        file_manager_service = self._file_manager(ml_models_dir.parent, file_id)
        file_manager_service.get_file_source_url.side_effect = asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await self._upload(file_manager_service)

        file_manager_service.delete_file.assert_awaited_once_with(file_id)

    @pytest.mark.asyncio
    async def test_cleanup_finishes_inside_a_cancelled_anyio_scope(self, ml_models_dir):
        """Starlette cancels through anyio scopes, which cancel every later await too."""
        import anyio

        file_id = uuid4()
        file_manager_service = self._file_manager(ml_models_dir.parent, file_id)
        started = anyio.Event()
        deleted = []

        async def hanging_source_url(_):
            started.set()
            await anyio.sleep_forever()

        async def delete_file(fid):
            await anyio.sleep(0)  # an await inside the cleanup, like the real DB lookup
            deleted.append(fid)

        file_manager_service.get_file_source_url.side_effect = hanging_source_url
        file_manager_service.delete_file.side_effect = delete_file

        async with anyio.create_task_group() as tg:
            tg.start_soon(self._upload, file_manager_service)
            await started.wait()
            tg.cancel_scope.cancel()

        assert deleted == [file_id]

    @pytest.mark.asyncio
    async def test_cleanup_failure_still_reports_the_upload_error(self, ml_models_dir):
        from fastapi import HTTPException

        file_manager_service = self._file_manager(ml_models_dir.parent, uuid4())
        file_manager_service.get_file_source_url.side_effect = RuntimeError("storage not ready")
        file_manager_service.delete_file.side_effect = RuntimeError("delete failed too")

        with pytest.raises(HTTPException) as exc:
            await self._upload(file_manager_service)

        assert "storage not ready" in exc.value.detail

    @pytest.mark.asyncio
    async def test_cancel_during_the_copy_leaves_no_copy_behind(self, ml_models_dir, tmp_path, monkeypatch):
        """A cancelled request doesn't stop the copy thread, so the cleanup waits for it."""
        import threading

        import anyio
        from app.api.v1.routes import ml_models as ml_models_routes

        monkeypatch.setattr(ml_models_routes, "ML_MODELS_UPLOAD_DIR", str(ml_models_dir))
        file_id = uuid4()
        copy_path = ml_models_dir / f"{file_id}.pkl"
        copy_started, copy_done = threading.Event(), threading.Event()

        def slow_copy(src, dst):
            copy_started.set()
            time.sleep(0.3)  # still copying when the request is cancelled and cleaned up
            with open(dst, "wb") as f:
                f.write(b"model")
            copy_done.set()

        monkeypatch.setattr(ml_models_routes.shutil, "copyfile", slow_copy)
        file_manager_service = self._file_manager(tmp_path / "custom", file_id)

        async with anyio.create_task_group() as tg:
            tg.start_soon(self._upload, file_manager_service)
            await anyio.to_thread.run_sync(copy_started.wait, 5)
            tg.cancel_scope.cancel()

        assert await anyio.to_thread.run_sync(copy_done.wait, 5)
        file_manager_service.delete_file.assert_awaited_once_with(file_id)
        assert not copy_path.exists()

    @pytest.mark.asyncio
    async def test_successful_upload_deletes_nothing(self, ml_models_dir):
        file_manager_service = self._file_manager(ml_models_dir.parent, uuid4())

        await self._upload(file_manager_service)

        file_manager_service.delete_file.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_successful_upload_logs_how_long_each_stage_took(self, ml_models_dir, caplog):
        """One upload's log line tells the server's time from the transfer time (MLP-13)."""
        import logging

        file_id = uuid4()
        file_manager_service = self._file_manager(ml_models_dir.parent, file_id)
        file_manager_service.create_file.return_value.size = 4_400_000

        with caplog.at_level(logging.INFO, logger="app.api.v1.routes.ml_models"):
            await self._upload(file_manager_service)

        line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("Model file upload "))
        assert f"Model file upload {file_id}: 4400000 bytes on local storage" in line
        for stage in ("settings", "storage write", "source URL", "route total"):
            assert re.search(rf"{stage} \d+ ms", line), f"{stage} has no duration in: {line}"

    @pytest.mark.asyncio
    async def test_upload_outside_ml_models_logs_the_copy_stage(self, ml_models_dir, tmp_path, monkeypatch, caplog):
        """A custom File Manager folder adds a copy into ml_models, which gets its own timing."""
        import logging
        from app.api.v1.routes import ml_models as ml_models_routes

        monkeypatch.setattr(ml_models_routes, "ML_MODELS_UPLOAD_DIR", str(ml_models_dir))
        custom = tmp_path / "custom"
        (custom / "ml_models").mkdir(parents=True)
        (custom / "ml_models" / "abc.pkl").write_bytes(b"model")
        file_manager_service = self._file_manager(custom, uuid4())

        with caplog.at_level(logging.INFO, logger="app.api.v1.routes.ml_models"):
            await self._upload(file_manager_service)

        line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("Model file upload "))
        assert re.search(r"copy into ml_models \d+ ms", line), line


def test_training_upload_discard_requires_the_file_delete_permission():
    """Deleting a File Manager file needs delete rights, not just the right to upload."""
    from app.api.v1.routes.ml_models import router
    from app.core.permissions.constants import Permissions as P

    route = next(r for r in router.routes if r.path.endswith("/training-data/upload/{file_id}"))
    assert route.methods == {"DELETE"}
    closures = [
        cell.cell_contents
        for dep in route.dependencies
        for cell in (getattr(dep.dependency, "__closure__", None) or ())
    ]
    flattened = {item for value in closures for item in (value if isinstance(value, (list, tuple, set)) else [value])}
    assert P.FileManager.DELETE in flattened
    assert P.FileManager.CREATE not in flattened
