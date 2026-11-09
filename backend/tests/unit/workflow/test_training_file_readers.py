"""Streaming readers for Parquet, Excel and JSON training files."""

import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from openpyxl import Workbook

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.error_policy import client_safe_error_detail
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode
from app.modules.workflow.engine.nodes.ml.training_file_readers import (
    TrainingFileReader,
    ensure_supported_training_file,
    read_training_file_preview,
)
from app.modules.workflow.engine.workflow_state import WorkflowState

MODULE = "app.modules.workflow.engine.nodes.ml.train_data_source_node"


def _node() -> TrainDataSourceNode:
    state = WorkflowState(workflow={})
    state.thread_id = "thread-1"
    return TrainDataSourceNode(node_id="node-1", node_config={"data": {}}, state=state)


async def _read_all(reader: TrainingFileReader):
    columns, rows, chunk_sizes = [], [], []
    async for chunk_columns, chunk_rows in reader.chunks():
        columns = chunk_columns
        if chunk_rows:
            chunk_sizes.append(len(chunk_rows))
            rows.extend(chunk_rows)
    return columns, rows, chunk_sizes


def _typed_frame(n: int = 6) -> pd.DataFrame:
    return pd.DataFrame({
        "code": [f"{i:03d}" for i in range(n)],  # text that looks numeric
        "count": pd.array([i if i % 3 else None for i in range(n)], dtype="Int64"),
        "active": [i % 2 == 0 for i in range(n)],
        "price": [1.5 * i for i in range(n)],
        "when": pd.date_range("2025-01-01", periods=n, freq="D"),
        "size": pd.Categorical(["S", "M", "L"] * (n // 3)),
        "tags": [["a", "b"] if i % 2 else [] for i in range(n)],
    })


# -- Supported types ---------------------------------------------------------

@pytest.mark.parametrize("name", ["a.csv", "a.parquet", "a.xlsx", "a.xlsm", "a.json", "a.jsonl", "a.NDJSON"])
def test_supported_suffixes(name):
    assert ensure_supported_training_file(name) == Path(name).suffix.lower()


def test_xls_gets_save_as_xlsx_hint():
    with pytest.raises(AppException) as exc_info:
        ensure_supported_training_file("old.xls")
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_UNSUPPORTED
    assert "save it as .xlsx" in exc_info.value.error_detail


def test_unknown_suffix_lists_supported_types():
    with pytest.raises(AppException) as exc_info:
        ensure_supported_training_file("notes.txt")
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_UNSUPPORTED
    assert ".parquet" in exc_info.value.error_detail and ".jsonl" in exc_info.value.error_detail


# -- Parquet -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_parquet_streams_row_groups_in_chunks(tmp_path):
    path = tmp_path / "big.parquet"
    pq.write_table(pa.table({"x": list(range(1000))}), path, row_group_size=100)

    columns, rows, chunk_sizes = await _read_all(TrainingFileReader(path, 250))

    assert columns == ["x"]
    assert [r[0] for r in rows] == list(range(1000))
    assert max(chunk_sizes) <= 250 and len(chunk_sizes) >= 4


@pytest.mark.asyncio
async def test_parquet_row_limit_fails_from_metadata_before_reading(tmp_path, monkeypatch):
    path = tmp_path / "big.parquet"
    pq.write_table(pa.table({"x": list(range(500))}), path)
    monkeypatch.setattr(pq.ParquetFile, "iter_batches", lambda *a, **k: pytest.fail("rows were read"))

    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 100, max_rows=499))

    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED
    assert "500 rows" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_parquet_values_and_types(tmp_path):
    path = tmp_path / "typed.parquet"
    _typed_frame().to_parquet(path, index=False)
    reader = TrainingFileReader(path, 4)

    columns, rows, _ = await _read_all(reader)

    first, second = dict(zip(columns, rows[0])), dict(zip(columns, rows[1]))
    assert first["code"] == "000"
    assert first["count"] is None and second["count"] == 1
    assert first["when"].startswith("2025-01-01")
    assert json.loads(second["tags"]) == ["a", "b"]
    assert reader.column_dtypes() == {
        "code": "object", "count": "Int64", "active": "boolean", "price": "float64",
        "when": "datetime64[ns]", "size": "category", "tags": "object",
    }


@pytest.mark.asyncio
async def test_corrupt_parquet_is_a_clear_error(tmp_path):
    path = tmp_path / "broken.parquet"
    path.write_bytes(b"not parquet at all")
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_INVALID
    assert "Parquet" in exc_info.value.error_detail


# -- Excel -------------------------------------------------------------------

