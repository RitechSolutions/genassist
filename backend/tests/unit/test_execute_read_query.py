"""Unit tests for DatabaseManager.execute_read_query safety controls.

AST validation is intentionally not used here. These tests prove the
execution layer independently applies (or does not invent) database-level
read-only protection.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from app.modules.integration.database.database_manager import DatabaseManager


def _sql(stmt) -> str:
    return getattr(stmt, "text", str(stmt))


class _SelectResult:
    def __init__(self, rows: Optional[List[Tuple]] = None, columns: Optional[List[str]] = None):
        self._rows = rows if rows is not None else [(1,)]
        self._columns = columns if columns is not None else ["n"]

    def keys(self):
        return self._columns

    def fetchall(self):
        return self._rows


class _AsyncCM:
    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RecordingConn:
    def __init__(self, execute_impl=None):
        self.calls: List[Tuple[Any, ...]] = []
        self._execute_impl = execute_impl

    async def execution_options(self, **opt):
        self.calls.append(("execution_options", opt))
        return self

    async def execute(self, stmt, parameters=None):
        sql = _sql(stmt)
        self.calls.append(("execute", sql, parameters))
        if self._execute_impl is not None:
            return await self._execute_impl(sql, parameters)
        return _SelectResult()

    @property
    def executed_sql(self) -> List[str]:
        return [c[1] for c in self.calls if c[0] == "execute"]


def _manager_with_engine(db_type: str, conn: RecordingConn) -> DatabaseManager:
    manager = DatabaseManager({"database_type": db_type})
    engine = MagicMock()
    engine.begin = MagicMock(return_value=_AsyncCM(conn))
    engine.connect = MagicMock(return_value=_AsyncCM(conn))
    manager.engine = engine
    manager.db_type = db_type
    return manager


@pytest.mark.asyncio
async def test_postgres_sets_transaction_read_only_before_user_sql():
    conn = RecordingConn()
    manager = _manager_with_engine("postgresql", conn)

    results, error = await manager.execute_read_query("SELECT 1")

    assert error is None
    assert results == [{"n": 1}]
    assert conn.executed_sql == ["SET TRANSACTION READ ONLY", "SELECT 1"]


@pytest.mark.asyncio
async def test_postgres_skips_user_sql_if_read_only_setup_fails():
    async def execute_impl(sql, _parameters):
        if sql == "SET TRANSACTION READ ONLY":
            raise RuntimeError("cannot set read only")
        return _SelectResult()

    conn = RecordingConn(execute_impl)
    manager = _manager_with_engine("postgresql", conn)

    results, error = await manager.execute_read_query("SELECT 1")

    assert results == []
    assert error is not None
    assert "cannot set read only" in error
    assert conn.executed_sql == ["SET TRANSACTION READ ONLY"]


@pytest.mark.asyncio
async def test_postgres_database_error_returns_results_error_tuple():
    async def execute_impl(sql, _parameters):
        if sql == "SELECT boom":
            raise RuntimeError("db failed")
        return _SelectResult()

    conn = RecordingConn(execute_impl)
    manager = _manager_with_engine("postgresql", conn)

    results, error = await manager.execute_read_query("SELECT boom")

    assert results == []
    assert error == "db failed"
    assert conn.executed_sql[0] == "SET TRANSACTION READ ONLY"


@pytest.mark.asyncio
async def test_execute_query_does_not_emit_postgres_read_only_preamble():
    conn = RecordingConn()
    manager = _manager_with_engine("postgresql", conn)

    results, error = await manager.execute_query("SELECT 1")

    assert error is None
    assert results == [{"n": 1}]
    assert conn.executed_sql == ["SELECT 1"]
    assert not any("READ ONLY" in sql for sql in conn.executed_sql)


@pytest.mark.asyncio
@pytest.mark.parametrize("db_type", ["mysql", "sql"])
async def test_mysql_start_transaction_read_only_then_commit(db_type):
    conn = RecordingConn()
    manager = _manager_with_engine(db_type, conn)

    results, error = await manager.execute_read_query("SELECT 1")

    assert error is None
    assert results == [{"n": 1}]
    assert conn.calls[0] == ("execution_options", {"isolation_level": "AUTOCOMMIT"})
    assert conn.executed_sql == [
        "START TRANSACTION READ ONLY",
        "SELECT 1",
        "COMMIT",
    ]


@pytest.mark.asyncio
async def test_mysql_rollback_after_failing_user_query():
    async def execute_impl(sql, _parameters):
        if sql == "DELETE FROM t":
            raise RuntimeError("cannot delete")
        return _SelectResult()

    conn = RecordingConn(execute_impl)
    manager = _manager_with_engine("mysql", conn)

    results, error = await manager.execute_read_query("DELETE FROM t")

    assert results == []
    assert "cannot delete" in error
    assert conn.executed_sql == [
        "START TRANSACTION READ ONLY",
        "DELETE FROM t",
        "ROLLBACK",
    ]


@pytest.mark.asyncio
async def test_mysql_does_not_run_user_sql_if_start_transaction_fails():
    async def execute_impl(sql, _parameters):
        if sql == "START TRANSACTION READ ONLY":
            raise RuntimeError("cannot start read-only transaction")
        return _SelectResult()

    conn = RecordingConn(execute_impl)
    manager = _manager_with_engine("mysql", conn)

    results, error = await manager.execute_read_query("SELECT 1")

    assert results == []
    assert "cannot start read-only transaction" in error
    assert conn.executed_sql == ["START TRANSACTION READ ONLY"]
    assert "SELECT 1" not in conn.executed_sql
    assert "ROLLBACK" not in conn.executed_sql


@pytest.mark.asyncio
async def test_mssql_does_not_invent_read_only_sql():
    conn = RecordingConn()
    manager = _manager_with_engine("mssql", conn)

    results, error = await manager.execute_read_query("SELECT 1")

    assert error is None
    assert results == [{"n": 1}]
    assert conn.executed_sql == ["SELECT 1"]
    joined = " ".join(conn.executed_sql).upper()
    assert "READ ONLY" not in joined
    assert "START TRANSACTION" not in joined
    assert not any(c[0] == "execution_options" for c in conn.calls)


@pytest.mark.asyncio
async def test_snowflake_delegates_to_existing_execute_query():
    manager = DatabaseManager({"source_type": "snowflake"})
    manager.db_type = "snowflake"
    snowflake = MagicMock()
    snowflake.execute_query = AsyncMock(return_value=([{"n": 1}], None))
    manager.snowflake_manager = snowflake
    manager.connect = AsyncMock()

    results, error = await manager.execute_read_query("SELECT 1")

    assert error is None
    assert results == [{"n": 1}]
    snowflake.execute_query.assert_awaited_once_with("SELECT 1", None)
    manager.connect.assert_not_awaited()
    issued = str(snowflake.execute_query.await_args)
    assert "USE ROLE" not in issued
    assert "ALTER SESSION" not in issued


@pytest.mark.asyncio
async def test_unsupported_db_type_does_not_guess_a_dialect():
    manager = DatabaseManager({"database_type": "oracle"})
    manager.engine = MagicMock()
    manager.engine.begin = MagicMock(side_effect=AssertionError("must not execute"))
    manager.connect = AsyncMock(side_effect=AssertionError("must not connect"))

    results, error = await manager.execute_read_query("SELECT 1")

    assert results == []
    assert error is not None
    assert "Unsupported database type" in error


async def _create_sqlite_table(manager: DatabaseManager) -> None:
    async with manager.engine.begin() as conn:
        await conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, n INTEGER)"))


@pytest.mark.asyncio
async def test_sqlite_file_mode_ro_blocks_write_but_generic_executor_still_writes(tmp_path):
    db_path = str(tmp_path / "g3.sqlite")
    manager = DatabaseManager({"database_type": "sqlite", "database_path": db_path})
    await manager.connect()
    try:
        await _create_sqlite_table(manager)
        inserted, insert_err = await manager.execute_query("INSERT INTO t (n) VALUES (1) RETURNING n")
        assert insert_err is None
        assert inserted == [{"n": 1}]

        rows, error = await manager.execute_read_query("SELECT n FROM t")
        assert error is None
        assert rows == [{"n": 1}]

        deleted, delete_error = await manager.execute_read_query("DELETE FROM t")
        assert deleted == []
        assert delete_error is not None
        assert "readonly" in delete_error.lower() or "read-only" in delete_error.lower()

        created, create_ro_error = await manager.execute_read_query("CREATE TABLE u (id INTEGER PRIMARY KEY)")
        assert created == []
        assert create_ro_error is not None

        remaining, error = await manager.execute_query("SELECT n FROM t")
        assert error is None
        assert remaining == [{"n": 1}]

        generic_insert, error = await manager.execute_query("INSERT INTO t (n) VALUES (2) RETURNING n")
        assert error is None
        assert generic_insert == [{"n": 2}]

        after, error = await manager.execute_query("SELECT n FROM t ORDER BY n")
        assert error is None
        assert after == [{"n": 1}, {"n": 2}]
    finally:
        await manager.disconnect()


@pytest.mark.asyncio
async def test_sqlite_memory_query_only_blocks_write_then_generic_still_writes():
    manager = DatabaseManager({"database_type": "sqlite", "database_path": ":memory:"})
    await manager.connect()
    try:
        await _create_sqlite_table(manager)
        inserted, insert_err = await manager.execute_query("INSERT INTO t (n) VALUES (1) RETURNING n")
        assert insert_err is None
        assert inserted == [{"n": 1}]

        rows, error = await manager.execute_read_query("SELECT n FROM t")
        assert error is None
        assert rows == [{"n": 1}]

        deleted, delete_error = await manager.execute_read_query("DELETE FROM t")
        assert deleted == []
        assert delete_error is not None
        assert "readonly" in delete_error.lower() or "read-only" in delete_error.lower()

        remaining, error = await manager.execute_query("SELECT n FROM t")
        assert error is None
        assert remaining == [{"n": 1}]

        generic_insert, error = await manager.execute_query("INSERT INTO t (n) VALUES (2) RETURNING n")
        assert error is None
        assert generic_insert == [{"n": 2}]
        after, error = await manager.execute_query("SELECT n FROM t ORDER BY n")
        assert error is None
        assert after == [{"n": 1}, {"n": 2}]
    finally:
        await manager.disconnect()
