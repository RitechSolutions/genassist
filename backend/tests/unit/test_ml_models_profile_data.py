"""Tests for Train Data Source profiling inputs."""

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pandas as pd
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.requests import Request

from app.api.v1.routes import ml_models
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.modules.integration.database.database_manager import DatabaseManager
from app.services.file_manager import FileManagerService


def _file_manager() -> MagicMock:
    manager = MagicMock()
    manager.get_file_by_id = AsyncMock(
        return_value=SimpleNamespace(
            name="training.csv",
            path="uploads/training.csv",
            file_extension="csv",
        )
    )
    manager.download_file_to_path = AsyncMock()
    manager.download_file_from_url_to_path = AsyncMock()
    manager.extract_file_id_from_url = AsyncMock(return_value=None)
    return manager


def _request(*granted_permissions: str) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/ml-models/profile-data",
            "headers": [],
            "query_string": b"",
        }
    )
    request.state.user = SimpleNamespace(permissions=set(granted_permissions))
    return request


async def _query_preview_chunks(columns, rows):
    yield columns, []
    if rows:
        yield columns, rows


@pytest.mark.asyncio
async def test_analyze_csv_file_id_requires_file_manager_read_permission():
    file_manager = _file_manager()

    with pytest.raises(AppException) as exc_info:
        await ml_models.analyze_csv(
            request=_request(P.MlModel.READ),
            file_url=None,
            file_id=uuid4(),
            file_name="training.csv",
            python_code=None,
            file_manager_service=file_manager,
        )

    assert exc_info.value.status_code == 403
    file_manager.get_file_by_id.assert_not_awaited()
    file_manager.download_file_to_path.assert_not_awaited()


@pytest.mark.asyncio
async def test_analyze_csv_local_path_does_not_require_file_manager_read(
    monkeypatch, tmp_path
):
    source = tmp_path / "local.csv"
    source.write_text("id,name\n1,Ada\n", encoding="utf-8")
    analyze = MagicMock(return_value={"row_count": 1})
    monkeypatch.setattr(ml_models.ml_utils, "analyze_csv_data", analyze)

    result = await ml_models.analyze_csv(
        request=_request(P.MlModel.READ),
        file_url=str(source),
        file_id=None,
        file_name=None,
        python_code=None,
        file_manager_service=_file_manager(),
    )

    assert result == {"row_count": 1}
    analyze.assert_called_once_with(str(source))


@pytest.mark.asyncio
async def test_profile_data_file_id_requires_file_manager_read_permission():
    file_manager = _file_manager()

    with pytest.raises(AppException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(file_id=uuid4(), file_name="remote.csv"),
            _request(P.MlModel.READ),
            file_manager,
        )

    assert exc_info.value.status_code == 403
    file_manager.download_file_to_path.assert_not_awaited()


@pytest.mark.asyncio
async def test_oversized_stored_file_is_rejected_before_download(monkeypatch):
    file_manager = _file_manager()
    file_manager.get_file_by_id.return_value = SimpleNamespace(
        name="training.csv",
        path="uploads/training.csv",
        file_extension="csv",
        size=10,
    )
    monkeypatch.setattr(ml_models.settings, "ML_EXTRACT_MAX_BYTES", 1)

    with pytest.raises(HTTPException) as exc_info:
        await ml_models._resolve_csv_input(
            request=_request(P.FileManager.READ),
            file_url=None,
            file_id=uuid4(),
            file_name="training.csv",
            file_manager_service=file_manager,
        )

    assert exc_info.value.status_code == 413
    file_manager.download_file_to_path.assert_not_awaited()


@pytest.mark.asyncio
async def test_analyze_csv_downloads_s3_file_by_id_and_cleans_up(monkeypatch):
    file_id = uuid4()
    downloaded_paths: list[Path] = []

    async def download_file(_file_id, destination):
        assert _file_id == file_id
        path = Path(destination)
        path.write_text("id,name\n1,Ada\n", encoding="utf-8")
        downloaded_paths.append(path)

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = download_file
    analyze = MagicMock(return_value={"row_count": 1})
    monkeypatch.setattr(ml_models.ml_utils, "analyze_csv_data", analyze)

    result = await ml_models.analyze_csv(
        request=_request(P.MlModel.READ, P.FileManager.READ),
        file_url="https://app.example/api/file-manager/files/source",
        file_id=file_id,
        file_name="training.csv",
        python_code=None,
        file_manager_service=file_manager,
    )

    assert result == {"row_count": 1}
    file_manager.download_file_to_path.assert_awaited_once()
    assert downloaded_paths and not downloaded_paths[0].exists()
    analyze.assert_called_once_with(str(downloaded_paths[0]))


@pytest.mark.asyncio
async def test_analyze_csv_returns_safe_s3_access_error_and_removes_partial_file():
    downloaded_paths: list[Path] = []

    async def fail_download(_file_id, destination):
        path = Path(destination)
        path.write_bytes(b"partial")
        downloaded_paths.append(path)
        raise RuntimeError("AccessDenied bucket=private-training key=secret.csv")

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = fail_download

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.analyze_csv(
            request=_request(P.MlModel.READ, P.FileManager.READ),
            file_url=None,
            file_id=uuid4(),
            file_name="training.csv",
            python_code=None,
            file_manager_service=file_manager,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Could not access the selected file. Check that it still exists "
        "and that the storage configuration is valid."
    )
    assert "AccessDenied" not in exc_info.value.detail
    assert downloaded_paths and not downloaded_paths[0].exists()


