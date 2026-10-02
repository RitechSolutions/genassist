"""Unit tests for database result streaming."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from app.modules.integration.database.database_manager import DatabaseManager


def _sql(statement):
    return getattr(statement, "text", str(statement))


class _AsyncContextManager:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _StreamResult:
    def __init__(self, columns, partitions):
        self.columns = columns
        self._partitions = partitions
        self.partition_sizes = []
        self.closed = False

    def keys(self):
        return self.columns

    async def partitions(self, size):
        self.partition_sizes.append(size)
        for partition in self._partitions:
            yield partition

    async def close(self):
        self.closed = True


class _StreamingConnection:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def execute(self, statement, parameters=None):
        self.calls.append(("execute", _sql(statement), parameters))

    async def stream(self, statement, parameters):
        self.calls.append(("stream", _sql(statement), parameters))
        return self.result

    async def execution_options(self, **options):
        self.calls.append(("execution_options", options))
        return self


def _manager(db_type, connection):
    manager = DatabaseManager({"database_type": db_type})
    engine = MagicMock()
    engine.connect.return_value = _AsyncContextManager(connection)
    engine.begin.return_value = _AsyncContextManager(connection)
    manager.engine = engine
    return manager


@pytest.mark.asyncio
async def test_stream_query_yields_columns_before_partitioned_tuple_rows():
    result = _StreamResult(["b", "a"], [[(2, 1), (4, 3)], [(6, 5)]])
    connection = _StreamingConnection(result)
    manager = _manager("mssql", connection)

    chunks = [
        chunk
        async for chunk in manager.stream_query(
            "SELECT b, a FROM example WHERE a = :value",
            {"value": 1},
            chunk_size=2,
        )
    ]

    assert chunks == [
        (["b", "a"], []),
        (["b", "a"], [(2, 1), (4, 3)]),
        (["b", "a"], [(6, 5)]),
    ]
    assert connection.calls == [
        (
            "stream",
            "SELECT b, a FROM example WHERE a = :value",
            {"value": 1},
        )
    ]
    assert result.partition_sizes == [2]
    assert result.closed is True


@pytest.mark.asyncio
async def test_stream_query_preserves_columns_for_empty_result():
    result = _StreamResult(["id", "name"], [])
    manager = _manager("mssql", _StreamingConnection(result))

    chunks = [
        chunk
        async for chunk in manager.stream_query(
            "SELECT id, name FROM example",
            chunk_size=2_000,
        )
    ]

    assert chunks == [(["id", "name"], [])]
    assert result.partition_sizes == [2_000]
    assert result.closed is True


@pytest.mark.asyncio
async def test_postgres_stream_sets_transaction_read_only_before_query():
    result = _StreamResult(["n"], [[(1,)]])
    connection = _StreamingConnection(result)
    manager = _manager("postgresql", connection)
    manager._coerce_postgres_parameters = AsyncMock(return_value=None)

    chunks = [
        chunk
        async for chunk in manager.stream_query("SELECT 1", chunk_size=2_000)
    ]

    assert chunks[-1] == (["n"], [(1,)])
    assert connection.calls[0] == ("execute", "SET TRANSACTION READ ONLY", None)
    assert connection.calls[1] == ("stream", "SELECT 1", {})


@pytest.mark.asyncio
async def test_mysql_stream_rolls_back_when_consumer_stops_early():
    result = _StreamResult(["n"], [[(1,)], [(2,)]])
    connection = _StreamingConnection(result)
    manager = _manager("mysql", connection)
    stream = manager.stream_query("SELECT n FROM example", chunk_size=1)

    assert await anext(stream) == (["n"], [])
    assert await anext(stream) == (["n"], [(1,)])
    await stream.aclose()

    executed = [call[1] for call in connection.calls if call[0] == "execute"]
    assert executed == ["START TRANSACTION READ ONLY", "ROLLBACK"]
    assert result.closed is True


@pytest.mark.asyncio
async def test_sqlite_stream_query_uses_real_partitioned_result():
    manager = DatabaseManager({"database_type": "sqlite", "database_path": ":memory:"})
    await manager.connect()
    try:
        async with manager.engine.begin() as connection:
            await connection.execute(text("CREATE TABLE example (id INTEGER, name TEXT)"))
            await connection.execute(text("INSERT INTO example (id, name) VALUES (1, 'a'), (2, 'b'), (3, 'c')"))

        chunks = [
            chunk
            async for chunk in manager.stream_query(
                "SELECT id, name FROM example ORDER BY id",
                chunk_size=2,
            )
        ]

        assert chunks == [
            (["id", "name"], []),
            (["id", "name"], [(1, "a"), (2, "b")]),
            (["id", "name"], [(3, "c")]),
        ]
    finally:
        await manager.disconnect()
