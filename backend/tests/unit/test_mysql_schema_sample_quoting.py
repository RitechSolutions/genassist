"""Unit tests for MySQL identifier quoting in DatabaseManager._get_schema.

Table and column names come from SHOW TABLES / DESCRIBE, but a name containing
a backtick must not break out of the identifier quoting in the sample-rows or
categorical-value queries.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects.mysql.aiomysql import dialect as aiomysql_dialect

from app.modules.integration.database.database_manager import DatabaseManager

WEIRD_TABLE = "odd`name"
WEIRD_COLUMN = "st`atus"


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


class _Result:
    def __init__(self, rows: List[Tuple], columns: Optional[List[str]] = None):
        self._rows = rows
        self._columns = columns or []

    def keys(self):
        return self._columns

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _AsyncCM:
    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _MySQLConn:
    """Answers the queries _get_schema issues for a single table."""

    def __init__(self):
        self.executed: List[Tuple[str, Any]] = []

    async def execute(self, stmt, parameters=None):
        sql = _normalize(getattr(stmt, "text", str(stmt)))
        self.executed.append((sql, parameters))
        if sql == "SHOW TABLES":
            return _Result([(WEIRD_TABLE,)])
        if sql.startswith("DESCRIBE"):
            return _Result([("id", "int", "NO", "PRI", None, ""), (WEIRD_COLUMN, "varchar(20)", "YES", "", None, "")])
        if sql.startswith("SELECT * FROM"):
            return _Result([(1, "open")], ["id", WEIRD_COLUMN])
        if sql.startswith("SELECT DISTINCT"):
            return _Result([("closed",), ("open",)])
        if sql.startswith("SELECT COUNT(DISTINCT"):
            return _Result([(2,)])
        return _Result([])


def _mysql_manager(conn: _MySQLConn) -> DatabaseManager:
    manager = DatabaseManager({"database_type": "mysql"})
    engine = MagicMock()
    engine.dialect = aiomysql_dialect()
    engine.begin = MagicMock(return_value=_AsyncCM(conn))
    manager.engine = engine
    manager.db_type = "mysql"
    return manager


def _calls_starting_with(conn: _MySQLConn, prefix: str) -> List[Tuple[str, Any]]:
    return [(sql, params) for sql, params in conn.executed if sql.startswith(prefix)]


@pytest.mark.asyncio
async def test_mysql_sample_query_quotes_table_with_backtick():
    conn = _MySQLConn()
    manager = _mysql_manager(conn)

    schema = await manager._get_schema(include_samples=True, sample_size=1, include_categorical_values=False)

    assert _calls_starting_with(conn, "SELECT * FROM") == [("SELECT * FROM `odd``name` LIMIT :limit", {"limit": 1})]

    (table,) = schema["tables"]
    assert table["name"] == WEIRD_TABLE
    assert table["samples"] == [{"id": 1, WEIRD_COLUMN: "open"}]


@pytest.mark.asyncio
async def test_mysql_categorical_queries_quote_table_and_column_with_backtick():
    conn = _MySQLConn()
    manager = _mysql_manager(conn)

    schema = await manager._get_schema(
        include_samples=False, include_categorical_values=True, max_categorical_values=5
    )

    assert _calls_starting_with(conn, "SELECT DISTINCT") == [
        (
            "SELECT DISTINCT `st``atus` FROM `odd``name` WHERE `st``atus` IS NOT NULL ORDER BY `st``atus` LIMIT :limit",
            {"limit": 5},
        )
    ]
    assert _calls_starting_with(conn, "SELECT COUNT(DISTINCT") == [
        ("SELECT COUNT(DISTINCT `st``atus`) FROM `odd``name` WHERE `st``atus` IS NOT NULL", None)
    ]

    (table,) = schema["tables"]
    status_col = next(c for c in table["columns"] if c["name"] == WEIRD_COLUMN)
    assert status_col["possible_values"] == ["closed", "open"]
    assert status_col["total_distinct_count"] == 2