@pytest.mark.asyncio
async def test_analyze_csv_rejects_server_recorded_non_csv_despite_client_name():
    file_manager = _file_manager()
    file_manager.get_file_by_id.return_value = SimpleNamespace(
        name="payload.exe",
        path="uploads/payload.exe",
        file_extension="exe",
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.analyze_csv(
            request=_request(P.MlModel.READ, P.FileManager.READ),
            file_url=None,
            file_id=uuid4(),
            file_name="training.csv",
            python_code=None,
            file_manager_service=file_manager,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Only CSV files can be previewed or profiled."
    file_manager.download_file_to_path.assert_not_awaited()


@pytest.mark.asyncio
async def test_oversized_local_csv_is_not_deleted(monkeypatch, tmp_path):
    source = tmp_path / "large.csv"
    source.write_text("id,name\n1,Ada\n", encoding="utf-8")
    original = source.read_bytes()
    monkeypatch.setattr(ml_models.settings, "ML_EXTRACT_MAX_BYTES", 1)

    with pytest.raises(HTTPException) as exc_info:
        await ml_models._resolve_csv_input(
            request=_request(P.FileManager.READ),
            file_url=str(source),
            file_id=None,
            file_name="large.csv",
            file_manager_service=_file_manager(),
        )

    assert exc_info.value.status_code == 413
    assert source.exists()
    assert source.read_bytes() == original


@pytest.mark.asyncio
async def test_oversized_s3_download_is_cleaned_up(monkeypatch):
    downloaded_paths: list[Path] = []

    async def download_file(_file_id, destination):
        path = Path(destination)
        path.write_bytes(b"too large")
        downloaded_paths.append(path)

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = download_file
    monkeypatch.setattr(ml_models.settings, "ML_EXTRACT_MAX_BYTES", 1)

    with pytest.raises(HTTPException) as exc_info:
        await ml_models._resolve_csv_input(
            request=_request(P.FileManager.READ),
            file_url=None,
            file_id=uuid4(),
            file_name="training.csv",
            file_manager_service=file_manager,
        )

    assert exc_info.value.status_code == 413
    assert downloaded_paths and not downloaded_paths[0].exists()


@pytest.mark.asyncio
async def test_profile_data_uses_existing_local_csv(monkeypatch, tmp_path):
    source = tmp_path / "local.csv"
    source.write_text("id,name\n1,Ada\n", encoding="utf-8")
    build_report = MagicMock(return_value="<html>local</html>")
    monkeypatch.setattr(ml_models, "_build_profile_report_html", build_report)
    file_manager = _file_manager()

    response = await ml_models.profile_data(
        ml_models.ProfileDataRequest(
            file_url=str(source),
            file_name="training.csv",
        ),
        _request(),
        file_manager,
    )

    assert response.body == b"<html>local</html>"
    assert response.headers["content-disposition"] == (
        'attachment; filename="training_profile.html"'
    )
    build_report.assert_called_once_with(str(source), "training.csv")
    file_manager.download_file_to_path.assert_not_awaited()
    file_manager.download_file_from_url_to_path.assert_not_awaited()


def test_profile_csv_legacy_body_is_accepted_over_http(monkeypatch, tmp_path):
    source = tmp_path / "legacy.csv"
    source.write_text("id,name\n1,Ada\n", encoding="utf-8")
    file_manager = _file_manager()
    monkeypatch.setattr(
        ml_models,
        "_build_profile_report_html",
        MagicMock(return_value="<html>legacy</html>"),
    )

    app = FastAPI()
    app.include_router(ml_models.router, prefix="/ml-models")
    route = next(
        route
        for route in app.routes
        if getattr(route, "path", None) == "/ml-models/profile-csv"
    )
    for dependency in route.dependant.dependencies:
        if getattr(dependency.call, "__name__", "") == "inject_into_route":
            app.dependency_overrides[dependency.call] = lambda: file_manager
        else:
            app.dependency_overrides[dependency.call] = lambda: None

    response = TestClient(app).post(
        "/ml-models/profile-csv",
        json={"file_url": str(source)},
    )

    assert response.status_code == 200
    assert response.content == b"<html>legacy</html>"


@pytest.mark.asyncio
async def test_profile_data_downloads_non_local_csv_by_file_id(monkeypatch):
    downloaded_paths: list[Path] = []

    async def download_file(_file_id, destination):
        path = Path(destination)
        path.write_text("id,name\n1,Ada\n", encoding="utf-8")
        downloaded_paths.append(path)

    def build_report(file_path, _display_name):
        assert Path(file_path).read_text(encoding="utf-8") == "id,name\n1,Ada\n"
        return "<html>remote</html>"

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = download_file
    monkeypatch.setattr(ml_models, "_build_profile_report_html", build_report)
    file_id = uuid4()

    response = await ml_models.profile_data(
        ml_models.ProfileDataRequest(
            source_type="csv",
            file_url="/path/from/another/container.csv",
            file_id=file_id,
            file_name="remote.csv",
        ),
        _request(P.FileManager.READ),
        file_manager,
    )

    assert response.body == b"<html>remote</html>"
    file_manager.download_file_to_path.assert_awaited_once()
    assert file_manager.download_file_to_path.await_args.args[0] == file_id
    assert len(downloaded_paths) == 1
    assert not downloaded_paths[0].exists()


@pytest.mark.asyncio
async def test_profile_data_uses_stable_name_for_download_without_file_name(monkeypatch):
    async def download_file(_file_id, destination):
        Path(destination).write_text("id,name\n1,Ada\n", encoding="utf-8")

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = download_file
    build_report = MagicMock(return_value="<html>remote</html>")
    monkeypatch.setattr(ml_models, "_build_profile_report_html", build_report)

    response = await ml_models.profile_data(
        ml_models.ProfileDataRequest(file_id=uuid4()),
        _request(P.FileManager.READ),
        file_manager,
    )

    assert response.headers["content-disposition"] == (
        'attachment; filename="data_profile.html"'
    )
    assert build_report.call_args.args[1] == "data.csv"


@pytest.mark.asyncio
async def test_profile_data_profiles_read_only_sql_results(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["id", "name"], [(1, "Ada"), (2, "Linus")])
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )
    build_report = MagicMock(return_value="<html>query</html>")
    monkeypatch.setattr(
        ml_models,
        "_build_dataframe_profile_report_html",
        build_report,
    )
    source_id = uuid4()

    response = await ml_models.profile_data(
        ml_models.ProfileDataRequest(
            source_type="datasource",
            data_source_id=source_id,
            query="SELECT id, name FROM people",
        ),
        _request(P.DataSource.READ),
        _file_manager(),
    )

    assert response.body == b"<html>query</html>"
    provider.get_database_manager.assert_awaited_once_with(str(source_id))
    database_manager.stream_query.assert_called_once_with(
        f"SELECT id, name FROM people LIMIT {ml_models.settings.ML_PROFILE_MAX_ROWS}",
        chunk_size=min(
            ml_models.settings.ML_PROFILE_MAX_ROWS,
            ml_models.PROFILE_QUERY_CHUNK_ROWS,
        ),
    )
    dataframe = build_report.call_args.args[0]
    assert isinstance(dataframe, pd.DataFrame)
    assert dataframe.to_dict("records") == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Linus"},
    ]
    assert build_report.call_args.kwargs == {
        "title": (
            "Data Profile: SQL Query Results "
            f"(up to {ml_models.settings.ML_PROFILE_MAX_ROWS:,} rows)"
        )
    }


