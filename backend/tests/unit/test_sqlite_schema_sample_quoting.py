"""Unit tests for SQLite identifier quoting in DatabaseManager._get_schema."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.modules.integration.database.database_manager import DatabaseManager

QUOTED_TABLE = 'odd`na"me'
QUOTED_COLUMN = 'st`at"us'


def _create_database(path: Path, statements: List[str]) -> None:
    with closing(sqlite3.connect(path)) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


async def _read_schema(path: Path) -> Dict[str, Any]:
    manager = DatabaseManager({"database_type": "sqlite", "database_path": str(path)})
    return await manager._get_schema(include_samples=True, sample_size=1, max_categorical_values=5)


def _table(schema: Dict[str, Any], name: str) -> Dict[str, Any]:
    table_names = [table["name"] for table in schema["tables"]]
    assert name in table_names, f"table {name!r} missing from schema tables {table_names}"
    return schema["tables"][table_names.index(name)]


@pytest.mark.asyncio
async def test_sqlite_schema_reads_table_and_column_with_quote_characters(tmp_path):
    db_path = tmp_path / "quoted_names.sqlite"
    _create_database(
        db_path,
        [
            'CREATE TABLE "odd`na""me" (id INTEGER PRIMARY KEY, "st`at""us" VARCHAR(20))',
            "INSERT INTO \"odd`na\"\"me\" VALUES (1, 'open'), (2, 'closed')",
        ],
    )

    schema = await _read_schema(db_path)

    assert "error" not in schema
    table = _table(schema, QUOTED_TABLE)
    assert [column["name"] for column in table["columns"]] == ["id", QUOTED_COLUMN]
    assert table["samples"] == [{"id": 1, QUOTED_COLUMN: "open"}]

    status_column = {column["name"]: column for column in table["columns"]}[QUOTED_COLUMN]
    assert status_column["possible_values"] == ["closed", "open"]
    assert status_column["total_distinct_count"] == 2


@pytest.mark.asyncio
async def test_sqlite_schema_reads_foreign_key_of_table_with_quote_characters(tmp_path):
    db_path = tmp_path / "quoted_foreign_key.sqlite"
    _create_database(
        db_path,
        [
            "CREATE TABLE parent (id INTEGER PRIMARY KEY)",
            'CREATE TABLE "odd`na""me" (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))',
            "INSERT INTO parent VALUES (1)",
            'INSERT INTO "odd`na""me" VALUES (1, 1)',
        ],
    )

    schema = await _read_schema(db_path)

    assert "error" not in schema
    assert _table(schema, QUOTED_TABLE)["samples"] == [{"id": 1, "parent_id": 1}]
    assert {
        "table": QUOTED_TABLE,
        "column": "parent_id",
        "referenced_table": "parent",
        "referenced_column": "id",
    } in schema["relationships"]


@pytest.mark.asyncio
async def test_sqlite_schema_skips_table_it_cannot_read(tmp_path):
    db_path = tmp_path / "unreadable_table.sqlite"
    _create_database(
        db_path,
        [
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, state VARCHAR(10))",
            "INSERT INTO orders VALUES (1, 'paid')",
            "PRAGMA writable_schema=ON",
            "INSERT INTO sqlite_master (type, name, tbl_name, rootpage, sql) "
            "VALUES ('table', 'broken', 'broken', 0, 'CREATE VIRTUAL TABLE broken USING missing_module()')",
        ],
    )

    schema = await _read_schema(db_path)

    assert "error" not in schema
    assert [table["name"] for table in schema["tables"]] == ["orders"]
    orders = _table(schema, "orders")
    assert orders["samples"] == [{"id": 1, "state": "paid"}]
    assert {column["name"]: column for column in orders["columns"]}["state"]["possible_values"] == ["paid"]
