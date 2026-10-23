"""Unit tests for MSSQL and PostgreSQL identifier quoting in DatabaseManager._get_schema."""

from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects.mssql.aioodbc import dialect as aioodbc_dialect
from sqlalchemy.dialects.postgresql.asyncpg import dialect as asyncpg_dialect
from sqlalchemy.sql.elements import TextClause

from app.modules.integration.database.database_manager import DatabaseManager, _sample_rows_query

ID_COLUMN = ("id", "int", "NO", None, None, 10, 0)
ALL_DATA_QUERIES = frozenset({"sample", "distinct", "count"})


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


class _AsyncContextManager:
    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, exc_type, exc, tb):
        return False


ABORTED_MESSAGE = "current transaction is aborted, commands ignored until end of transaction block"


class _Savepoint:
    """Like PostgreSQL, a savepoint with a failed query can only be rolled back, not released."""

    def __init__(self, conn: "_FakeConn"):
        self._conn = conn

    async def __aenter__(self):
        self._conn.savepoint_failures.append(False)

    async def __aexit__(self, exc_type, exc, tb):
        failed = self._conn.savepoint_failures.pop()
        if exc_type is None and failed:
            raise RuntimeError(ABORTED_MESSAGE)
        return False


class _FakeConn:
    """Answers _get_schema's queries; with aborts_on_error it fails later queries the way PostgreSQL does."""

    def __init__(self, dialect, tables: Dict[str, Dict[str, Any]], aborts_on_error: bool = False):
        self.dialect = dialect
        self.tables = tables
        self.aborts_on_error = aborts_on_error
        self.aborted = False
        self.savepoint_failures: List[bool] = []
        self.executed: List[Tuple[str, Dict[str, Any]]] = []
        self.unmatched_queries: List[str] = []

    def begin_nested(self):
        return _Savepoint(self)

    async def execute(self, statement, parameters=None):
        inside_failed_savepoint = bool(self.savepoint_failures) and self.savepoint_failures[-1]
        if self.aborted or inside_failed_savepoint:
            raise RuntimeError(ABORTED_MESSAGE)
        sql, bound = self._render(statement, parameters)
        self.executed.append((sql, bound))
        try:
            return self._answer(sql, bound)
        except Exception:
            self._record_failure()
            raise

    def _record_failure(self):
        if not self.aborts_on_error:
            return
        if self.savepoint_failures:
            self.savepoint_failures[-1] = True
        else:
            self.aborted = True

    def _render(self, statement, parameters) -> Tuple[str, Dict[str, Any]]:
        if isinstance(statement, TextClause):
            return _normalize(statement.text), dict(parameters or {})
        compiled = statement.compile(dialect=self.dialect, compile_kwargs={"render_postcompile": True})
        return _normalize(str(compiled)), dict(compiled.params)

    def _answer(self, sql: str, parameters: Dict[str, Any]) -> _Result:
        lowered = sql.lower()
        if "information_schema.tables" in lowered:
            return _Result([(name,) for name in self.tables])
        if "information_schema.columns" in lowered:
            return _Result(self.tables[parameters["table_name"]]["columns"])
        if "primary key" in lowered or "isprimarykey" in lowered:
            return _Result([("id",)])
        if "foreign key" in lowered or "sys.foreign_key_columns" in lowered:
            return _Result([])
        table = self._queried_table(sql)
        if table is None:
            self.unmatched_queries.append(sql)
            return _Result([])
        query_kind = self._query_kind(lowered)
        if query_kind in self.tables[table]["failing_queries"]:
            raise PermissionError(f"{query_kind} query failed for table {table}")
        if query_kind == "count":
            return _Result([(len(self.tables[table]["values"]),)])
        if query_kind == "distinct":
            return _Result([(value,) for value in self.tables[table]["values"]])
        return _Result(self.tables[table]["rows"], self.tables[table]["row_columns"])

    def _queried_table(self, sql: str) -> Optional[str]:
        from_clause = sql.split(" FROM ", 1)[-1]
        preparer = self.dialect.identifier_preparer
        return next((name for name in self.tables if preparer.quote_identifier(name) in from_clause), None)

    @staticmethod
    def _query_kind(lowered_sql: str) -> str:
        if "count(distinct" in lowered_sql:
            return "count"
        if lowered_sql.startswith("select distinct"):
            return "distinct"
        return "sample"