@pytest.mark.asyncio
async def test_preview_query_returns_six_bounded_rows(monkeypatch):
    rows = [(index, f"user-{index}") for index in range(1, 7)]
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["id", "username"], rows)
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )
    source_id = uuid4()

    result = await ml_models.preview_query(
        ml_models.QueryPreviewRequest(
            data_source_id=source_id,
            query="SELECT id, username FROM users",
        ),
        _request(P.DataSource.READ),
    )

    assert result == {
        "row_count": 6,
        "column_count": 2,
        "column_names": ["id", "username"],
        "sample_data": [
            {"id": index, "username": f"user-{index}"}
            for index in range(1, 7)
        ],
        "columns_info": [],
    }
    provider.get_database_manager.assert_awaited_once_with(str(source_id))
    database_manager.stream_query.assert_called_once_with(
        "SELECT id, username FROM users LIMIT 6",
        chunk_size=6,
    )


@pytest.mark.asyncio
async def test_preview_query_preserves_columns_for_empty_results(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "sqlite"
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["id", "name"], [])
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    result = await ml_models.preview_query(
        ml_models.QueryPreviewRequest(
            data_source_id=uuid4(),
            query="SELECT id, name FROM people WHERE 1 = 0",
        ),
        _request(P.DataSource.READ),
    )

    assert result["row_count"] == 0
    assert result["column_count"] == 2
    assert result["column_names"] == ["id", "name"]
    assert result["sample_data"] == []


@pytest.mark.asyncio
async def test_preview_query_rejects_write_sql(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.stream_query = MagicMock()
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.preview_query(
            ml_models.QueryPreviewRequest(
                data_source_id=uuid4(),
                query="DELETE FROM users",
            ),
            _request(P.DataSource.READ),
        )

    assert exc_info.value.status_code == 400
    assert "SQL execution blocked" in exc_info.value.detail
    database_manager.stream_query.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["preview", "profile"])