def _workbook(path: Path, sheets: dict) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    wb.save(path)
    return path


@pytest.mark.asyncio
async def test_excel_first_sheet_by_default_and_named_sheet(tmp_path):
    path = _workbook(tmp_path / "book.xlsx", {
        "First": [["a", "b"], [1, "x"]],
        "Second": [["c"], [10], [None], [20]],  # a blank row is skipped
    })

    columns, rows, _ = await _read_all(TrainingFileReader(path, 10))
    assert (columns, rows) == (["a", "b"], [(1, "x")])

    columns, rows, _ = await _read_all(TrainingFileReader(path, 10, sheet_name="Second"))
    assert (columns, rows) == (["c"], [(10,), (20,)])


@pytest.mark.asyncio
async def test_excel_unknown_sheet_lists_sheet_names(tmp_path):
    path = _workbook(tmp_path / "book.xlsx", {"Sales": [["a"], [1]], "Costs": [["b"], [2]]})
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10, sheet_name="Revenue"))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID
    assert "Sheets: Sales, Costs" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_excel_types_and_dates(tmp_path):
    path = _workbook(tmp_path / "typed.xlsx", {"S": [
        ["n", "flag", "when", "code"],
        [1, True, dt.datetime(2025, 3, 1), "001"],
        [None, False, dt.datetime(2025, 3, 2), "002"],
    ]})
    reader = TrainingFileReader(path, 10)
    columns, rows, _ = await _read_all(reader)
    assert rows[0] == (1, True, "2025-03-01T00:00:00", "001")
    assert reader.column_dtypes() == {"n": "Int64", "flag": "boolean", "when": "datetime64[ns]", "code": "object"}


@pytest.mark.asyncio
@pytest.mark.parametrize("rows, message", [
    ([["a", "a"], [1, 2]], "two columns named 'a'"),
    ([["a"], [1, 2]], "Row 2 of sheet 'S' has more values than the header"),
    ([], "is empty"),
])
async def test_excel_layout_errors(tmp_path, rows, message):
    path = _workbook(tmp_path / "bad.xlsx", {"S": rows})
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_INVALID
    assert message in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_file_that_is_not_a_workbook(tmp_path):
    path = tmp_path / "fake.xlsx"
    path.write_text("a,b\n1,2\n")
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_INVALID


# -- JSON Lines --------------------------------------------------------------

@pytest.mark.asyncio
async def test_jsonl_rows_with_different_keys_line_up(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"a": 1}\n\n{"b": "x", "a": 2}\n{"c": [1, 2]}\n', encoding="utf-8")

    columns, rows, _ = await _read_all(TrainingFileReader(path, 2))

    assert columns == ["a", "b", "c"]
    assert rows == [(1, None, None), (2, "x", None), (None, None, "[1, 2]")]


@pytest.mark.asyncio
@pytest.mark.parametrize("content, message", [
    ('{"a": 1}\n{"a": \n', "Line 2 isn't valid JSON"),
    ('{"a": 1}\n[1, 2]\n', "Line 2 is a JSON list, not an object"),
    ("\n\n", "has no records"),
])
async def test_jsonl_errors_name_the_line(tmp_path, content, message):
    path = tmp_path / "rows.jsonl"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_INVALID
    assert message in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_jsonl_row_limit_before_writing(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text("".join(f'{{"i": {i}}}\n' for i in range(5)), encoding="utf-8")
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10, max_rows=3))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_non_utf8_jsonl(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_bytes('{"name": "café"}\n'.encode("latin-1"))
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_ENCODING_INVALID


# -- JSON arrays -------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("content", [
    '[{"a": "true", "b": null}, {"a": "001"}]',
    '{"data": [{"a": "true", "b": null}, {"a": "001"}]}',
    '{"a": "true", "b": null}\n{"a": "001"}\n',  # JSON Lines saved as .json
])
async def test_json_shapes_and_values_kept_as_written(tmp_path, content):
    path = tmp_path / "rows.json"
    path.write_text(content, encoding="utf-8")
    columns, rows, _ = await _read_all(TrainingFileReader(path, 10))
    assert columns == ["a", "b"]
    assert rows == [("true", None), ("001", None)]


@pytest.mark.asyncio
async def test_large_json_array_points_to_jsonl(tmp_path):
    path = tmp_path / "rows.json"
    path.write_text('[{"a": 1}, {"a": 2}]', encoding="utf-8")
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10, json_max_bytes=5))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED
    assert ".jsonl" in exc_info.value.error_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("content, message", [
    ('[{"a": 1}, 5]', "Item 2 of the JSON array is a int"),
    ('{"a": 1, "b": 2}', "must hold an array of objects"),
    ('[{"a": 1}', "isn't valid JSON"),
])
async def test_json_errors(tmp_path, content, message):
    path = tmp_path / "rows.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(AppException) as exc_info:
        await _read_all(TrainingFileReader(path, 10))
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_INVALID
    assert message in exc_info.value.error_detail