def _manager(db_type: str, conn: _FakeConn) -> DatabaseManager:
    manager = DatabaseManager({"database_type": db_type})
    engine = MagicMock()
    engine.dialect = conn.dialect
    engine.begin = MagicMock(return_value=_AsyncContextManager(conn))
    engine.dispose = AsyncMock()
    manager.engine = engine
    manager.db_type = db_type
    return manager


def _table(status_column: str, failing_queries: FrozenSet[str] = frozenset()) -> Dict[str, Any]:
    return {
        "columns": [ID_COLUMN, (status_column, "varchar", "YES", None, 20, None, None)],
        "row_columns": ["id", status_column],
        "rows": [(1, "open")],
        "values": ["open"],
        "failing_queries": failing_queries,
    }


def _columns_by_name(table: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {column["name"]: column for column in table["columns"]}


@pytest.mark.asyncio
async def test_mssql_schema_queries_escape_brackets_and_send_top_as_number():
    conn = _FakeConn(aioodbc_dialect(), {"odd]name": _table("st]atus")})
    manager = _manager("mssql", conn)

    schema = await manager._get_schema(include_samples=True, sample_size=1, max_categorical_values=5)

    executed_sql = [sql for sql, _ in conn.executed]
    assert "SELECT TOP 1 * FROM [odd]]name]" in executed_sql
    assert (
        "SELECT DISTINCT TOP 5 [st]]atus] FROM [odd]]name] WHERE [st]]atus] IS NOT NULL ORDER BY [st]]atus]"
        in executed_sql
    )
    assert "SELECT count(DISTINCT [st]]atus]) AS count_1 FROM [odd]]name] WHERE [st]]atus] IS NOT NULL" in executed_sql
    assert conn.unmatched_queries == []

    (table,) = schema["tables"]
    assert table["samples"] == [{"id": 1, "st]atus": "open"}]
    assert _columns_by_name(table)["st]atus"]["possible_values"] == ["open"]


def test_sample_rows_query_rejects_non_numeric_size():
    with pytest.raises(ValueError):
        _sample_rows_query("orders", "1; DROP TABLE orders")


@pytest.mark.asyncio
async def test_postgres_schema_queries_escape_double_quotes_and_name_the_schema():
    conn = _FakeConn(asyncpg_dialect(), {'odd"name': _table('st"atus')})
    manager = _manager("postgresql", conn)

    schema = await manager._get_schema(include_samples=True, sample_size=1, max_categorical_values=5)

    assert ('SELECT * FROM public."odd""name" LIMIT $1::INTEGER', {"param_1": 1}) in conn.executed
    assert (
        'SELECT DISTINCT "st""atus" FROM public."odd""name" WHERE "st""atus" IS NOT NULL '
        'ORDER BY "st""atus" LIMIT $1::INTEGER',
        {"param_1": 5},
    ) in conn.executed
    assert (
        'SELECT count(DISTINCT "st""atus") AS count_1 FROM public."odd""name" WHERE "st""atus" IS NOT NULL',
        {},
    ) in conn.executed
    assert conn.unmatched_queries == []

    (table,) = schema["tables"]
    assert table["samples"] == [{"id": 1, 'st"atus': "open"}]


@pytest.mark.asyncio
async def test_postgres_schema_read_continues_after_failed_queries():
    conn = _FakeConn(
        asyncpg_dialect(),
        {
            "secret": _table("code", failing_queries=ALL_DATA_QUERIES),
            "big": _table("kind", failing_queries=frozenset({"count"})),
            "orders": _table("state"),
        },
        aborts_on_error=True,
    )
    manager = _manager("postgresql", conn)

    schema = await manager._get_schema(include_samples=True, sample_size=1, max_categorical_values=5)

    assert "error" not in schema
    assert conn.unmatched_queries == []
    tables = {table["name"]: table for table in schema["tables"]}
    assert tables["secret"]["samples"] == []
    assert _columns_by_name(tables["secret"])["code"]["possible_values"] == []
    assert tables["big"]["samples"] == [{"id": 1, "kind": "open"}]
    assert _columns_by_name(tables["big"])["kind"]["possible_values"] == []
    assert tables["orders"]["samples"] == [{"id": 1, "state": "open"}]
    assert _columns_by_name(tables["orders"])["state"]["possible_values"] == ["open"]