@pytest.mark.parametrize("provider_raises", [True, False], ids=["exception", "none"])
async def test_query_returns_404_for_unknown_data_source(
    monkeypatch, operation, provider_raises
):
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(
        return_value=None,
        side_effect=(
            AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND)
            if provider_raises
            else None
        ),
    )
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    source_id = uuid4()
    with pytest.raises(HTTPException) as exc_info:
        if operation == "preview":
            await ml_models.preview_query(
                ml_models.QueryPreviewRequest(
                    data_source_id=source_id,
                    query="SELECT 1",
                ),
                _request(P.DataSource.READ),
            )
        else:
            await ml_models.profile_data(
                ml_models.ProfileDataRequest(
                    source_type="datasource",
                    data_source_id=source_id,
                    query="SELECT 1",
                ),
                _request(P.DataSource.READ),
                _file_manager(),
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Data source not found."
    provider.get_database_manager.assert_awaited_once_with(str(source_id))


@pytest.mark.asyncio
async def test_preview_query_returns_safe_database_error(monkeypatch):
    async def failed_stream():
        raise RuntimeError('column "secret_column" does not exist')
        yield

    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.stream_query = MagicMock(return_value=failed_stream())
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.preview_query(
            ml_models.QueryPreviewRequest(
                data_source_id=uuid4(),
                query="SELECT missing FROM users",
            ),
            _request(P.DataSource.READ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        'Database query failed: column "secret_column" does not exist'
    )


@pytest.mark.asyncio
async def test_preview_query_hides_connection_details(monkeypatch):
    async def failed_stream():
        raise RuntimeError(
            'connection to server at "db.internal" failed: password authentication failed'
        )
        yield

    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.stream_query = MagicMock(return_value=failed_stream())
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.preview_query(
            ml_models.QueryPreviewRequest(
                data_source_id=uuid4(),
                query="SELECT * FROM users",
            ),
            _request(P.DataSource.READ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Could not run the query on the selected data source. "
        "Check the query and connection settings."
    )
    assert "db.internal" not in exc_info.value.detail


@pytest.mark.asyncio
async def test_profile_data_rejects_write_query(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.stream_query = MagicMock()
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(
                source_type="datasource",
                data_source_id=uuid4(),
                query="DELETE FROM people",
            ),
            _request(P.DataSource.READ),
            _file_manager(),
        )

    assert exc_info.value.status_code == 400
    assert "blocked" in exc_info.value.detail.lower()
    database_manager.stream_query.assert_not_called()


@pytest.mark.asyncio
async def test_profile_data_requires_source_details():
    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(source_type="csv"),
            _request(),
            _file_manager(),
        )

    assert exc_info.value.status_code == 400
    assert "file path" in exc_info.value.detail


@pytest.mark.asyncio
async def test_profile_data_cleans_download_when_profiling_fails(monkeypatch):
    downloaded_paths: list[Path] = []

    async def download_file(_file_id, destination):
        path = Path(destination)
        path.write_text("id\n1\n", encoding="utf-8")
        downloaded_paths.append(path)

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = download_file
    monkeypatch.setattr(
        ml_models,
        "_build_profile_report_html",
        MagicMock(side_effect=RuntimeError("profile failed")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(
                source_type="csv",
                file_id=uuid4(),
                file_name="remote.csv",
            ),
            _request(P.FileManager.READ),
            file_manager,
        )

    assert exc_info.value.status_code == 500
    assert len(downloaded_paths) == 1
    assert not downloaded_paths[0].exists()


@pytest.mark.asyncio
async def test_profile_data_recovers_file_id_from_source_url(monkeypatch):
    file_id = uuid4()
    downloaded_paths: list[Path] = []

    async def download_file(_file_id, destination):
        assert _file_id == file_id
        path = Path(destination)
        path.write_text("id,name\n1,Ada\n", encoding="utf-8")
        downloaded_paths.append(path)

    file_manager = object.__new__(FileManagerService)
    file_manager.get_file_by_id = AsyncMock(
        return_value=SimpleNamespace(
            name="s3.csv",
            path="uploads/s3.csv",
            file_extension="csv",
        )
    )
    file_manager.download_file_to_path = AsyncMock(side_effect=download_file)
    file_manager.download_file_from_url_to_path = AsyncMock()
    monkeypatch.setattr(
        ml_models,
        "_build_profile_report_html",
        MagicMock(return_value="<html>s3</html>"),
    )

    response = await ml_models.profile_data(
        ml_models.ProfileDataRequest(
            file_url=(
                f"https://app.example/api/file-manager/files/{file_id}/source"
                "?X-Tenant-Id=tenant"
            ),
            file_name="s3.csv",
        ),
        _request(P.FileManager.READ),
        file_manager,
    )

    assert response.body == b"<html>s3</html>"
    file_manager.download_file_to_path.assert_awaited_once()
    file_manager.download_file_from_url_to_path.assert_not_awaited()
    assert len(downloaded_paths) == 1
    assert not downloaded_paths[0].exists()


@pytest.mark.asyncio
async def test_profile_data_prefers_file_id_over_existing_local_path(monkeypatch, tmp_path):
    local_path = tmp_path / "local.csv"
    local_path.write_text("source\nlocal\n", encoding="utf-8")
    file_id = uuid4()

    async def download_file(_file_id, destination):
        assert _file_id == file_id
        Path(destination).write_text("source\nfile-manager\n", encoding="utf-8")

    def build_report(file_path, _display_name):
        assert Path(file_path).read_text(encoding="utf-8") == "source\nfile-manager\n"
        return "<html>file-manager</html>"

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = download_file
    monkeypatch.setattr(ml_models, "_build_profile_report_html", build_report)

    response = await ml_models.profile_data(
        ml_models.ProfileDataRequest(file_url=str(local_path), file_id=file_id),
        _request(P.FileManager.READ),
        file_manager,
    )

    assert response.body == b"<html>file-manager</html>"
    file_manager.download_file_to_path.assert_awaited_once()


@pytest.mark.asyncio
async def test_profile_data_rejects_failed_url_download(monkeypatch, tmp_path):
    created_paths: list[Path] = []

    def temporary_path(_suffix=".csv"):
        path = tmp_path / "profile.csv"
        path.touch()
        created_paths.append(path)
        return path

    file_manager = _file_manager()
    file_manager.download_file_from_url_to_path.return_value = False
    monkeypatch.setattr(ml_models, "_temporary_csv_path", temporary_path)

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(file_url="https://files.example/data.csv"),
            _request(),
            file_manager,
        )

    assert exc_info.value.status_code == 400
    assert created_paths and not created_paths[0].exists()


@pytest.mark.asyncio
async def test_profile_data_rejects_failed_file_manager_download(monkeypatch, tmp_path):
    created_paths: list[Path] = []

    def temporary_path(_suffix=".csv"):
        path = tmp_path / "profile.csv"
        path.touch()
        created_paths.append(path)
        return path

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = RuntimeError("storage unavailable")
    monkeypatch.setattr(ml_models, "_temporary_csv_path", temporary_path)

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(file_id=uuid4()),
            _request(P.FileManager.READ),
            file_manager,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Could not access the selected file. Check that it still exists "
        "and that the storage configuration is valid."
    )
    assert created_paths and not created_paths[0].exists()


@pytest.mark.asyncio
async def test_profile_data_requires_datasource_permission():
    with pytest.raises(AppException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(
                source_type="datasource",
                data_source_id=uuid4(),
                query="SELECT 1",
            ),
            _request(P.MlModel.READ),
            _file_manager(),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_profile_data_rejects_unresolved_workflow_variables(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.stream_query = MagicMock()
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(
                source_type="datasource",
                data_source_id=uuid4(),
                query="SELECT * FROM people WHERE id = {{session.id}}",
            ),
            _request(P.DataSource.READ),
            _file_manager(),
        )

    assert exc_info.value.status_code == 400
    assert "workflow variables" in exc_info.value.detail
    database_manager.stream_query.assert_not_called()


@pytest.mark.asyncio
async def test_profile_data_reports_empty_query_result(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "sqlite"
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["id"], [])
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(
                source_type="datasource",
                data_source_id=uuid4(),
                query="SELECT * FROM people",
            ),
            _request(P.DataSource.READ),
            _file_manager(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "The query returned no rows."


@pytest.mark.asyncio
async def test_profile_data_returns_safe_query_error(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    async def failed_stream():
        raise RuntimeError('column "secret_column" does not exist')
        yield

    database_manager.stream_query = MagicMock(return_value=failed_stream())
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(
                source_type="datasource",
                data_source_id=uuid4(),
                query="SELECT missing FROM people",
            ),
            _request(P.DataSource.READ),
            _file_manager(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        'Database query failed: column "secret_column" does not exist'
    )


@pytest.mark.asyncio
async def test_profile_data_executes_real_sqlite_read_query(monkeypatch, tmp_path):
    database_path = tmp_path / "profile.sqlite"
    database_manager = DatabaseManager(
        {"source_type": "sqlite", "database_path": str(database_path)}
    )
    await database_manager.connect()
    try:
        async with database_manager.engine.begin() as connection:
            await connection.execute(text("CREATE TABLE people (id INTEGER, name TEXT)"))
            await connection.execute(
                text("INSERT INTO people VALUES (1, 'Ada'), (2, 'Linus')")
            )

        provider = MagicMock()
        provider.get_database_manager = AsyncMock(return_value=database_manager)
        monkeypatch.setattr(
            ml_models.DBProviderManager,
            "get_instance",
            MagicMock(return_value=provider),
        )
        build_report = MagicMock(return_value="<html>sqlite</html>")
        monkeypatch.setattr(
            ml_models,
            "_build_dataframe_profile_report_html",
            build_report,
        )

        response = await ml_models.profile_data(
            ml_models.ProfileDataRequest(
                source_type="datasource",
                data_source_id=uuid4(),
                query="SELECT id, name FROM people ORDER BY id",
            ),
            _request(P.DataSource.READ),
            _file_manager(),
        )

        assert response.body == b"<html>sqlite</html>"
        assert build_report.call_args.args[0].to_dict("records") == [
            {"id": 1, "name": "Ada"},
            {"id": 2, "name": "Linus"},
        ]
    finally:
        await database_manager.disconnect()


@pytest.mark.parametrize(
    ("db_type", "expected_fragment"),
    [
        ("postgresql", "LIMIT 7"),
        ("mysql", "LIMIT 7"),
        ("sqlite", "LIMIT 7"),
        ("snowflake", "LIMIT 7"),
        ("mssql", "TOP 7"),
    ],
)
@pytest.mark.asyncio
async def test_profile_data_caps_query_for_supported_dialects(
    monkeypatch,
    db_type,
    expected_fragment,
):
    monkeypatch.setattr(ml_models.settings, "ML_PROFILE_MAX_ROWS", 7)
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = db_type
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["id"], [(1,)])
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )
    monkeypatch.setattr(
        ml_models,
        "_build_dataframe_profile_report_html",
        MagicMock(return_value="<html>query</html>"),
    )

    await ml_models.profile_data(
        ml_models.ProfileDataRequest(
            source_type="datasource",
            data_source_id=uuid4(),
            query="WITH people AS (SELECT 1 AS id) SELECT * FROM people ORDER BY id",
        ),
        _request(P.DataSource.READ),
        _file_manager(),
    )

    executed_query = database_manager.stream_query.call_args.args[0]
    assert expected_fragment in executed_query


@pytest.mark.parametrize(
    ("db_type", "query", "expected_fragment"),
    [
        (
            "postgresql",
            "SELECT * FROM people FETCH FIRST 2 ROWS ONLY",
            "LIMIT 2",
        ),
        (
            "mssql",
            (
                "SELECT * FROM people ORDER BY id OFFSET 0 ROWS "
                "FETCH NEXT 2 ROWS ONLY"
            ),
            "FETCH FIRST 2 ROWS ONLY",
        ),
    ],
)
@pytest.mark.asyncio
async def test_profile_data_preserves_smaller_fetch_limit(
    monkeypatch,
    db_type,
    query,
    expected_fragment,
):
    monkeypatch.setattr(ml_models.settings, "ML_PROFILE_MAX_ROWS", 7)
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = db_type
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["id"], [(1,)])
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )
    monkeypatch.setattr(
        ml_models,
        "_build_dataframe_profile_report_html",
        MagicMock(return_value="<html>query</html>"),
    )

    await ml_models.profile_data(
        ml_models.ProfileDataRequest(
            source_type="datasource",
            data_source_id=uuid4(),
            query=query,
        ),
        _request(P.DataSource.READ),
        _file_manager(),
    )

    executed_query = database_manager.stream_query.call_args.args[0]
    assert expected_fragment in executed_query
    assert "100000" not in executed_query


