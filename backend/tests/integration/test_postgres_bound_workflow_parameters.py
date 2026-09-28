"""PostgreSQL coverage for workflow values that arrive as strings."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.modules.integration.database.database_manager import DatabaseManager
from app.modules.workflow.engine.utils import BoundParameters

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _postgres_url() -> str:
    url = os.getenv("TEST_PG_URL", "")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _parameters(**values) -> BoundParameters:
    parameters = BoundParameters()
    for name, value in values.items():
        parameters[name] = value
        parameters.variable_names[name] = name
    return parameters


@pytest.mark.skipif(not os.getenv("TEST_PG_URL"), reason="TEST_PG_URL is not configured")
async def test_postgres_bound_strings_are_coerced_and_never_interpolated():
    table_name = f"test_bound_values_{uuid4().hex}"
    manager = DatabaseManager(
        {
            "database_type": "postgresql",
            "connection_string": _postgres_url(),
        }
    )
    await manager.connect()
    try:
        async with manager.engine.begin() as conn:
            await conn.execute(
                text(f"CREATE TABLE {table_name} (city TEXT, quantity INTEGER, event_date DATE, created_at TIMESTAMP)")
            )
            await conn.execute(
                text(
                    f"INSERT INTO {table_name} "
                    "(city, quantity, event_date, created_at) VALUES "
                    "('Tirana', 2, DATE '2026-09-16', TIMESTAMP '2026-09-16 09:00:00'), "
                    "('Tirana', 3, DATE '2026-09-17', TIMESTAMP '2026-09-17 10:00:00'), "
                    "('Pristina', 1, DATE '2026-09-18', TIMESTAMP '2026-09-18 11:00:00')"
                )
            )

        cases = [
            (
                f"SELECT city FROM {table_name} WHERE city = :city",
                _parameters(city="Tirana"),
                2,
            ),
            (
                f"SELECT city FROM {table_name} WHERE city = :city",
                _parameters(city="x' OR '1'='1"),
                0,
            ),
            (
                f"SELECT city FROM {table_name} WHERE city = :city",
                _parameters(city="O'Brien"),
                0,
            ),
            (
                f"SELECT city FROM {table_name} WHERE quantity >= :quantity",
                _parameters(quantity="2"),
                2,
            ),
            (
                f"SELECT city FROM {table_name} WHERE event_date >= :event_date",
                _parameters(event_date="2026-09-17"),
                2,
            ),
            (
                f"SELECT city FROM {table_name} WHERE created_at >= :created_at",
                _parameters(created_at="2026-09-17T00:00:00"),
                2,
            ),
            (
                f"SELECT city FROM {table_name} ORDER BY city LIMIT :row_limit",
                _parameters(row_limit="2"),
                2,
            ),
            (
                f"SELECT city FROM {table_name} WHERE event_date = (:event_date)::date",
                _parameters(event_date="2026-09-16"),
                1,
            ),
        ]

        for query, parameters, expected_count in cases:
            rows, error = await manager.execute_read_query(query, parameters)
            assert error is None
            assert len(rows) == expected_count
    finally:
        if manager.engine:
            async with manager.engine.begin() as conn:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        await manager.disconnect()
