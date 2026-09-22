"""Tests for safe Snowflake bound-parameter failures."""

import logging
from unittest.mock import MagicMock

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