@pytest.mark.parametrize(
    ("db_type", "query", "expected_fragment"),
    [
        (
            "postgresql",
            "SELECT d::date, j->>'k' FROM records",
            "CAST(d AS DATE)",
        ),
        (
            "snowflake",
            "SELECT value:field::string FROM records",
            "CAST(GET_PATH(value, 'field') AS TEXT)",
        ),
        (
            "postgresql",
            "SELECT * FROM records -- profile note",
            "/* profile note */",
        ),
    ],
)
@pytest.mark.asyncio
async def test_profile_data_executes_validated_sqlglot_rewrite(
    monkeypatch,
    db_type,
    query,
    expected_fragment,
):
    monkeypatch.setattr(ml_models.settings, "ML_PROFILE_MAX_ROWS", 7)
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = db_type
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["value"], [(1,)])
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )
    monkeypatch.setattr(
        ml_models,
        "_build_dataframe_profile_report_html",
        MagicMock(return_value="<html>query</html>"),
    )

    await ml_models.profile_data(
        ml_models.ProfileDataRequest(
            source_type="datasource",
            data_source_id=uuid4(),
            query=query,
        ),
        _request(P.DataSource.READ),
        _file_manager(),
    )

    executed_query = database_manager.stream_query.call_args.args[0]
    assert expected_fragment in executed_query
    assert "LIMIT 7" in executed_query