# -- Node: types survive, nothing left behind --------------------------------

@pytest.mark.asyncio
async def test_parquet_through_node_keeps_types_for_the_next_node(monkeypatch, tmp_path):
    source = tmp_path / "typed.parquet"
    _typed_frame().to_parquet(source, index=False)
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)

    result = await _node().process({"sourceType": "csv", "csvFilePath": str(source)})

    assert result["metadata"]["rowCount"] == 6
    reloaded = ml_utils.read_csv_with_dtypes(ml_utils.DATA_VOLUME / "train" / result["data_path"])
    assert reloaded["code"].tolist()[:2] == ["000", "001"]
    assert str(reloaded["count"].dtype) == "Int64" and reloaded["count"].isna().sum() == 2
    assert str(reloaded["active"].dtype) == "boolean"
    assert str(reloaded["when"].dtype).startswith("datetime64")
    assert str(reloaded["size"].dtype) == "category"


@pytest.mark.asyncio
async def test_excel_sheet_name_from_node_config(monkeypatch, tmp_path):
    source = _workbook(tmp_path / "book.xlsx", {"A": [["x"], [1]], "B": [["y"], [2], [3]]})
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)

    result = await _node().process({"sourceType": "csv", "csvFilePath": str(source), "sheetName": "B"})

    assert result["metadata"] == {"rowCount": 2, "columns": ["y"]}


@pytest.mark.asyncio
async def test_failed_extraction_removes_output_and_downloaded_copy(monkeypatch, tmp_path):
    source = tmp_path / "rows.jsonl"
    source.write_text('{"a": 1}\n{"a": \n', encoding="utf-8")
    copies = []

    async def copy_download(_file_id, destination):
        copies.append(Path(destination))
        Path(destination).write_bytes(source.read_bytes())

    file_manager = MagicMock()
    file_manager.download_file_to_path = AsyncMock(side_effect=copy_download)
    file_manager.get_file_by_id = AsyncMock(
        return_value=SimpleNamespace(name="rows.jsonl", size=source.stat().st_size)
    )
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)
    monkeypatch.setattr("app.dependencies.injector.injector.get", lambda _service: file_manager)

    with pytest.raises(AppException) as exc_info:
        await _node().process({"sourceType": "csv", "csvFileId": "f-1", "csvFileName": "rows.jsonl"})

    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_INVALID
    assert copies and not copies[0].exists()
    assert not list((tmp_path / "train").rglob("*.csv"))
    assert not list((tmp_path / "train").rglob("*.dtypes.json"))


# -- Preview -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_reads_only_the_first_rows(tmp_path):
    path = tmp_path / "big.parquet"
    pq.write_table(pa.table({"x": list(range(1000))}), path, row_group_size=100)

    frame, total, truncated = await read_training_file_preview(path, 150)

    assert len(frame) == 150 and total == 1000 and truncated


@pytest.mark.asyncio
async def test_preview_of_a_small_file_is_complete_and_typed(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"n": 1, "f": true}\n{"n": null, "f": false}\n', encoding="utf-8")

    frame, total, truncated = await read_training_file_preview(path, 100)

    assert (len(frame), total, truncated) == (2, 2, False)
    assert str(frame["n"].dtype) == "Int64" and str(frame["f"].dtype) == "boolean"


