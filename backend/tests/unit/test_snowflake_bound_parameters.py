"""Tests for safe Snowflake bound-parameter failures."""

import logging
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from app.modules.integration.snowflake.snowflake_manager import SnowflakeManager


@pytest.mark.asyncio
async def test_snowflake_error_does_not_expose_bound_value(caplog):
    secret = "private-query-value"
    manager = SnowflakeManager({})
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError(f"invalid value {secret!r}")
    manager.connection = MagicMock()
    manager.connection.cursor.return_value = cursor

    with caplog.at_level(logging.ERROR):
        rows, error = await manager.execute_query(
            "SELECT %(value)s",
            {"value": secret},
        )

    assert rows == []
    assert secret not in error
    assert secret not in caplog.text
    assert "[BOUND_VALUE]" in error


@pytest.mark.asyncio
async def test_snowflake_stream_uses_fetchmany_and_keeps_empty_columns():
    manager = SnowflakeManager({})
    cursor = MagicMock()
    cursor.description = [("id",), ("name",)]
    cursor.fetchmany.side_effect = [[(1, "a"), (2, "b")], [(3, "c")], []]
    manager.connection = MagicMock()
    manager.connection.cursor.return_value = cursor

    chunks = [
        chunk
        async for chunk in manager.stream_query(
            "SELECT id, name FROM example WHERE id >= %(minimum)s",
            {"minimum": 1},
            chunk_size=2,
        )
    ]

    assert chunks == [
        (["id", "name"], []),
        (["id", "name"], [(1, "a"), (2, "b")]),
        (["id", "name"], [(3, "c")]),
    ]
    cursor.execute.assert_called_once_with(
        "SELECT id, name FROM example WHERE id >= %(minimum)s",
        {"minimum": 1},
    )
    assert cursor.fetchmany.call_args_list == [call(2), call(2), call(2)]
    cursor.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_snowflake_stream_uses_requested_two_thousand_rows():
    manager = SnowflakeManager({})
    cursor = MagicMock()
    cursor.description = [("id",)]
    cursor.fetchmany.return_value = []
    manager.connection = MagicMock()
    manager.connection.cursor.return_value = cursor

    chunks = [
        chunk
        async for chunk in manager.stream_query(
            "SELECT id FROM example",
            chunk_size=2_000,
        )
    ]

    assert chunks == [(["id"], [])]
    cursor.fetchmany.assert_called_once_with(2_000)


@pytest.mark.asyncio
async def test_snowflake_stream_reconnects_once_when_token_expires():
    manager = SnowflakeManager({})
    expired_cursor = MagicMock()
    expired_cursor.execute.side_effect = Exception(
        "390114: Authentication token has expired"
    )
    initial_connection = MagicMock()
    initial_connection.cursor.return_value = expired_cursor

    retry_cursor = MagicMock()
    retry_cursor.description = [("id",)]
    retry_cursor.fetchmany.side_effect = [[(1,)], []]
    retry_connection = MagicMock()
    retry_connection.cursor.return_value = retry_cursor

    manager.connection = initial_connection
    manager.disconnect = AsyncMock()

    async def reconnect():
        manager.connection = retry_connection

    manager.connect = AsyncMock(side_effect=reconnect)

    chunks = [
        chunk
        async for chunk in manager.stream_query(
            "SELECT id FROM example",
            chunk_size=2_000,
        )
    ]

    assert chunks == [(["id"], []), (["id"], [(1,)])]
    manager.disconnect.assert_awaited_once_with()
    manager.connect.assert_awaited_once_with()
    expired_cursor.close.assert_called_once_with()
    retry_cursor.execute.assert_called_once_with("SELECT id FROM example")
    retry_cursor.close.assert_called_once_with()
