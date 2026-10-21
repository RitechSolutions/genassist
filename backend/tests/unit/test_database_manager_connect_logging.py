"""Unit tests for how DatabaseManager.connect builds connection URLs and logs them."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.dialects.mssql.aioodbc import dialect as aioodbc_dialect

from app.core.utils.encryption_utils import encrypt_key
from app.modules.integration.database import database_manager as database_manager_module
from app.modules.integration.database.database_manager import DatabaseManager

PASSWORD = "S3cret-pw-67616"
SPECIAL_PASSWORD = "p@ss:S3cret/67616"
SECRET_FRAGMENT = "S3cret"


def _host_config(database_type: str, port: int, password: str = PASSWORD) -> Dict[str, Any]:
    return {
        "database_type": database_type,
        "database_host": "db.internal",
        "database_port": port,
        "database_user": "reader",
        "database_password": encrypt_key(password),
        "database_name": "shop",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "expected_line", "expected_password"),
    [
        (_host_config("postgresql", 5432), "Connecting to PostgreSQL at db.internal:5432/shop", PASSWORD),
        (_host_config("mysql", 3306), "Connecting to MySQL at db.internal:3306/shop", PASSWORD),
        (_host_config("mssql", 1433), "Connecting to MSSQL...", PASSWORD),
        (
            _host_config("postgresql", 5432, SPECIAL_PASSWORD),
            "Connecting to PostgreSQL at db.internal:5432/shop",
            SPECIAL_PASSWORD,
        ),
        (
            {
                "database_type": "postgresql",
                "connection_string": f"postgresql+asyncpg://reader:{PASSWORD}@db.internal:5432/shop",
            },
            "Connecting to PostgreSQL with the configured connection string",
            PASSWORD,
        ),
    ],
    ids=["postgresql-host", "mysql-host", "mssql-host", "postgresql-special-password", "postgresql-connection-string"],
)
async def test_connect_passes_the_password_to_the_driver_without_logging_it(
    caplog, config, expected_line, expected_password
):
    manager = DatabaseManager(config)
    engine_factory = MagicMock()

    with caplog.at_level(logging.INFO), patch.object(database_manager_module, "create_async_engine", engine_factory):
        await manager.connect()

    assert expected_line in caplog.text
    assert SECRET_FRAGMENT not in caplog.text
    assert engine_factory.call_args.args[0].password == expected_password


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "connection_string",
    [
        f"postgresql+asyncpg:/reader:{PASSWORD}@db.internal:5432/shop",
        f"postgresql+asyncpg://reader:{SPECIAL_PASSWORD}@db.internal:5432/shop",
    ],
    ids=["missing-slash", "unencoded-at-and-colon"],
)
async def test_connect_rejects_an_unreadable_connection_string_without_exposing_the_password(
    caplog, connection_string
):
    manager = DatabaseManager({"database_type": "postgresql", "connection_string": connection_string})

    with caplog.at_level(logging.INFO), pytest.raises(ValueError) as raised:
        await manager.connect()

    assert str(raised.value) == "Invalid database connection string"
    assert raised.value.__context__ is None
    assert SECRET_FRAGMENT not in "".join(traceback.format_exception(raised.value))
    assert SECRET_FRAGMENT not in caplog.text


@pytest.mark.asyncio
async def test_connect_keeps_the_message_for_an_unknown_driver(caplog):
    manager = DatabaseManager(
        {"database_type": "postgresql", "connection_string": f"postgres://reader:{PASSWORD}@db.internal:5432/shop"}
    )

    with caplog.at_level(logging.INFO), pytest.raises(Exception) as raised:
        await manager.connect()

    assert "Can't load plugin" in str(raised.value)
    assert SECRET_FRAGMENT not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("driver_setting", ["ODBC+Driver+18+for+SQL+Server", "ODBC Driver 18 for SQL Server"])
async def test_connect_passes_the_decoded_mssql_driver_name(driver_setting):
    manager = DatabaseManager(_host_config("mssql", 1433))
    engine_factory = MagicMock()

    with patch.object(database_manager_module.settings, "MSSQL_DRIVER", driver_setting), patch.object(
        database_manager_module, "create_async_engine", engine_factory
    ):
        await manager.connect()

    _, connect_kwargs = aioodbc_dialect().create_connect_args(engine_factory.call_args.args[0])
    assert connect_kwargs["dsn"].startswith("DRIVER={ODBC Driver 18 for SQL Server};")
