"""SQLNode integration tests for TDS-2 read-only enforcement.

These tests prove both modes share one pre-execute validator and that rejected
SQL never reaches ``execute_read_query``. Validator policy is covered separately.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.modules.integration.database.read_only_sql import read_only_sql_blocked_message, validate_read_only_sql
from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes import sql_node as sql_module
from app.modules.workflow.engine.nodes.sql_node import SQLNode


def _node():
    return SQLNode("s1", {"type": "sqlNode", "data": {}}, SimpleNamespace())


def _sql_config(sql: str) -> dict:
    return {
        "mode": "sqlQuery",
        "dataSourceId": "ds-1",
        "sqlQuery": sql,
    }


def _human_config() -> dict:
    return {
        "mode": "humanQuery",
        "dataSourceId": "ds-1",
        "humanQuery": "how many users?",
        "providerId": "p1",
        "systemPrompt": "",
    }


def _db_manager(db_type: str = "postgresql"):
    manager = MagicMock()
    manager.get_db_type.return_value = db_type
    manager.execute_read_query = AsyncMock(return_value=([{"n": 1}], None))
    manager.execute_query = AsyncMock(return_value=([{"n": 1}], None))
    return manager


def _patch_db(manager):
    return patch.object(
        sql_module.db_provider_manager,
        "get_database_manager",
        AsyncMock(return_value=manager),
    )


def _patch_llm():
    model = MagicMock()
    provider = MagicMock()
    provider.get_model = AsyncMock(return_value=model)
    inj = MagicMock()
    inj.get = MagicMock(return_value=provider)
    return patch.object(sql_module, "injector", inj)


def _translate_returning(sql: str):
    async def _translate(_manager, **kwargs):
        return {"formatted_query": sql}

    return _translate


@pytest.mark.asyncio
async def test_sql_query_select_is_executed_unchanged():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        result = await _node().process(_sql_config("SELECT 1"))

    assert result["status"] == 200
    assert result["data"] == [{"n": 1}]
    db_manager.execute_read_query.assert_awaited_once_with("SELECT 1")
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_sql_query_delete_never_executes():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        result = await _node().process(_sql_config("DELETE FROM users WHERE id = 1"))

    failure = is_node_failure(result)
    assert failure is not None
    assert failure["code"] == 400
    assert failure["details"]["error_key"] == ErrorKey.READ_ONLY_SQL_BLOCKED.value
    assert failure["error"] == read_only_sql_blocked_message(
        validate_read_only_sql("DELETE FROM users WHERE id = 1", "postgresql")
    )
    assert "SQL execution blocked" in failure["error"]
    assert "Delete" in failure["error"]
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_sql_query_stacked_write_never_executes():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        result = await _node().process(_sql_config("SELECT 1;\nDROP TABLE users;"))

    failure = is_node_failure(result)
    assert failure is not None
    assert failure["code"] == 400
    assert failure["details"]["error_key"] == ErrorKey.READ_ONLY_SQL_BLOCKED.value
    assert "SQL execution blocked" in failure["error"]
    assert "Multiple SQL statements" in failure["error"]
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_sql_query_two_selects_never_executes():
    db_manager = _db_manager()
    with _patch_db(db_manager):
        result = await _node().process(_sql_config("SELECT 1;\nSELECT 2;"))

    failure = is_node_failure(result)
    assert failure is not None
    assert failure["code"] == 400
    assert failure["details"]["error_key"] == ErrorKey.READ_ONLY_SQL_BLOCKED.value
    assert "Multiple SQL statements" in failure["error"]
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_human_query_select_is_executed():
    db_manager = _db_manager()
    with (
        _patch_llm(),
        _patch_db(db_manager),
        patch.object(sql_module, "translate_to_query", _translate_returning("SELECT * FROM users")),
    ):
        result = await _node().process(_human_config())

    assert result["status"] == 200
    db_manager.execute_read_query.assert_awaited_once_with("SELECT * FROM users")
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_human_query_update_never_executes():
    db_manager = _db_manager()
    with (
        _patch_llm(),
        _patch_db(db_manager),
        patch.object(
            sql_module,
            "translate_to_query",
            _translate_returning("UPDATE users SET active = 0"),
        ),
    ):
        result = await _node().process(_human_config())

    failure = is_node_failure(result)
    assert failure is not None
    assert failure["code"] == 400
    assert failure["details"]["error_key"] == ErrorKey.READ_ONLY_SQL_BLOCKED.value
    assert "SQL execution blocked" in failure["error"]
    assert "Update" in failure["error"]
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_human_query_stacked_sql_never_executes():
    db_manager = _db_manager()
    with (
        _patch_llm(),
        _patch_db(db_manager),
        patch.object(
            sql_module,
            "translate_to_query",
            _translate_returning("SELECT * FROM users;\nDELETE FROM users;"),
        ),
    ):
        result = await _node().process(_human_config())

    failure = is_node_failure(result)
    assert failure is not None
    assert failure["code"] == 400
    assert failure["details"]["error_key"] == ErrorKey.READ_ONLY_SQL_BLOCKED.value
    assert "Multiple SQL statements" in failure["error"]
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_db_type_never_executes():
    db_manager = _db_manager(db_type="oracle")
    with _patch_db(db_manager):
        result = await _node().process(_sql_config("SELECT 1"))

    failure = is_node_failure(result)
    assert failure is not None
    assert failure["code"] == 400
    assert failure["details"]["error_key"] == ErrorKey.READ_ONLY_SQL_BLOCKED.value
    assert "SQL execution blocked" in failure["error"]
    assert "Unsupported database type" in failure["error"]
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_mysql_executable_comment_never_executes():
    db_manager = _db_manager(db_type="mysql")
    sql = "SELECT 1 /*!50000 INTO OUTFILE '/tmp/x' */"
    with _patch_db(db_manager):
        result = await _node().process(_sql_config(sql))

    failure = is_node_failure(result)
    assert failure is not None
    assert failure["code"] == 400
    assert failure["details"]["error_key"] == ErrorKey.READ_ONLY_SQL_BLOCKED.value
    assert failure["error"] == read_only_sql_blocked_message(
        validate_read_only_sql(sql, "mysql")
    )
    assert "executable comment" in failure["error"].lower()
    db_manager.execute_read_query.assert_not_awaited()
    db_manager.execute_query.assert_not_awaited()
