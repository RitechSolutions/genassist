"""TrainDataSourceNode integration tests for safe SQL execution."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import _response_error_detail
from app.modules.integration.database.bound_parameters import BoundValueError
from app.modules.integration.database.read_only_sql import (
    read_only_sql_blocked_message,
    validate_read_only_sql,
)
from app.modules.workflow.engine.nodes.ml.train_data_source_node import (
    TrainDataSourceNode,
)
from app.modules.workflow.engine.workflow_state import WorkflowState

MODULE = "app.modules.workflow.engine.nodes.ml.train_data_source_node"


def _state(initial_values=None) -> WorkflowState:
    return WorkflowState(
        workflow={"nodes": [], "source_edges": {}, "target_edges": {}},
        initial_values=initial_values or {},
        thread_id="thread-1",
    )


def _node(query: str | None = None, state=None) -> TrainDataSourceNode:
    data = {"name": "Training Data"}
    if query is not None:
        data.update(_config(query))
    node_config = {"id": "train-source-1", "type": "trainDataSourceNode", "data": data}
    state = state or _state()
    if not any(node.get("id") == "train-source-1" for node in state.workflow["nodes"]):
        state.workflow["nodes"].append(node_config)
    return TrainDataSourceNode(
        "train-source-1",
        node_config,
        state,
    )


def _config(query: str) -> dict:
    return {
        "name": "Training Data",
        "sourceType": "datasource",
        "dataSourceId": "ds-1",
        "query": query,
    }


def _db_manager(db_type: str = "postgresql"):
    manager = MagicMock()
    manager.get_db_type.return_value = db_type
    manager.execute_read_query = AsyncMock(return_value=([{"id": 1, "name": "a"}], None))
    manager.execute_query = AsyncMock(return_value=([{"id": 1, "name": "a"}], None))
    return manager


def _patch_db(manager):
    return patch.object(
        TrainDataSourceNode,
        "_get_database_manager",
        AsyncMock(return_value=manager),
    )


def _patch_csv_helpers():
    return (
        patch(f"{MODULE}.ml_utils.save_data_to_csv", AsyncMock(return_value="/tmp/train.csv")),
        patch(f"{MODULE}.ml_utils.get_sample_data", return_value=[{"id": 1}]),
    )


@pytest.mark.asyncio
async def test_select_is_executed_unchanged():
    db_manager = _db_manager()
    save_csv, sample = _patch_csv_helpers()
    sql = "SELECT * FROM demo_lots"
    with _patch_db(db_manager), save_csv, sample:
        result = await _node().process(_config(sql))

    assert result["success"] is True
    assert result["data_path"] == "/tmp/train.csv"
    assert result["metadata"]["rowCount"] == 1
    db_manager.execute_read_query.assert_awaited_once_with(sql)
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_never_executes():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await _node().process(_config("DELETE FROM demo_lots"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert exc_info.value.error_detail == read_only_sql_blocked_message(
        validate_read_only_sql("DELETE FROM demo_lots", "postgresql")
    )
    assert "SQL execution blocked" in exc_info.value.error_detail
    assert "Delete" in exc_info.value.error_detail
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_never_executes():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await _node().process(_config("UPDATE demo_lots SET status = 'deleted'"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert "SQL execution blocked" in exc_info.value.error_detail
    assert "Update" in exc_info.value.error_detail
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_stacked_query_never_executes():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await _node().process(_config("SELECT * FROM demo_lots;\nDELETE FROM demo_lots;"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert "SQL execution blocked" in exc_info.value.error_detail
    assert "Multiple SQL statements" in exc_info.value.error_detail
    assert "found 2" in exc_info.value.error_detail
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_two_selects_never_executes():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await _node().process(_config("SELECT 1;\nSELECT 2;"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert "Multiple SQL statements" in exc_info.value.error_detail
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_db_type_never_executes():
    db_manager = _db_manager(db_type="oracle")
    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await _node().process(_config("SELECT 1"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert "SQL execution blocked" in exc_info.value.error_detail
    assert "Unsupported database type" in exc_info.value.error_detail
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejected_query_uses_read_only_sql_blocked_key():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await _node().process(_config("DELETE FROM demo_lots"))

    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert exc_info.value.error_key != ErrorKey.INTERNAL_ERROR
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_mysql_executable_comment_never_executes():
    db_manager = _db_manager(db_type="mysql")
    sql = "SELECT 1 /*!50000 INTO OUTFILE '/tmp/x' */"
    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await _node().process(_config(sql))

    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert exc_info.value.error_detail == read_only_sql_blocked_message(
        validate_read_only_sql(sql, "mysql")
    )
    assert "executable comment" in exc_info.value.error_detail.lower()
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_failure_after_valid_sql_stays_internal(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    db_manager = _db_manager()
    db_manager.execute_read_query = AsyncMock(
        return_value=(None, "could not connect password=secret host=db.internal")
    )
    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await _node().process(_config("SELECT 1"))

    assert exc_info.value.error_key == ErrorKey.INTERNAL_ERROR
    assert "password=secret" in exc_info.value.error_detail
    assert _response_error_detail(exc_info.value) is None
    db_manager.execute_read_query.assert_awaited_once_with("SELECT 1")


@pytest.mark.asyncio
async def test_advisory_warnings_are_logged_without_blocking(caplog):
    db_manager = _db_manager()
    save_csv, sample = _patch_csv_helpers()
    sql = "SELECT * FROM demo_lots"

    with (
        _patch_db(db_manager),
        save_csv,
        sample,
        caplog.at_level(logging.WARNING, logger=MODULE),
    ):
        result = await _node().process(_config(sql))

    assert result["success"] is True
    assert "Training query advisory: SELECT * without LIMIT" in caplog.text
    db_manager.execute_read_query.assert_awaited_once_with(sql)


@pytest.mark.asyncio
async def test_advisory_validator_failure_does_not_block_execution(caplog):
    db_manager = _db_manager()
    save_csv, sample = _patch_csv_helpers()
    sql = "SELECT id FROM demo_lots"

    with (
        _patch_db(db_manager),
        save_csv,
        sample,
        patch(f"{MODULE}.AdvancedQueryValidator", side_effect=RuntimeError("boom")),
        caplog.at_level(logging.DEBUG, logger=MODULE),
    ):
        result = await _node().process(_config(sql))

    assert result["success"] is True
    assert "Advisory validation skipped: boom" in caplog.text
    db_manager.execute_read_query.assert_awaited_once_with(sql)


@pytest.mark.asyncio
async def test_execute_binds_injection_payload_without_logging_value(caplog):
    payload = "x' OR '1'='1"
    query = "SELECT * FROM demo_lots WHERE city = '{{chat.input}}'"
    db_manager = _db_manager()
    save_csv, sample = _patch_csv_helpers()
    node = _node(query, _state({"chat.input": payload}))

    with (
        _patch_db(db_manager),
        save_csv,
        sample,
        caplog.at_level(logging.DEBUG),
    ):
        result = await node.execute()

    assert result["success"] is True
    db_manager.execute_read_query.assert_awaited_once_with(
        "SELECT * FROM demo_lots WHERE city = :wf_0_chat_input",
        {"wf_0_chat_input": payload},
    )
    assert "Executing training query with 1 bound parameter(s)" in caplog.text
    assert payload not in caplog.text


@pytest.mark.asyncio
async def test_bound_database_failure_does_not_expose_value(caplog):
    payload = "private-query-value"
    query = "SELECT * FROM demo_lots WHERE city = {{chat.input}}"
    db_manager = _db_manager()
    db_manager.execute_read_query = AsyncMock(return_value=([], f"invalid input syntax near {payload!r}"))
    node = _node(query, _state({"chat.input": payload}))

    with _patch_db(db_manager), caplog.at_level(logging.ERROR):
        with pytest.raises(AppException) as exc_info:
            await node.process(_config(query))

    assert payload not in caplog.text
    assert payload not in exc_info.value.error_detail
    assert exc_info.value.error_detail.startswith("Database query failed.")


@pytest.mark.asyncio
async def test_postgres_conversion_error_names_variable_without_value():
    payload = "not-a-date-private"
    query = "SELECT * FROM demo_lots WHERE created_at >= {{start_date}}"
    db_manager = _db_manager()
    db_manager.execute_read_query = AsyncMock(side_effect=BoundValueError("start_date", "date"))
    node = _node(query, _state({"start_date": payload}))

    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await node.process(_config(query))

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert "start_date" in exc_info.value.error_detail
    assert "date" in exc_info.value.error_detail
    assert payload not in exc_info.value.error_detail


@pytest.mark.asyncio
async def test_execute_conversion_traceback_does_not_log_bound_value(caplog):
    payload = "not-an-integer-private"
    query = "SELECT * FROM demo_lots WHERE quantity >= {{minimum_quantity}}"
    db_manager = _db_manager()

    async def fail_conversion(*_args, **_kwargs):
        try:
            int(payload)
        except ValueError as exc:
            raise BoundValueError("minimum_quantity", "int4") from exc

    db_manager.execute_read_query = AsyncMock(side_effect=fail_conversion)
    node = _node(query, _state({"minimum_quantity": payload}))

    with _patch_db(db_manager), caplog.at_level(logging.ERROR):
        result = await node.execute()

    assert result["__node_failed__"] is True
    assert payload not in caplog.text


@pytest.mark.asyncio
async def test_execute_uses_snowflake_parameter_style():
    query = "SELECT * FROM demo_lots WHERE city = {{chat.input}}"
    db_manager = _db_manager(db_type="snowflake")
    save_csv, sample = _patch_csv_helpers()
    node = _node(query, _state({"chat.input": "Tirana"}))

    with _patch_db(db_manager), save_csv, sample:
        result = await node.execute()

    assert result["success"] is True
    db_manager.execute_read_query.assert_awaited_once_with(
        "SELECT * FROM demo_lots WHERE city = %(wf_0_chat_input)s",
        {"wf_0_chat_input": "Tirana"},
    )


@pytest.mark.asyncio
async def test_identifier_variable_is_rejected_before_execution():
    query = "SELECT * FROM {{table_name}}"
    db_manager = _db_manager()
    node = _node(state=_state({"table_name": "demo_lots"}))

    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await node.process(_config(query))

    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert "variables" in exc_info.value.error_detail
    assert "table or column names" in exc_info.value.error_detail
    db_manager.execute_read_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_embedded_literal_variable_is_rejected_before_execution():
    query = "SELECT * FROM demo_lots WHERE city LIKE '%{{search}}%'"
    db_manager = _db_manager()
    node = _node(state=_state({"search": "Tirana"}))

    with _patch_db(db_manager):
        with pytest.raises(AppException) as exc_info:
            await node.process(_config(query))

    assert exc_info.value.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED
    assert "concatenation" in exc_info.value.error_detail
    db_manager.execute_read_query.assert_not_awaited()