@pytest.mark.asyncio
async def test_csv_preview_types_columns_like_read_csv(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("price,qty,size,ok\n1.5,3,M,True\n,4,L,False\n", encoding="utf-8")

    frame, total, truncated = await read_training_file_preview(path, 100)

    assert (len(frame), total, truncated) == (2, 2, False)
    assert frame["price"].dtype == "float64" and frame["qty"].dtype == "int64"
    assert frame["size"].dtype == object and frame["ok"].dtype == bool
    assert ml_utils.analyze_dataframe(frame)["columns_info"][0]["type"] == "numeric"


@pytest.mark.asyncio
async def test_jsonl_preview_stops_scanning_after_the_preview_rows(tmp_path):
    path = tmp_path / "rows.jsonl"
    # The line after the preview rows is invalid: the preview must not read it.
    path.write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\nnot json\n', encoding="utf-8")

    frame, total, truncated = await read_training_file_preview(path, 2)

    assert list(frame["a"]) == [1, 2] and total is None and truncated


@pytest.mark.asyncio
async def test_jsonl_preview_with_exactly_the_preview_rows_is_complete(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"a": 1}\n{"a": 2}\n\n', encoding="utf-8")

    frame, total, truncated = await read_training_file_preview(path, 2)

    assert (len(frame), total, truncated) == (2, 2, False)


@pytest.mark.asyncio
async def test_json_preview_uses_the_configured_size_limit(tmp_path):
    path = tmp_path / "rows.json"
    path.write_text(json.dumps([{"a": i} for i in range(50)]), encoding="utf-8")

    with pytest.raises(AppException) as exc_info:
        await read_training_file_preview(path, 10, json_max_bytes=100)

    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED


# -- Duplicate column names (TDS-28) ------------------------------------------

DUPLICATE_SCORE = {
    "data.csv": "id,score,score\n1,10,99\n2,20,88\n",
    "data.json": '[{"id": 1, "score": 10, "score": 99}, {"id": 2, "score": 20, "score": 88}]',
    "data.jsonl": '{"id": 1, "score": 10, "score": 99}\n{"id": 2, "score": 20, "score": 88}\n',
}


async def _run_and_preview_errors(monkeypatch, tmp_path, path):
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)
    with pytest.raises(AppException) as run:
        await _node().process({"sourceType": "csv", "csvFilePath": str(path)})
    with pytest.raises(AppException) as preview:
        await read_training_file_preview(path, 100)
    assert not list((tmp_path / "train").rglob("*.csv"))
    return run.value, preview.value


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(DUPLICATE_SCORE))
async def test_duplicate_columns_are_refused_by_run_and_preview_alike(monkeypatch, tmp_path, name):
    path = tmp_path / name
    path.write_text(DUPLICATE_SCORE[name], encoding="utf-8")

    run, preview = await _run_and_preview_errors(monkeypatch, tmp_path, path)

    assert run.error_key == preview.error_key == ErrorKey.ML_EXTRACT_FILE_INVALID
    assert run.error_detail == preview.error_detail
    assert "two columns named 'score'" in run.error_detail
    assert "unique name" in run.error_detail


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        # Names are compared after strip(), as Parquet and Excel headers are.
        ("spaces.csv", "id,score, score \n1,10,99\n", "two columns named 'score'"),
        ("blank.csv", "id,,,x\n1,2,3,4\n", "two columns with no name"),
        ("keys.json", '[{"id": 1, "score": 10}, {"id": 2, " score": 20}]', "two columns named 'score'"),
        ("keys.jsonl", '{"id": 1, "score": 10, "score ": 99}\n', "two columns named 'score'"),
    ],
)
async def test_names_that_repeat_once_stripped_are_refused(monkeypatch, tmp_path, name, content, message):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")

    run, preview = await _run_and_preview_errors(monkeypatch, tmp_path, path)

    assert message in run.error_detail and run.error_detail == preview.error_detail


@pytest.mark.asyncio
async def test_case_still_tells_columns_apart(monkeypatch, tmp_path):
    path = tmp_path / "case.csv"
    path.write_text("Score,score\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)

    result = await _node().process({"sourceType": "csv", "csvFilePath": str(path)})

    assert result["metadata"]["columns"] == ["Score", "score"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "content", "columns"),
    [
        ("plain.csv", "id, score\n1,10\n", ["id", " score"]),
        ("plain.json", '[{"id": 1, "score": 10}]', ["id", "score"]),
        ("plain.jsonl", '{"id": 1, "score": 10}\n', ["id", "score"]),
    ],
)
async def test_unique_headers_come_out_unchanged(monkeypatch, tmp_path, name, content, columns):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)

    result = await _node().process({"sourceType": "csv", "csvFilePath": str(path)})
    frame, _, _ = await read_training_file_preview(path, 100)

    assert result["metadata"]["columns"] == columns == list(frame.columns)
    assert pd.read_csv(result["data_path"]).iloc[0].tolist() == [1, 10]


@pytest.mark.asyncio
async def test_repeated_key_inside_a_nested_value_is_not_a_column(tmp_path):
    path = tmp_path / "nested.jsonl"
    path.write_text('{"id": 1, "meta": {"a": 1, "a": 2}}\n', encoding="utf-8")

    columns, rows, _ = await _read_all(TrainingFileReader(path, 10))

    assert columns == ["id", "meta"] and rows == [(1, '{"a": 2}')]


