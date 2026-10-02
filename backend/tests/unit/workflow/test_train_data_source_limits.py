"""Resource-limit tests for the Train Data Source workflow node."""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config.settings import settings
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import train_data_source_node as module
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode


def _node() -> TrainDataSourceNode:
    state = SimpleNamespace(thread_id="thread-1")
    return TrainDataSourceNode("source-1", {"data": {}}, state)


def _database_manager(rows):
    return SimpleNamespace(
        db_type="postgresql",
        execute_query=AsyncMock(return_value=(rows, None)),
    )


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

    assert "returned 11 rows" in exc_info.value.error_detail
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

    assert "returned 11 rows" in exc_info.value.error_detail
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

    assert "returned 6 rows" in exc_info.value.error_detail
    assert "limit of 5" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_csv_larger_than_the_byte_cap_is_refused(monkeypatch, tmp_path):
    node = _node()
    csv_path = tmp_path / "large.csv"
    csv_path.write_bytes(b"a\n123456789")
    parse_csv = Mock()
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_BYTES", 10)
    monkeypatch.setattr(module.ml_utils, "parse_csv_file", parse_csv)

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
    parse_csv.assert_not_called()


@pytest.mark.asyncio
async def test_csv_row_cap_is_enforced_after_parsing(monkeypatch, tmp_path):
    node = _node()
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_ROWS", 10)
    monkeypatch.setattr(
        module.ml_utils,
        "parse_csv_file",
        Mock(return_value=[{"a": index} for index in range(11)]),
    )

    with pytest.raises(AppException) as exc_info:
        await node.process({"sourceType": "csv", "csvFilePath": str(csv_path)})

    assert "returned 11 rows" in exc_info.value.error_detail
    assert "limit of 10" in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_timeout_message_uses_effective_node_override(monkeypatch):
    node = _node()

    async def wait_forever(_query):
        await asyncio.Event().wait()

    manager = SimpleNamespace(db_type="postgresql", execute_query=wait_forever)
    monkeypatch.setattr(settings, "ML_EXTRACT_QUERY_TIMEOUT_SECONDS", 600)
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

    assert exc_info.value.error_detail == "Database query timed out after 0.01 seconds"


@pytest.mark.asyncio
async def test_effective_limits_are_logged(monkeypatch, tmp_path, caplog):
    node = _node()
    csv_path = tmp_path / "small.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_ROWS", 10)
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_BYTES", 20)
    monkeypatch.setattr(settings, "ML_EXTRACT_QUERY_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(module.ml_utils, "parse_csv_file", Mock(return_value=[{"a": "1"}]))
    monkeypatch.setattr(
        module.ml_utils,
        "save_data_to_csv",
        AsyncMock(return_value="/tmp/thread-1.csv"),
    )

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
    monkeypatch.setattr(settings, "ML_EXTRACT_QUERY_TIMEOUT_SECONDS", 30)

    limits = TrainDataSourceNode._resolve_extraction_limits({"timeoutSeconds": 120})

    assert limits.query_timeout_seconds == 30
