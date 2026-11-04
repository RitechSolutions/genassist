"""Values written in a SQL query never reach the logs through database errors."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.exceptions.error_policy import sanitize_database_error, sanitize_error_detail
from app.core.utils.sensitive_data_utils import redact_sql_literal_values, redact_sql_literals
from app.modules.integration.database.database_manager import DatabaseManager
from app.modules.integration.snowflake.snowflake_manager import SnowflakeManager
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode
from app.modules.workflow.engine.workflow_state import WorkflowState

SECRET = "secret"
QUERY = "SELECT * FROM missing_accounts WHERE password='secret'"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (QUERY, "SELECT * FROM missing_accounts WHERE password='***'"),
        (
            "SELECT * FROM t WHERE \"password\" = 'it''s secret' AND id = 1",
            "SELECT * FROM t WHERE \"password\" = '***' AND id = 1",
        ),
        ("SELECT * FROM t WHERE p IN ('secret', 'other')", "SELECT * FROM t WHERE p IN ('***', '***')"),
        ("SELECT * FROM t WHERE p = $$secret$$", "SELECT * FROM t WHERE p = '***'"),
        ("SELECT * FROM t WHERE p = $pw$secret$pw$", "SELECT * FROM t WHERE p = '***'"),
        ("SELECT * FROM t WHERE p = 'secret", "SELECT * FROM t WHERE p = '***'"),
        ("SELECT * FROM t WHERE id = $1", "SELECT * FROM t WHERE id = $1"),
    ],
)
def test_redact_sql_literals_masks_values_and_keeps_names(sql, expected):
    assert redact_sql_literals(sql) == expected


def test_double_quoted_strings_are_masked_only_when_asked():
    sql = 'SELECT * FROM t WHERE password = "secret"'

    assert redact_sql_literals(sql) == sql
    assert redact_sql_literals(sql, double_quoted=True) == 'SELECT * FROM t WHERE password = "***"'


@pytest.mark.parametrize(
    "driver_message",
    [
        # SQLAlchemy repeats the statement
        '(ProgrammingError) relation "missing_accounts" does not exist\n'
        f"[SQL: {QUERY}]",
        # PostgreSQL repeats the value alone
        'invalid input syntax for type integer: "secret"',
        'duplicate key value violates unique constraint "u" DETAIL: Key (password)=(secret) already exists.',
        # MySQL / MSSQL
        "Duplicate entry 'secret' for key 'PRIMARY'",
        "You have an error in your SQL syntax; check the manual near 'password='secret'' at line 1",
        "Conversion failed when converting the varchar value 'secret' to data type int.",
    ],
)
def test_query_literal_values_are_removed_from_driver_messages(driver_message):
    assert SECRET not in redact_sql_literal_values(driver_message, QUERY)


def test_literal_values_do_not_mangle_names_that_contain_them():
    message = redact_sql_literal_values(
        'relation "active_orders" does not exist, value "active"',
        "SELECT * FROM active_orders WHERE status = 'active'",
    )

    assert message == 'relation "active_orders" does not exist, value "***"'


def test_sanitize_database_error_keeps_type_and_table_name():
    error = RuntimeError(
        "(sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) "
        "<class 'asyncpg.exceptions.UndefinedTableError'>: "
        'relation "missing_accounts" does not exist\n'
        "[SQL: SELECT * FROM missing_accounts WHERE password = 'my secret phrase']"
    )

    message = sanitize_database_error(error, query="SELECT * FROM missing_accounts WHERE password = 'my secret phrase'")

    assert SECRET not in message
    assert "phrase" not in message
    assert "UndefinedTableError" in message
    assert 'relation "missing_accounts" does not exist' in message


def test_sanitize_database_error_still_hides_bound_values():
    message = sanitize_database_error(
        RuntimeError("driver rejected 'bound-secret' and 'literal-secret'"),
        query="SELECT :v, 'literal-secret'",
        parameters={"v": "bound-secret"},
    )

    assert "bound-secret" not in message
    assert "literal-secret" not in message
    assert "[BOUND_VALUE]" in message


@pytest.mark.parametrize("detail", ["password='secret'", 'password = "secret"', "password=secret"])
def test_sanitize_error_detail_masks_quoted_passwords(detail):
    assert SECRET not in sanitize_error_detail(f"login failed {detail} extra")


# --------------------------------------------------------------------------- #
# DatabaseManager against a real SQLite database
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def sqlite_manager(tmp_path):
    manager = DatabaseManager({"database_type": "sqlite", "database_path": str(tmp_path / "db.sqlite")})
    await manager.connect()
    async with manager.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE people (id INTEGER)"))
    yield manager
    await manager.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["execute_query", "execute_read_query"])
async def test_failed_query_logs_no_query_values(sqlite_manager, caplog, method):
    with caplog.at_level(logging.DEBUG):
        rows, error = await getattr(sqlite_manager, method)(QUERY)

    assert rows == []
    assert SECRET not in error
    assert SECRET not in caplog.text
    assert "no such table: missing_accounts" in caplog.text
    assert "password='***'" in caplog.text


@pytest.mark.asyncio
async def test_failed_stream_logs_no_query_values(sqlite_manager, caplog):
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError) as raised:
            async for _chunk in sqlite_manager.stream_query(QUERY, chunk_size=10):
                pass

    assert SECRET not in str(raised.value)
    assert SECRET not in caplog.text
    assert "no such table: missing_accounts" in caplog.text


@pytest.mark.asyncio
async def test_sqlalchemy_does_not_echo_datasource_statements(sqlite_manager, caplog):
    # init_logging puts sqlalchemy.engine at DEBUG whenever settings.DEBUG is on
    engine_logger = logging.getLogger("sqlalchemy.engine")
    previous = engine_logger.level
    engine_logger.setLevel(logging.DEBUG)
    try:
        with caplog.at_level(logging.DEBUG):
            await sqlite_manager.execute_read_query("SELECT 'secret' AS v FROM people")
    finally:
        engine_logger.setLevel(previous)

    assert SECRET not in caplog.text


# --------------------------------------------------------------------------- #
# The reported scenario: Train Data Source on a missing table
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_train_data_source_failure_logs_no_password(sqlite_manager, tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    node_config = {
        "id": "source-1",
        "type": "trainDataSourceNode",
        "data": {"sourceType": "datasource", "dataSourceId": "ds-1", "query": QUERY},
    }
    state = WorkflowState(
        workflow={"nodes": [node_config], "source_edges": {}, "target_edges": {}},
        initial_values={},
        thread_id="thread-1",
    )
    node = TrainDataSourceNode("source-1", node_config, state)
    monkeypatch.setattr(node, "_get_database_manager", AsyncMock(return_value=sqlite_manager))

    with caplog.at_level(logging.DEBUG):
        await node.execute()

    error = node.state.node_execution_status[node.node_id]["error"]
    assert error.endswith("Database query failed: no such table: missing_accounts")
    assert SECRET not in caplog.text
    assert "no such table: missing_accounts" in caplog.text


# --------------------------------------------------------------------------- #
# Snowflake
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_snowflake_error_logs_no_query_values(caplog):
    manager = SnowflakeManager({})
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError(
        "001003 (42000): SQL compilation error: Object 'MISSING_ACCOUNTS' does not exist "
        f"in query {QUERY}"
    )
    manager.connection = MagicMock()
    manager.connection.cursor.return_value = cursor

    with caplog.at_level(logging.ERROR):
        rows, error = await manager.execute_query(QUERY)

    assert rows == []
    assert SECRET not in error
    assert SECRET not in caplog.text
    assert "MISSING_ACCOUNTS" in error
