"""Preview (/analyze-file) and profiling of Parquet, Excel and JSON training files."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import HTTPException
from openpyxl import Workbook
from starlette.requests import Request

from app.api.v1.routes import ml_models
from app.core.permissions.constants import Permissions as P


def _file_manager(source: Path | None = None, name: str | None = None) -> MagicMock:
    manager = MagicMock()

    async def copy(_file_id, destination):
        Path(destination).write_bytes(source.read_bytes())

    manager.download_file_to_path = AsyncMock(side_effect=copy)
    manager.extract_file_id_from_url = AsyncMock(return_value=None)
    record_name = name or (source.name if source else None)
    manager.get_file_by_id = AsyncMock(
        return_value=SimpleNamespace(name=record_name) if record_name else None
    )
    return manager


def _request() -> Request:
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.user = SimpleNamespace(permissions={P.MlModel.READ, P.FileManager.READ})
    return request


async def _analyze(analyze_request, manager):
    return await ml_models.analyze_training_file(analyze_request, _request(), manager)


@pytest.fixture
def data_volume(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_models, "DATA_VOLUME", tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_parquet_by_file_id_previews_first_rows_with_exact_total(monkeypatch, tmp_path):
    source = tmp_path / "upload.parquet"
    pq.write_table(pa.table({"x": list(range(300)), "s": ["a", "b", "c"] * 100}), source, row_group_size=50)
    monkeypatch.setattr(ml_models.settings, "ML_PROFILE_MAX_ROWS", 120)
    manager = _file_manager(source)

    result = await _analyze(
        ml_models.AnalyzeFileRequest(file_id=uuid4(), file_name="sales.parquet"), manager
    )

    assert result["row_count"] == 300
    assert result["rows_analyzed"] == 120 and result["rows_truncated"] is True
    assert result["column_names"] == ["x", "s"]
    temp_copy = Path(manager.download_file_to_path.await_args.args[1])
    assert temp_copy.suffix == ".parquet" and not temp_copy.exists()


@pytest.mark.asyncio
async def test_extension_comes_from_the_file_record_when_no_name_given(tmp_path):
    source = tmp_path / "upload.jsonl"
    source.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    manager = _file_manager(source, name="events.jsonl")

    result = await _analyze(ml_models.AnalyzeFileRequest(file_id=uuid4()), manager)

    assert result["row_count"] == 2 and result["rows_truncated"] is False


@pytest.mark.asyncio
async def test_excel_preview_lists_sheets_and_reads_the_chosen_one(data_volume):
    path = data_volume / "book.xlsx"
    wb = Workbook()
    wb.active.title = "First"
    wb.active.append(["a"])
    wb.active.append([1])
    second = wb.create_sheet("Second")
    for row in (["b", "c"], [1, "x"], [2, "y"]):
        second.append(row)
    wb.save(path)

    default = await _analyze(
        ml_models.AnalyzeFileRequest(file_url=str(path)), _file_manager()
    )
    chosen = await _analyze(
        ml_models.AnalyzeFileRequest(file_url=str(path), sheet_name="Second"), _file_manager()
    )

    assert default["sheet_names"] == ["First", "Second"] and default["sheet_name"] == "First"
    assert default["column_names"] == ["a"]
    assert chosen["sheet_name"] == "Second" and chosen["row_count"] == 2
    assert chosen["column_names"] == ["b", "c"]


@pytest.mark.asyncio
async def test_unsupported_type_is_a_400_with_the_reason(data_volume):
    path = data_volume / "old.xls"
    path.write_bytes(b"x")
    with pytest.raises(HTTPException) as exc_info:
        await _analyze(ml_models.AnalyzeFileRequest(file_url=str(path)), _file_manager())
    assert exc_info.value.status_code == 400
    assert "save it as .xlsx" in exc_info.value.detail


@pytest.mark.asyncio
async def test_paths_outside_the_data_volume_are_refused(data_volume, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.parquet"
    pq.write_table(pa.table({"x": [1]}), outside)
    with pytest.raises(HTTPException) as exc_info:
        await _analyze(ml_models.AnalyzeFileRequest(file_url=str(outside)), _file_manager())
    # Same answer as a missing file, so the response doesn't reveal what exists outside.
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_invalid_file_is_a_400_and_temp_copy_is_removed(tmp_path):
    source = tmp_path / "broken.parquet"
    source.write_bytes(b"nope")
    manager = _file_manager(source)
    with pytest.raises(HTTPException) as exc_info:
        await _analyze(
            ml_models.AnalyzeFileRequest(file_id=uuid4(), file_name="broken.parquet"), manager
        )
    assert exc_info.value.status_code == 400 and "Parquet" in exc_info.value.detail
    assert not Path(manager.download_file_to_path.await_args.args[1]).exists()


@pytest.mark.asyncio
async def test_profile_parquet_by_file_id_uses_the_typed_preview(monkeypatch, tmp_path):
    source = tmp_path / "upload.parquet"
    pd.DataFrame({"n": pd.array([1, None, 3], dtype="Int64"), "s": ["a", "b", "c"]}).to_parquet(source)
    captured = {}

    def fake_report(frame, *, title, empty_detail):
        captured["dtypes"] = {c: str(t) for c, t in frame.dtypes.items()}
        captured["title"] = title
        return "<html>ok</html>"

    monkeypatch.setattr(ml_models, "_build_dataframe_profile_report_html", fake_report)
    response = await ml_models.profile_data(
        ml_models.ProfileDataRequest(file_id=uuid4(), file_name="sales.parquet"), _request(), _file_manager(source)
    )

    assert response.body == b"<html>ok</html>"
    assert captured["dtypes"]["n"] == "Int64"
    assert "sales.parquet" in captured["title"]
