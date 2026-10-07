"""Tests for constant-memory Train Data Source CSV writing."""

from __future__ import annotations

import asyncio
import csv
import gc
import tracemalloc
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import ml_utils


async def _chunks(columns, rows, chunk_size=2):
    yield columns, []
    for start in range(0, len(rows), chunk_size):
        yield columns, rows[start : start + chunk_size]


def _legacy_csv_output(file_path: Path) -> bytes:
    with file_path.open("r", encoding="utf-8") as handle:
        sample = handle.read(1024)
        handle.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample).delimiter
        except Exception:
            delimiter = ","
        rows = [
            {key: value if value != "" else None for key, value in row.items()}
            for row in csv.DictReader(handle, delimiter=delimiter)
        ]

    if not rows:
        return b""
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


@pytest.mark.asyncio
async def test_streamed_file_matches_legacy_writer_byte_for_byte(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    columns = [
        "integer",
        "float",
        "decimal",
        "boolean",
        "datetime",
        "date",
        "nan",
        "optional",
        "large_integer",
        "bytes",
        "string",
    ]
    rows = [
        (
            1,
            0.75,
            Decimal("12.34"),
            True,
            datetime(2026, 9, 23, 12, 30, 45),
            date(2026, 9, 23),
            float("nan"),
            None,
            9_007_199_254_740_993,
            b"bytes",
            'comma, quote " and\nnewline',
        ),
    ]

    streamed, actual_columns, count, preview = await ml_utils.stream_rows_to_csv(
        _chunks(columns, rows),
        "streamed",
        max_rows=100,
        max_bytes=1_000_000,
    )
    legacy = await ml_utils.save_data_to_csv(
        [dict(zip(columns, row)) for row in rows],
        columns,
        "legacy",
    )

    assert actual_columns == columns
    assert count == len(rows)
    assert preview == ml_utils.sanitize_for_json([dict(zip(columns, rows[0]))])
    assert Path(streamed).read_bytes() == Path(legacy).read_bytes()
    assert pd.isna(pd.read_csv(streamed).loc[0, "nan"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "contents"),
    [
        ("plain", b"id,name\n1,Ada\n2,Linus\n"),
        (
            "quoted-newline",
            b'id,note,value\n1,"comma,quote and\nnewline",x\n2,plain,y\n',
        ),
        ("unicode", "id,city\n1,Tiranë\n".encode()),
        ("semicolon", b"id;name\n1;Ada\n"),
        ("blank-lines", b"id,name\n\n1,Ada\n\n2,Linus\n"),
        ("short-row", b"id,name,note\n1,Ada\n"),
        ("duplicate-header", b"a,a,b\n1,2,3\n"),
    ],
)
async def test_uploaded_csv_stream_matches_legacy_output(
    monkeypatch, tmp_path, name, contents
):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / f"{name}.csv"
    source.write_bytes(contents)

    streamed, _, _, _ = await ml_utils.stream_rows_to_csv(
        ml_utils.iter_csv_chunks(str(source), chunk_size=2),
        f"streamed-{name}",
        max_rows=100,
        max_bytes=1_000_000,
        source_kind="csv",
    )

    assert Path(streamed).read_bytes() == _legacy_csv_output(source)


@pytest.mark.asyncio
async def test_uploaded_csv_preserves_valid_utf8(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "utf8.csv"
    source.write_text("id,city\n1,Tiranë\n2,東京\n", encoding="utf-8")

    streamed, columns, count, preview = await ml_utils.stream_rows_to_csv(
        ml_utils.iter_csv_chunks(str(source), chunk_size=1),
        "valid-utf8",
        max_rows=100,
        max_bytes=1_000_000,
        source_kind="csv",
    )

    assert columns == ["id", "city"]
    assert count == 2
    assert preview == [
        {"id": "1", "city": "Tiranë"},
        {"id": "2", "city": "東京"},
    ]
    assert Path(streamed).read_text(encoding="utf-8") == (
        "id,city\n1,Tiranë\n2,東京\n"
    )
    assert "�" not in Path(streamed).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_uploaded_csv_strips_utf8_bom_from_first_header(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "excel-utf8.csv"
    source.write_bytes(b"\xef\xbb\xbfid,name\n1,Ada\n")

    streamed, columns, count, preview = await ml_utils.stream_rows_to_csv(
        ml_utils.iter_csv_chunks(str(source), chunk_size=2),
        "utf8-bom",
        max_rows=100,
        max_bytes=1_000_000,
        source_kind="csv",
    )

    assert columns == ["id", "name"]
    assert count == 1
    assert preview == [{"id": "1", "name": "Ada"}]
    assert Path(streamed).read_bytes() == b"id,name\n1,Ada\n"


@pytest.mark.asyncio
async def test_uploaded_csv_rejects_invalid_utf8_and_removes_partial_output(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "invalid-utf8.csv"
    valid_prefix = b"id,name\n" + b"".join(
        f"{index},name-{index}\n".encode("utf-8") for index in range(1_000)
    )
    source.write_bytes(valid_prefix + b"1000,TOP-SECRET-\xff\n")

    with pytest.raises(AppException) as exc_info:
        await ml_utils.stream_rows_to_csv(
            ml_utils.iter_csv_chunks(str(source), chunk_size=10),
            "invalid-utf8",
            max_rows=2_000,
            max_bytes=1_000_000,
            source_kind="csv",
        )

    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_ENCODING_INVALID
    assert exc_info.value.error_detail == (
        "The uploaded CSV could not be decoded as UTF-8. "
        "Save it with UTF-8 encoding and upload it again."
    )
    assert "TOP-SECRET" not in exc_info.value.error_detail
    assert "�" not in exc_info.value.error_detail
    assert not list((tmp_path / "train" / "invalid-utf8").glob("*.csv"))


@pytest.mark.asyncio
async def test_uploaded_header_only_csv_preserves_columns(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "header-only.csv"
    source.write_text("third,first,second\n", encoding="utf-8")

    streamed, columns, count, preview = await ml_utils.stream_rows_to_csv(
        ml_utils.iter_csv_chunks(str(source), chunk_size=2),
        "header-only",
        max_rows=100,
        max_bytes=1_000_000,
        source_kind="csv",
    )

    assert columns == ["third", "first", "second"]
    assert count == 0
    assert preview == []
    assert Path(streamed).read_text(encoding="utf-8") == "third,first,second\n"


@pytest.mark.asyncio
async def test_uploaded_csv_rejects_row_longer_than_header(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "extra-value.csv"
    source.write_text("id,name\n1,Ada,EXTRA\n2,Linus\n", encoding="utf-8")

    with pytest.raises(AppException) as exc_info:
        await ml_utils.stream_rows_to_csv(
            ml_utils.iter_csv_chunks(str(source), chunk_size=2),
            "extra-value",
            max_rows=100,
            max_bytes=1_000_000,
            source_kind="csv",
        )

    assert exc_info.value.error_detail == (
        "Line 2 has more values than the header has columns."
    )
    assert not list((tmp_path / "train" / "extra-value").glob("*.csv"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "contents",
    [
        "id,name\n\n\n1,Ada\n2,Linus,EXTRA\n",
        'id,note\n0,plain\n1,"first\nsecond\nthird",EXTRA\n',
    ],
)
async def test_uploaded_csv_error_uses_physical_line_number(
    monkeypatch, tmp_path, contents
):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "physical-line.csv"
    source.write_text(contents, encoding="utf-8")

    with pytest.raises(AppException) as exc_info:
        await ml_utils.stream_rows_to_csv(
            ml_utils.iter_csv_chunks(str(source), chunk_size=2),
            "physical-line",
            max_rows=100,
            max_bytes=1_000_000,
            source_kind="csv",
        )

    assert exc_info.value.error_detail == (
        "Line 5 has more values than the header has columns."
    )


@pytest.mark.asyncio
async def test_uploaded_csv_row_cap_stops_early_with_csv_wording(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "row-cap.csv"
    source.write_text(
        "id\n" + "".join(f"{index}\n" for index in range(20)),
        encoding="utf-8",
    )

    with pytest.raises(AppException) as exc_info:
        await ml_utils.stream_rows_to_csv(
            ml_utils.iter_csv_chunks(str(source), chunk_size=4),
            "csv-row-limit",
            max_rows=10,
            max_bytes=1_000_000,
            source_kind="csv",
        )

    assert "CSV file returned more than 10 rows" in exc_info.value.error_detail
    assert "Use a smaller file" in exc_info.value.error_detail
    assert "LIMIT" not in exc_info.value.error_detail
    assert not list((tmp_path / "train" / "csv-row-limit").glob("*.csv"))


@pytest.mark.asyncio
async def test_uploaded_csv_output_byte_cap_uses_csv_wording(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)

    with pytest.raises(AppException) as exc_info:
        await ml_utils.stream_rows_to_csv(
            _chunks(["a"], [("é" * 20,)]),
            "csv-byte-limit",
            max_rows=100,
            max_bytes=10,
            source_kind="csv",
        )

    assert "The CSV file is" in exc_info.value.error_detail
    assert "Use a smaller file" in exc_info.value.error_detail
    assert "LIMIT" not in exc_info.value.error_detail
    assert not list((tmp_path / "train" / "csv-byte-limit").glob("*.csv"))


@pytest.mark.asyncio
async def test_uploaded_csv_timeout_removes_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "large.csv"
    source.write_text(
        "id,value\n"
        + "".join(f"{index},value-{index}\n" for index in range(50_000)),
        encoding="utf-8",
    )

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            ml_utils.stream_rows_to_csv(
                ml_utils.iter_csv_chunks(str(source), chunk_size=100),
                "csv-timeout",
                max_rows=100_000,
                max_bytes=10_000_000,
                source_kind="csv",
            ),
            timeout=0.001,
        )

    assert not list((tmp_path / "train" / "csv-timeout").glob("*.csv"))


@pytest.mark.asyncio
async def test_row_cap_stops_stream_and_removes_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)

    with pytest.raises(AppException) as exc_info:
        await ml_utils.stream_rows_to_csv(
            _chunks(["id"], [(index,) for index in range(6)], chunk_size=2),
            "row-limit",
            max_rows=5,
            max_bytes=1_000_000,
        )

    assert "returned more than 5 rows" in exc_info.value.error_detail
    assert "limit of 5" in exc_info.value.error_detail
    assert not list((tmp_path / "train" / "row-limit").glob("*.csv"))


@pytest.mark.asyncio
async def test_byte_cap_removes_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)

    with pytest.raises(AppException) as exc_info:
        await ml_utils.stream_rows_to_csv(
            _chunks(["value"], [("é" * 20,)]),
            "byte-limit",
            max_rows=100,
            max_bytes=10,
        )

    assert "bytes" in exc_info.value.error_detail
    assert "limit of 10 bytes" in exc_info.value.error_detail
    assert not list((tmp_path / "train" / "byte-limit").glob("*.csv"))


@pytest.mark.asyncio
async def test_database_failure_removes_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)

    async def failing_chunks():
        yield ["id"], [(1,)]
        raise RuntimeError("connection lost")

    with pytest.raises(RuntimeError, match="connection lost"):
        await ml_utils.stream_rows_to_csv(
            failing_chunks(),
            "database-failure",
            max_rows=100,
            max_bytes=1_000_000,
        )

    assert not list((tmp_path / "train" / "database-failure").glob("*.csv"))


@pytest.mark.asyncio
async def test_timeout_cancellation_removes_partial_file_and_closes_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    closed = False

    async def slow_chunks():
        nonlocal closed
        try:
            yield ["id"], [(1,)]
            await asyncio.Event().wait()
        finally:
            closed = True

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            ml_utils.stream_rows_to_csv(
                slow_chunks(),
                "timeout",
                max_rows=100,
                max_bytes=1_000_000,
            ),
            timeout=0.01,
        )

    assert closed is True
    assert not list((tmp_path / "train" / "timeout").glob("*.csv"))


@pytest.mark.asyncio
async def test_empty_stream_writes_headers_and_preserves_column_order(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    columns = ["third", "first", "second"]

    streamed, actual_columns, count, preview = await ml_utils.stream_rows_to_csv(
        _chunks(columns, []),
        "empty",
        max_rows=100,
        max_bytes=1_000_000,
    )

    assert actual_columns == columns
    assert count == 0
    assert preview == []
    assert Path(streamed).read_text(encoding="utf-8") == "third,first,second\n"


@pytest.mark.asyncio
async def test_preview_keeps_first_and_last_three_without_guessing_types(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    columns = ["id", "city", "occupied", "ratio", "missing"]
    rows = [
        (index, f"city-{index}", index % 2 == 0, index + 0.25, None)
        for index in range(10)
    ]
    _, _, _, preview = await ml_utils.stream_rows_to_csv(
        _chunks(columns, rows),
        "preview",
        max_rows=100,
        max_bytes=1_000_000,
    )

    expected_rows = rows[:3] + rows[-3:]
    assert preview == [dict(zip(columns, row)) for row in expected_rows]
    for row in preview:
        assert type(row["id"]) is int
        assert type(row["city"]) is str
        assert type(row["occupied"]) is bool
        assert type(row["ratio"]) is float
        assert row["missing"] is None


@pytest.mark.asyncio
async def test_uploaded_csv_preview_preserves_codes_and_na(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "codes.csv"
    source.write_text(
        "code,country,amount\n007,NA,1\n010,AL,2\n",
        encoding="utf-8",
    )

    _, _, _, preview = await ml_utils.stream_rows_to_csv(
        ml_utils.iter_csv_chunks(str(source), chunk_size=2),
        "codes",
        max_rows=100,
        max_bytes=1_000_000,
        source_kind="csv",
    )

    assert preview == [
        {"code": "007", "country": "NA", "amount": "1"},
        {"code": "010", "country": "AL", "amount": "2"},
    ]


@pytest.mark.asyncio
async def test_streaming_memory_does_not_scale_with_total_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)

    async def generated_chunks(total_rows):
        columns = ["id", "value"]
        yield columns, []
        for start in range(0, total_rows, 1_000):
            stop = min(start + 1_000, total_rows)
            yield columns, [(index, f"value-{index}") for index in range(start, stop)]

    async def peak_for(total_rows):
        gc.collect()
        tracemalloc.start()
        await ml_utils.stream_rows_to_csv(
            generated_chunks(total_rows),
            f"memory-{total_rows}",
            max_rows=total_rows,
            max_bytes=100_000_000,
        )
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak

    peak_small = await peak_for(1_000)
    peak_large = await peak_for(100_000)

    assert peak_large < peak_small * 3


@pytest.mark.asyncio
async def test_uploaded_csv_memory_does_not_scale_with_total_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)

    def source_for(total_rows):
        source = tmp_path / f"source-{total_rows}.csv"
        with source.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["id", "value"])
            for index in range(total_rows):
                writer.writerow([index, f"value-{index}"])
        return source

    async def peak_for(total_rows):
        source = source_for(total_rows)
        gc.collect()
        tracemalloc.start()
        await ml_utils.stream_rows_to_csv(
            ml_utils.iter_csv_chunks(str(source), chunk_size=1_000),
            f"csv-memory-{total_rows}",
            max_rows=total_rows,
            max_bytes=100_000_000,
            source_kind="csv",
        )
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak

    peak_small = await peak_for(20_000)
    peak_large = await peak_for(200_000)

    assert peak_large < peak_small * 1.5