def test_profile_csv_applies_row_limit(monkeypatch, tmp_path):
    source = tmp_path / "limited.csv"
    source.write_text("id\n1\n2\n3\n", encoding="utf-8")
    build_report = MagicMock(return_value="<html>limited</html>")
    monkeypatch.setattr(ml_models.settings, "ML_PROFILE_MAX_ROWS", 2)
    monkeypatch.setattr(
        ml_models,
        "_build_dataframe_profile_report_html",
        build_report,
    )

    html = ml_models._build_profile_report_html(str(source))

    assert html == "<html>limited</html>"
    assert build_report.call_args.args[0].to_dict("records") == [{"id": 1}, {"id": 2}]


def test_profile_csv_reports_empty_file(tmp_path):
    source = tmp_path / "empty.csv"
    source.write_text("id,name\n", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        ml_models._build_profile_report_html(str(source))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "The file has no rows."


def test_profile_dataframe_normalizes_decimal_and_uuid_values():
    identifier = uuid4()
    dataframe = pd.DataFrame(
        {
            "amount": [Decimal("10.25"), Decimal("2.50")],
            "identifier": [identifier, UUID(int=0)],
        }
    )

    normalized = ml_models._normalize_profile_dataframe(dataframe)

    assert pd.api.types.is_numeric_dtype(normalized["amount"])
    assert normalized["identifier"].tolist() == [str(identifier), str(UUID(int=0))]


@pytest.mark.asyncio
@pytest.mark.parametrize("file_url", ["{{source.data_path}}", "/data/{{session.file}}.csv"])
async def test_analyze_csv_refuses_unfilled_placeholder(file_url):
    file_manager = _file_manager()

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.analyze_csv(
            request=_request(P.MlModel.READ),
            file_url=file_url,
            file_id=None,
            file_name=None,
            python_code=None,
            file_manager_service=file_manager,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == ml_models.UNFILLED_FILE_PATH_DETAIL
    file_manager.extract_file_id_from_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_query_refuses_duplicate_column_names(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "sqlite"
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["id", "score", "score"], [(1, 10, 99)])
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.preview_query(
            ml_models.QueryPreviewRequest(
                data_source_id=uuid4(),
                query="SELECT 1 AS id, 10 AS score, 99 AS score",
            ),
            _request(P.DataSource.READ),
        )

    assert exc_info.value.status_code == 400
    assert "two columns named 'score'" in exc_info.value.detail
    assert "with AS" in exc_info.value.detail


@pytest.mark.asyncio
async def test_profile_data_refuses_query_with_repeated_column(monkeypatch):
    # As dicts, a.score and b.score would profile as one 'score' column.
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.stream_query = MagicMock(
        return_value=_query_preview_chunks(["id", "score", "score"], [(1, 2, 3)])
    )
    provider = MagicMock()
    provider.get_database_manager = AsyncMock(return_value=database_manager)
    monkeypatch.setattr(
        ml_models.DBProviderManager,
        "get_instance",
        MagicMock(return_value=provider),
    )
    build_report = MagicMock()
    monkeypatch.setattr(ml_models, "_build_dataframe_profile_report_html", build_report)

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(
                source_type="datasource",
                data_source_id=uuid4(),
                query="SELECT a.id, a.score, b.score FROM a JOIN b ON a.id = b.id",
            ),
            _request(P.DataSource.READ),
            _file_manager(),
        )

    assert exc_info.value.status_code == 400
    assert "two columns named 'score'" in exc_info.value.detail
    build_report.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "name"),
    [
        ("a,a,b\n1,2,3\n", "a"),
        # Excel's "CSV UTF-8" export starts with a BOM.
        ("\ufeffid,id\n1,2\n", "id"),
        # The run sniffs the delimiter, so the profile check must too.
        ("id;name;id\n1;Ada;2\n", "id"),
    ],
)
async def test_profile_csv_refuses_repeated_header(tmp_path, content, name):
    # pd.read_csv would rename the second column to '<name>.1'.
    source = tmp_path / "repeated.csv"
    source.write_text(content, encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        await ml_models._ensure_unique_csv_header(source)

    assert exc_info.value.status_code == 400
    assert f"two columns named '{name}'" in exc_info.value.detail


@pytest.mark.asyncio
async def test_profile_csv_header_check_ignores_trailing_empty_cells(tmp_path):
    source = tmp_path / "trailing.csv"
    source.write_text("a,b,,\n1,2,,\n", encoding="utf-8")

    await ml_models._ensure_unique_csv_header(source)


# DP-21 (68395): a step's Run on a File Manager / S3 source


def _downloading_file_manager(content: str, downloaded_paths: list[Path]) -> MagicMock:
    async def download_file(_file_id, destination):
        path = Path(destination)
        path.write_text(content, encoding="utf-8")
        downloaded_paths.append(path)

    file_manager = _file_manager()
    file_manager.download_file_to_path.side_effect = download_file
    return file_manager


@pytest.mark.asyncio
async def test_step_run_on_a_file_manager_source_reads_the_downloaded_copy(monkeypatch):
    downloaded: list[Path] = []
    file_manager = _downloading_file_manager("id,name,city\n1,Ada,Tirana\n2,Bo,Durres\n", downloaded)
    seen = {}

    async def run_step(python_code, df, file_url, raise_on_error=True):
        seen["rows"] = len(df)
        seen["file_url"] = file_url
        return df.drop(columns=["city"]), None, None

    analyzed_paths: list[str] = []

    def analyze(path):
        analyzed_paths.append(path)
        return {"column_names": list(pd.read_csv(path).columns)}

    monkeypatch.setattr(ml_models.ml_utils, "execute_and_process_preprocessing_code", run_step)
    monkeypatch.setattr(ml_models.ml_utils, "analyze_csv_data", analyze)

    result = await ml_models.analyze_csv(
        request=_request(P.MlModel.READ, P.FileManager.READ),
        file_url=None,
        file_id=uuid4(),
        file_name="customers.csv",
        python_code="def process(params): return params['df']",
        file_manager_service=file_manager,
    )

    assert result == {"column_names": ["id", "name"]}
    assert seen["rows"] == 2
    # The code gets the name the user knows, never the server's temp path.
    assert seen["file_url"] == "customers.csv"
    # The downloaded copy, the step's preview file and its dtypes file are all removed.
    assert downloaded and not downloaded[0].exists()
    assert analyzed_paths and not Path(analyzed_paths[0]).exists()
    assert not ml_models.ml_utils.dtypes_sidecar_path(analyzed_paths[0]).exists()


@pytest.mark.asyncio
async def test_failing_step_on_a_file_manager_source_removes_the_temp_file_and_hides_paths(monkeypatch):
    downloaded: list[Path] = []
    file_manager = _downloading_file_manager("id,name\n1,Ada\n", downloaded)

    async def failing_step(python_code, df, file_url, raise_on_error=True):
        raise AppException(
            error_key=ErrorKey.INTERNAL_ERROR,
            error_detail="Column Filter: column(s) not found in the data: citty",
        )

    monkeypatch.setattr(ml_models.ml_utils, "execute_and_process_preprocessing_code", failing_step)

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.analyze_csv(
            request=_request(P.MlModel.READ, P.FileManager.READ),
            file_url=None,
            file_id=uuid4(),
            file_name="customers.csv",
            python_code="code",
            file_manager_service=file_manager,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Column Filter: column(s) not found in the data: citty"
    assert downloaded and not downloaded[0].exists()


@pytest.mark.asyncio
async def test_unexpected_step_error_names_no_server_path(monkeypatch):
    downloaded: list[Path] = []
    file_manager = _downloading_file_manager("id,name\n1,Ada\n", downloaded)

    async def run_step(python_code, df, file_url, raise_on_error=True):
        return df, None, None

    real_read = ml_models.ml_utils.read_csv_with_dtypes
    calls = []

    def read_csv(path, *args, **kwargs):
        calls.append(path)
        if len(calls) == 1:  # loading the downloaded file works
            return real_read(path, *args, **kwargs)
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(ml_models.ml_utils, "execute_and_process_preprocessing_code", run_step)
    # The real analyze_csv_data, failing on its read: its message must not name the temp path.
    monkeypatch.setattr(ml_models.ml_utils, "read_csv_with_dtypes", read_csv)

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.analyze_csv(
            request=_request(P.MlModel.READ, P.FileManager.READ),
            file_url=None,
            file_id=uuid4(),
            file_name="customers.csv",
            python_code="code",
            file_manager_service=file_manager,
        )

    assert len(calls) == 2, "the failure must come from analyzing the step's preview"
    assert exc_info.value.status_code in (400, 500)
    assert "/" not in exc_info.value.detail
    assert "tmp" not in exc_info.value.detail
    assert downloaded and not downloaded[0].exists()


@pytest.mark.asyncio
async def test_step_run_on_a_local_csv_still_works(monkeypatch, tmp_path):
    source = tmp_path / "local.csv"
    source.write_text("id,name\n1,Ada\n", encoding="utf-8")
    monkeypatch.setattr(ml_models.ml_utils, "DATA_VOLUME", tmp_path)

    seen = {}

    async def run_step(python_code, df, file_url, raise_on_error=True):
        seen["file_url"] = file_url
        return df, None, None

    monkeypatch.setattr(ml_models.ml_utils, "execute_and_process_preprocessing_code", run_step)
    monkeypatch.setattr(ml_models.ml_utils, "analyze_csv_data", lambda path: {"row_count": len(pd.read_csv(path))})
    monkeypatch.setattr(ml_models.ml_utils, "extra_csv_directories", AsyncMock(return_value=[]))
    monkeypatch.setattr(ml_models.training_data_storage, "fetch_training_data", AsyncMock())

    result = await ml_models.analyze_csv(
        request=_request(P.MlModel.READ),
        file_url=str(source),
        file_id=None,
        file_name=None,
        python_code="code",
        file_manager_service=_file_manager(),
    )

    assert result == {"row_count": 1}
    assert source.exists()
    # A local file's code still gets its readable path, as before.
    assert seen["file_url"] == str(source)


# DP-22 (68397): data pasted into File URL


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pasted",
    [
        "id,name,city1,Ada,Tirana2,Bo,Durres",  # CSV text after the single-line field drops line breaks
        "id,name\n1,Ada\n",
        "1.5,2.3,4.1",
        "date,amount2024/01/05,3.2",
        "id;name;city1;Ada",
        '[{"id": 1}]',
    ],
)
async def test_analyze_csv_names_pasted_data_without_repeating_it(pasted, monkeypatch, tmp_path):
    monkeypatch.setattr(ml_models.ml_utils, "DATA_VOLUME", tmp_path)
    monkeypatch.setattr(ml_models.ml_utils, "extra_csv_directories", AsyncMock(return_value=[]))
    monkeypatch.setattr(ml_models.training_data_storage, "fetch_training_data", AsyncMock())
    file_manager = _file_manager()

    with pytest.raises(HTTPException) as exc_info:
        await ml_models.analyze_csv(
            request=_request(P.MlModel.READ),
            file_url=pasted,
            file_id=None,
            file_name=None,
            python_code="code",
            file_manager_service=file_manager,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == ml_models.ml_utils.INLINE_DATA_DETAIL
    assert "{{source.data_path}}" in exc_info.value.detail
    assert pasted.strip() not in exc_info.value.detail
    file_manager.download_file_to_path.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_real_local_file_with_a_comma_in_its_name_is_analyzed(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_models.ml_utils, "DATA_VOLUME", tmp_path)
    monkeypatch.setattr(ml_models.ml_utils, "extra_csv_directories", AsyncMock(return_value=[]))
    monkeypatch.setattr(ml_models.training_data_storage, "fetch_training_data", AsyncMock())
    (tmp_path / "train").mkdir()
    source = tmp_path / "train" / "sales, 2024.csv"
    source.write_text("id,name\n1,Ada\n", encoding="utf-8")
    analyze = MagicMock(return_value={"row_count": 1})
    monkeypatch.setattr(ml_models.ml_utils, "analyze_csv_data", analyze)

    result = await ml_models.analyze_csv(
        request=_request(P.MlModel.READ),
        file_url="sales, 2024.csv",
        file_id=None,
        file_name=None,
        python_code=None,
        file_manager_service=_file_manager(),
    )

    assert result == {"row_count": 1}
    analyze.assert_called_once_with(str(source.resolve()))


@pytest.mark.asyncio
async def test_an_unfilled_placeholder_is_not_called_pasted_data(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_models.ml_utils, "DATA_VOLUME", tmp_path)
    monkeypatch.setattr(ml_models.ml_utils, "extra_csv_directories", AsyncMock(return_value=[]))
    monkeypatch.setattr(ml_models.training_data_storage, "fetch_training_data", AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await ml_models._resolve_csv_input(
            request=_request(P.MlModel.READ),
            file_url="{{source.data_path}}",
            file_id=None,
            file_name=None,
            file_manager_service=_file_manager(),
        )

    # Unchanged from before: the extension check answers first, not the pasted-data message.
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Only CSV files can be previewed or profiled."


@pytest.mark.asyncio
async def test_a_comma_named_output_only_in_storage_is_fetched_before_anything_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_models.ml_utils, "DATA_VOLUME", tmp_path)
    monkeypatch.setattr(ml_models.ml_utils, "extra_csv_directories", AsyncMock(return_value=[]))
    (tmp_path / "train" / "thread-1").mkdir(parents=True)
    target = tmp_path / "train" / "thread-1" / "sales, 2024.csv"

    async def fetch(file_url, thread_id=None, allowed_directories=None):
        # Another server wrote it; this one downloads it from storage first.
        target.write_text("id,name\n1,Ada\n", encoding="utf-8")

    monkeypatch.setattr(ml_models.training_data_storage, "fetch_training_data", fetch)
    analyze = MagicMock(return_value={"row_count": 1})
    monkeypatch.setattr(ml_models.ml_utils, "analyze_csv_data", analyze)

    result = await ml_models.analyze_csv(
        request=_request(P.MlModel.READ),
        file_url="thread-1/sales, 2024.csv",
        file_id=None,
        file_name=None,
        python_code=None,
        file_manager_service=_file_manager(),
    )

    assert result == {"row_count": 1}
    analyze.assert_called_once_with(str(target.resolve()))


@pytest.mark.asyncio
async def test_a_downloaded_file_gives_the_code_its_name_not_its_url(monkeypatch):
    downloaded: list[Path] = []
    file_manager = _downloading_file_manager("id,name\n1,Ada\n", downloaded)
    seen = {}

    async def run_step(python_code, df, file_url, raise_on_error=True):
        seen["file_url"] = file_url
        return df, None, None

    monkeypatch.setattr(ml_models.ml_utils, "execute_and_process_preprocessing_code", run_step)
    monkeypatch.setattr(ml_models.ml_utils, "analyze_csv_data", lambda path: {"row_count": 1})

    await ml_models.analyze_csv(
        request=_request(P.MlModel.READ, P.FileManager.READ),
        file_url="https://bucket.example/uploads/x.csv?X-Amz-Signature=secret",
        file_id=uuid4(),
        file_name="customers.csv",
        python_code="code",
        file_manager_service=file_manager,
    )

    assert seen["file_url"] == "customers.csv"


@pytest.mark.asyncio
async def test_a_real_unsupported_extension_with_a_comma_still_says_unsupported():
    with pytest.raises(HTTPException) as exc_info:
        await ml_models._resolve_csv_input(
            request=_request(P.MlModel.READ),
            file_url="exports/Q1, 2024.tsv",
            file_id=None,
            file_name=None,
            file_manager_service=_file_manager(),
        )

    # The existing unsupported-type message, not the pasted-data one.
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Only CSV files can be previewed or profiled."


@pytest.mark.asyncio
async def test_a_bracketed_output_name_is_still_fetched_from_storage(monkeypatch, tmp_path):
    storage = ml_models.training_data_storage
    monkeypatch.setattr(storage.ml_utils, "DATA_VOLUME", tmp_path)
    find = AsyncMock(return_value=None)
    monkeypatch.setattr(storage, "_find_in_storage", find)

    await storage.fetch_training_data("[Q1] sales.csv", "thread-1")
    find.assert_awaited_once()

    find.reset_mock()
    await storage.fetch_training_data('[{"id": 1}]', "thread-1")  # JSON rows: nothing to fetch
    find.assert_not_awaited()
