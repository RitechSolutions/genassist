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
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.modules.integration.database.database_manager import DatabaseManager
from app.services.file_manager import FileManagerService


def _file_manager() -> MagicMock:
    manager = MagicMock()
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
        _request(),
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
        _request(),
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
    database_manager.execute_read_query = AsyncMock(
        return_value=([{"id": 1, "name": "Ada"}, {"id": 2, "name": "Linus"}], None)
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
    database_manager.execute_read_query.assert_awaited_once_with(
        f"SELECT id, name FROM people LIMIT {ml_models.settings.ML_PROFILE_MAX_ROWS}"
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
async def test_profile_data_rejects_write_query(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "postgresql"
    database_manager.execute_read_query = AsyncMock()
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
    database_manager.execute_read_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_profile_data_requires_source_details():
    with pytest.raises(HTTPException) as exc_info:
        await ml_models.profile_data(
            ml_models.ProfileDataRequest(source_type="csv"),
            _request(),
            _file_manager(),
        )

    assert exc_info.value.status_code == 400
    assert "CSV file path" in exc_info.value.detail


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
            _request(),
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
        _request(),
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
        _request(),
        file_manager,
    )

    assert response.body == b"<html>file-manager</html>"
    file_manager.download_file_to_path.assert_awaited_once()


@pytest.mark.asyncio
async def test_profile_data_rejects_failed_url_download(monkeypatch, tmp_path):
    created_paths: list[Path] = []

    def temporary_path():
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

    def temporary_path():
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
            _request(),
            file_manager,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "Could not fetch the CSV file from File Manager."
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
    database_manager.execute_read_query = AsyncMock()
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
    database_manager.execute_read_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_profile_data_reports_empty_query_result(monkeypatch):
    database_manager = MagicMock()
    database_manager.get_db_type.return_value = "sqlite"
    database_manager.execute_read_query = AsyncMock(return_value=([], None))
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
    database_manager.execute_read_query = AsyncMock(
        return_value=([], 'column "secret_column" does not exist')
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
                query="SELECT missing FROM people",
            ),
            _request(P.DataSource.READ),
            _file_manager(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        "The profiling query failed. Check the selected columns and data source."
    )
    assert "secret_column" not in exc_info.value.detail


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
    database_manager.execute_read_query = AsyncMock(return_value=([{"id": 1}], None))
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

    executed_query = database_manager.execute_read_query.await_args.args[0]
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
    database_manager.execute_read_query = AsyncMock(return_value=([{"id": 1}], None))
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

    executed_query = database_manager.execute_read_query.await_args.args[0]
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
    database_manager.execute_read_query = AsyncMock(return_value=([{"value": 1}], None))
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

    executed_query = database_manager.execute_read_query.await_args.args[0]
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