@pytest.mark.asyncio
async def test_csv_trailing_unnamed_empty_columns_are_dropped_like_excel(monkeypatch, tmp_path):
    path = tmp_path / "export.csv"
    path.write_text("price,size,,\n10,M,,\n12,L\n", encoding="utf-8")
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)

    result = await _node().process({"sourceType": "csv", "csvFilePath": str(path)})
    frame, _, _ = await read_training_file_preview(path, 100)

    assert result["metadata"]["columns"] == ["price", "size"] == list(frame.columns)
    assert Path(result["data_path"]).read_text(encoding="utf-8") == "price,size\n10,M\n12,L\n"


@pytest.mark.asyncio
async def test_csv_value_under_a_trailing_unnamed_column_is_refused(monkeypatch, tmp_path):
    path = tmp_path / "export.csv"
    path.write_text("price,size,,\n10,M,,\n12,L,,x\n", encoding="utf-8")

    run, preview = await _run_and_preview_errors(monkeypatch, tmp_path, path)

    assert run.error_detail == preview.error_detail
    assert "Line 3 has a value in column 4" in run.error_detail
    # The API shows only allow-listed details; anything else becomes "Invalid file format."
    assert client_safe_error_detail(run) == run.error_detail


@pytest.mark.asyncio
async def test_csv_row_with_more_values_than_the_header_reaches_the_client(monkeypatch, tmp_path):
    path = tmp_path / "wide.csv"
    path.write_text("price,size\n10,M\n12,L,x\n", encoding="utf-8")

    run, preview = await _run_and_preview_errors(monkeypatch, tmp_path, path)

    assert run.error_detail == preview.error_detail
    assert "Line 3 has more values than the header has columns" in run.error_detail
    assert client_safe_error_detail(run) == run.error_detail


@pytest.mark.asyncio
async def test_csv_whitespace_under_a_trailing_unnamed_column_is_dropped(monkeypatch, tmp_path):
    # The header cell is blank once stripped, so a blank-once-stripped value is too.
    path = tmp_path / "export.csv"
    path.write_text("price,size, ,\n10,M, ,\n12,L,,  \n", encoding="utf-8")
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)

    result = await _node().process({"sourceType": "csv", "csvFilePath": str(path)})

    assert result["metadata"]["columns"] == ["price", "size"]
    assert Path(result["data_path"]).read_text(encoding="utf-8") == "price,size\n10,M\n12,L\n"


@pytest.mark.asyncio
async def test_csv_single_leading_unnamed_column_is_kept(monkeypatch, tmp_path):
    # pandas' to_csv() writes the index under an empty header.
    path = tmp_path / "pandas.csv"
    path.write_text(",a\n0,1\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(f"{MODULE}.ml_utils.DATA_VOLUME", tmp_path)

    result = await _node().process({"sourceType": "csv", "csvFilePath": str(path)})

    assert result["metadata"]["columns"] == ["", "a"]


@pytest.mark.asyncio
async def test_json_wrapper_with_a_repeated_key_is_refused(monkeypatch, tmp_path):
    path = tmp_path / "wrapped.json"
    path.write_text('{"rows": [{"id": 1}], "rows": [{"id": 2}]}', encoding="utf-8")

    run, preview = await _run_and_preview_errors(monkeypatch, tmp_path, path)

    assert "two keys named 'rows'" in run.error_detail
    assert run.error_detail == preview.error_detail


@pytest.mark.asyncio
async def test_json_wrapper_with_a_repeated_metadata_key_is_read(tmp_path):
    # Only the rows array is read; a repeated key beside it loses no row.
    path = tmp_path / "wrapped.json"
    path.write_text(
        '{"count": 1, "count": 2, "rows": [{"id": 1}, {"id": 2}]}', encoding="utf-8"
    )

    frame, _, _ = await read_training_file_preview(path, 10)

    assert frame["id"].tolist() == [1, 2]


@pytest.mark.asyncio
async def test_json_lines_saved_as_json_names_the_line(monkeypatch, tmp_path):
    path = tmp_path / "lines.json"
    path.write_text('{"id": 1}\n\n{"id": 2, "id": 3}\n', encoding="utf-8")

    run, _ = await _run_and_preview_errors(monkeypatch, tmp_path, path)

    assert run.error_detail.startswith("Line 3 has two columns named 'id'")


@pytest.mark.asyncio
async def test_long_duplicate_name_is_shortened_in_the_message(monkeypatch, tmp_path):
    name = "x" * 500
    path = tmp_path / "long.csv"
    path.write_text(f"{name},{name}\n1,2\n", encoding="utf-8")

    run, _ = await _run_and_preview_errors(monkeypatch, tmp_path, path)

    assert len(run.error_detail) < 200 and "xxx..." in run.error_detail
