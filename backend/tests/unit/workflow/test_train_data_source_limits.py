"""Resource-limit tests for the Train Data Source workflow node."""

import asyncio
import logging
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.config.settings import ProjectSettings, settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import train_data_source_node as module
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode
from app.modules.workflow.engine.workflow_state import WorkflowState


def _node() -> TrainDataSourceNode:
    node_config = {"id": "source-1", "type": "trainDataSourceNode", "data": {}}
    state = WorkflowState(
        workflow={
            "nodes": [node_config],
            "source_edges": {},
            "target_edges": {},
        },
        initial_values={},
        thread_id="thread-1",
    )
    return TrainDataSourceNode("source-1", node_config, state)


def _database_manager(rows):
    async def stream_query(*_args, **_kwargs):
        columns = list(rows[0]) if rows else ["a"]
        yield columns, []
        yield columns, [tuple(row[column] for column in columns) for row in rows]

    manager = Mock()
    manager.get_db_type.return_value = "postgresql"
    manager.stream_query = Mock(side_effect=stream_query)
    return manager


@pytest.mark.asyncio
async def test_row_cap_refuses_rather_than_truncates(monkeypatch):
    node = _node()
    manager = _database_manager([{"a": index} for index in range(11)])
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_ROWS", 10)
    monkeypatch.setattr(node, "_get_database_manager", AsyncMock(return_value=manager))

    with pytest.raises(AppException) as exc_info:
        await node.process(
            {
                "sourceType": "datasource",
                "dataSourceId": "ds-1",
                "query": "SELECT a FROM example",
            }
        )

    assert "returned more than 10 rows" in exc_info.value.error_detail
    assert "limit of 10" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_node_override_cannot_raise_the_platform_limit(monkeypatch):
    node = _node()
    manager = _database_manager([{"a": index} for index in range(11)])
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_ROWS", 10)
    monkeypatch.setattr(node, "_get_database_manager", AsyncMock(return_value=manager))

    with pytest.raises(AppException) as exc_info:
        await node.process(
            {
                "sourceType": "datasource",
                "dataSourceId": "ds-1",
                "query": "SELECT a FROM example",
                "maxRows": 1_000,
            }
        )

    assert "returned more than 10 rows" in exc_info.value.error_detail
    assert "limit of 10" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_node_override_can_lower_the_platform_limit(monkeypatch):
    node = _node()
    manager = _database_manager([{"a": index} for index in range(6)])
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_ROWS", 10)
    monkeypatch.setattr(node, "_get_database_manager", AsyncMock(return_value=manager))

    with pytest.raises(AppException) as exc_info:
        await node.process(
            {
                "sourceType": "datasource",
                "dataSourceId": "ds-1",
                "query": "SELECT a FROM example",
                "maxRows": 5,
            }
        )

    assert "returned more than 5 rows" in exc_info.value.error_detail
    assert "limit of 5" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_csv_larger_than_the_byte_cap_is_refused(monkeypatch, tmp_path):
    node = _node()
    csv_path = tmp_path / "large.csv"
    csv_path.write_bytes(b"a\n123456789")
    iter_csv_chunks = Mock()
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_BYTES", 10)
    monkeypatch.setattr(module.ml_utils, "iter_csv_chunks", iter_csv_chunks)

    with pytest.raises(AppException) as exc_info:
        await node.process(
            {
                "sourceType": "csv",
                "csvFilePath": str(csv_path),
                "maxBytes": 1_000,
            }
        )

    assert "11 bytes" in exc_info.value.error_detail
    assert "limit of 10 bytes" in exc_info.value.error_detail
    iter_csv_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_csv_row_cap_is_enforced_while_streaming(monkeypatch, tmp_path):
    node = _node()
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text(
        "a\n" + "".join(f"{index}\n" for index in range(11)),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_ROWS", 10)
    monkeypatch.setattr(module.ml_utils, "DATA_VOLUME", tmp_path)

    with pytest.raises(AppException) as exc_info:
        await node.process({"sourceType": "csv", "csvFilePath": str(csv_path)})

    assert "returned more than 10 rows" in exc_info.value.error_detail
    assert "limit of 10" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_csv_header_only_preserves_columns(monkeypatch, tmp_path):
    node = _node()
    csv_path = tmp_path / "header-only.csv"
    csv_path.write_text("id,name\n", encoding="utf-8")
    monkeypatch.setattr(module.ml_utils, "DATA_VOLUME", tmp_path)

    result = await node.process(
        {"sourceType": "csv", "csvFilePath": str(csv_path)}
    )

    assert result["data"] == []
    assert result["metadata"] == {"rowCount": 0, "columns": ["id", "name"]}
    assert Path(result["data_path"]).read_text(encoding="utf-8") == "id,name\n"


@pytest.mark.asyncio
async def test_configured_chunk_rows_reaches_csv_reader(monkeypatch, tmp_path):
    node = _node()
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("id\n1\n", encoding="utf-8")
    observed_chunk_sizes = []
    original_iter_csv_chunks = module.ml_utils.iter_csv_chunks

    def iter_csv_chunks(file_path, chunk_size):
        observed_chunk_sizes.append(chunk_size)
        return original_iter_csv_chunks(file_path, chunk_size)

    monkeypatch.setattr(settings, "ML_EXTRACT_CHUNK_ROWS", 37)
    monkeypatch.setattr(module.ml_utils, "DATA_VOLUME", tmp_path)
    monkeypatch.setattr(module.ml_utils, "iter_csv_chunks", iter_csv_chunks)

    await node.process({"sourceType": "csv", "csvFilePath": str(csv_path)})

    assert observed_chunk_sizes == [37]


@pytest.mark.asyncio
async def test_csv_preview_preserves_values_as_written(monkeypatch, tmp_path):
    node = _node()
    csv_path = tmp_path / "typed.csv"
    csv_path.write_text(
        "id,city,occupied,ratio,missing\n"
        + "".join(
            f"{index},city-{index},{index % 2 == 0},{index + 0.25},\n"
            for index in range(10)
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module.ml_utils, "DATA_VOLUME", tmp_path)

    result = await node.process(
        {"sourceType": "csv", "csvFilePath": str(csv_path)}
    )

    assert [row["id"] for row in result["data"]] == ["0", "1", "2", "7", "8", "9"]
    for row in result["data"]:
        assert type(row["id"]) is str
        assert type(row["city"]) is str
        assert type(row["occupied"]) is str
        assert type(row["ratio"]) is str
        assert row["missing"] is None


@pytest.mark.asyncio
async def test_csv_timeout_uses_extraction_timeout_message(monkeypatch, tmp_path):
    node = _node()
    csv_path = tmp_path / "slow.csv"
    csv_path.write_text("id\n1\n", encoding="utf-8")

    async def wait_forever(*_args, **_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(module.ml_utils, "stream_rows_to_csv", wait_forever)

    with pytest.raises(AppException) as exc_info:
        await node.process(
            {
                "sourceType": "csv",
                "csvFilePath": str(csv_path),
                "timeoutSeconds": 0.01,
            }
        )

    assert exc_info.value.error_detail == (
        "Training data extraction timed out after 0.01 seconds"
    )
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_non_csv_parsing_is_included_in_extraction_timeout(monkeypatch, tmp_path):
    node = _node()
    source = tmp_path / "slow.json"
    source.write_text("[]", encoding="utf-8")

    def slow_parse(_file_path):
        time.sleep(0.05)
        return []

    monkeypatch.setattr(module.ml_utils, "parse_training_file", slow_parse)
    monkeypatch.setattr(module.ml_utils, "DATA_VOLUME", tmp_path)

    with pytest.raises(AppException) as exc_info:
        await node.process(
            {
                "sourceType": "csv",
                "csvFilePath": str(source),
                "timeoutSeconds": 0.01,
            }
        )

    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED
    assert exc_info.value.error_detail == (
        "Training data extraction timed out after 0.01 seconds"
    )


@pytest.mark.asyncio
async def test_timeout_message_uses_effective_node_override(monkeypatch):
    node = _node()

    async def wait_forever(*_args, **_kwargs):
        await asyncio.Event().wait()
        yield

    manager = Mock()
    manager.get_db_type.return_value = "postgresql"
    manager.stream_query = Mock(side_effect=wait_forever)
    monkeypatch.setattr(settings, "ML_EXTRACT_TIMEOUT_SECONDS", 600)
    monkeypatch.setattr(node, "_get_database_manager", AsyncMock(return_value=manager))

    with pytest.raises(AppException) as exc_info:
        await node.process(
            {
                "sourceType": "datasource",
                "dataSourceId": "ds-1",
                "query": "SELECT pg_sleep(35)",
                "timeoutSeconds": 0.01,
            }
        )

    assert exc_info.value.error_detail == "Training data extraction timed out after 0.01 seconds"
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_effective_limits_are_logged(monkeypatch, tmp_path, caplog):
    node = _node()
    csv_path = tmp_path / "small.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_ROWS", 10)
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_BYTES", 20)
    monkeypatch.setattr(settings, "ML_EXTRACT_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(module.ml_utils, "DATA_VOLUME", tmp_path)

    with caplog.at_level(logging.INFO, logger=module.__name__):
        await node.process(
            {
                "sourceType": "csv",
                "csvFilePath": str(csv_path),
                "maxRows": 5,
                "maxBytes": 15,
                "timeoutSeconds": 4,
            }
        )

    assert "max_rows=5, max_bytes=15, timeout=4s" in caplog.text


@pytest.mark.parametrize(
    ("config_key", "config_value"),
    [
        ("maxRows", 0),
        ("maxBytes", -1),
        ("timeoutSeconds", "not-a-number"),
    ],
)
def test_invalid_node_limit_is_rejected(config_key, config_value):
    with pytest.raises(AppException) as exc_info:
        TrainDataSourceNode._resolve_extraction_limits({config_key: config_value})

    assert exc_info.value.error_detail == f"{config_key} must be a positive number"


def test_node_timeout_override_cannot_raise_platform_limit(monkeypatch):
    monkeypatch.setattr(settings, "ML_EXTRACT_TIMEOUT_SECONDS", 30)

    limits = TrainDataSourceNode._resolve_extraction_limits({"timeoutSeconds": 120})

    assert limits.extraction_timeout_seconds == 30


@pytest.mark.parametrize("chunk_rows", [0, -1])
def test_extract_chunk_rows_must_be_positive(chunk_rows):
    with pytest.raises(ValidationError):
        ProjectSettings(_env_file=None, ML_EXTRACT_CHUNK_ROWS=chunk_rows)


def test_legacy_extract_timeout_environment_name_is_supported(monkeypatch):
    monkeypatch.delenv("ML_EXTRACT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("ML_EXTRACT_QUERY_TIMEOUT_SECONDS", "45")

    configured = ProjectSettings(_env_file=None)

    assert configured.ML_EXTRACT_TIMEOUT_SECONDS == 45


def test_new_extract_timeout_environment_name_takes_precedence(monkeypatch):
    monkeypatch.setenv("ML_EXTRACT_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("ML_EXTRACT_QUERY_TIMEOUT_SECONDS", "45")

    configured = ProjectSettings(_env_file=None)

    assert configured.ML_EXTRACT_TIMEOUT_SECONDS == 30
