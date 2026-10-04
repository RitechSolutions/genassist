"""Client-safe workflow-test errors produced by the real Train Data Source node."""

import logging
import re
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from sqlalchemy import text

from app.core.exceptions.error_messages import ErrorKey, get_error_message
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import _response_error_detail
from app.modules.integration.database.database_manager import DatabaseManager
from app.modules.workflow.engine import base_node as base_node_module
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode
from app.modules.workflow.engine.workflow_state import WorkflowState


def _node(data: dict, *, node_type: str = "trainDataSourceNode") -> TrainDataSourceNode:
    node_config = {"id": "source-1", "type": node_type, "data": data}
    state = WorkflowState(
        workflow={
            "nodes": [node_config],
            "source_edges": {},
            "target_edges": {},
        },
        initial_values={},
        thread_id="thread-1",
    )
    return TrainDataSourceNode("source-1", node_config, state)


async def _public_failure(node: TrainDataSourceNode) -> str:
    await node.execute()
    error = node.state.node_execution_status[node.node_id]["error"]
    return error.split(": ", 1)[1]


@pytest_asyncio.fixture
async def sqlite_manager(tmp_path):
    manager = DatabaseManager(
        {
            "database_type": "sqlite",
            "database_path": str(tmp_path / "training.sqlite"),
        }
    )
    await manager.connect()
    async with manager.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE people (id INTEGER, name TEXT)"))
        await connection.execute(text("INSERT INTO people VALUES (1, 'Ada')"))
    yield manager
    await manager.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"sourceType": "datasource", "query": "SELECT 1"}, "Select a data source."),
        (
            {"sourceType": "datasource", "dataSourceId": "ds-1", "query": ""},
            "Enter a SQL query.",
        ),
        ({"sourceType": "csv"}, "Upload a training file."),
    ],
)
async def test_missing_configuration_names_the_action(data, expected):
    node = _node(data)
    assert await _public_failure(node) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("SELECT nme FROM people", "no such column: nme"),
        ("SELECT * FROM peple", "no such table: peple"),
    ],
)
async def test_query_mistakes_are_actionable_and_do_not_echo_sql(
    sqlite_manager,
    tmp_path,
    monkeypatch,
    query,
    reason,
):
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    node = _node(
        {
            "sourceType": "datasource",
            "dataSourceId": "ds-1",
            "query": query,
        }
    )
    monkeypatch.setattr(node, "_get_database_manager", AsyncMock(return_value=sqlite_manager))

    public_error = await _public_failure(node)

    assert public_error == f"Database query failed: {reason}"
    assert "[SQL:" not in public_error
    assert query not in public_error


@pytest.mark.asyncio
async def test_connection_failure_hides_driver_details(monkeypatch):
    async def fail_stream(*_args, **_kwargs):
        raise RuntimeError("could not connect password=secret host=db.internal")
        yield

    manager = Mock()
    manager.get_db_type.return_value = "postgresql"
    manager.stream_query = Mock(side_effect=fail_stream)
    node = _node(
        {
            "sourceType": "datasource",
            "dataSourceId": "ds-1",
            "query": "SELECT 1",
        }
    )
    monkeypatch.setattr(node, "_get_database_manager", AsyncMock(return_value=manager))

    public_error = await _public_failure(node)

    assert public_error == (
        "Could not run the query on the selected data source. "
        "Check the query and connection settings."
    )
    assert "secret" not in public_error
    assert "db.internal" not in public_error


@pytest.mark.asyncio
async def test_missing_uploaded_file_does_not_publish_its_path(tmp_path):
    missing_path = tmp_path / "private" / "missing.csv"
    node = _node(
        {
            "sourceType": "csv",
            "csvFilePath": str(missing_path),
            "csvFileName": "missing.csv",
        }
    )

    public_error = await _public_failure(node)

    assert public_error == (
        "The uploaded training file is no longer available. Upload it again."
    )
    assert str(missing_path) not in public_error


@pytest.mark.asyncio
async def test_invalid_csv_encoding_is_safe_for_api_and_workflow(
    monkeypatch, tmp_path, caplog
):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
    source = tmp_path / "private" / "customer-data.csv"
    source.parent.mkdir()
    source.write_bytes(b"id,name\n1,TOP-SECRET-\xff\n")
    data = {
        "sourceType": "csv",
        "csvFilePath": str(source),
        "csvFileName": source.name,
    }
    expected = (
        "The uploaded CSV could not be decoded as UTF-8. "
        "Save it with UTF-8 encoding and upload it again."
    )

    with caplog.at_level(logging.INFO):
        with pytest.raises(AppException) as exc_info:
            await _node(data).process(data)
        public_error = await _public_failure(_node(data))

    error = exc_info.value
    assert error.error_key == ErrorKey.ML_EXTRACT_FILE_ENCODING_INVALID
    assert _response_error_detail(error) == expected

    assert public_error == expected
    assert str(source) not in public_error
    assert "TOP-SECRET" not in public_error
    assert "0xff" not in public_error
    assert "�" not in public_error
    assert str(source) not in caplog.text
    assert source.name not in caplog.text
    assert "TOP-SECRET" not in caplog.text
    assert "Traceback" not in caplog.text
    assert not list((tmp_path / "train" / "thread-1").glob("*.csv"))


@pytest.mark.asyncio
async def test_hidden_detail_is_logged_with_secrets_masked(monkeypatch, caplog):
    node = _node({}, node_type="trainDataSourceNodeV2")
    monkeypatch.setattr(
        node,
        "process",
        AsyncMock(
            side_effect=AppException(
                ErrorKey.INTERNAL_ERROR,
                error_detail="could not connect password=secret host=db.internal",
            )
        ),
    )

    with caplog.at_level(logging.ERROR):
        public_error = await _public_failure(node)

    assert public_error == get_error_message(ErrorKey.ML_EXTRACT_FAILED)
    assert "secret" not in public_error
    assert "db.internal" not in public_error
    assert "could not connect" in caplog.text
    assert "secret" not in caplog.text
    assert "password=***" in caplog.text
    assert re.search(r"AppException at .+\.py:\d+ in ", caplog.text)


@pytest.mark.parametrize(
    ("driver_message", "expected"),
    [
        (
            "(sqlite3.OperationalError) no such column: nme\n"
            "[SQL: SELECT nme FROM people]",
            "Database query failed: no such column: nme",
        ),
        (
            '(psycopg.errors.UndefinedColumn) column "nme" does not exist',
            'Database query failed: column "nme" does not exist',
        ),
        (
            "(1054, \"Unknown column 'nme' in 'field list'\")",
            "Database query failed: Unknown column 'nme' in 'field list'",
        ),
        (
            "(1146, \"Table 'shop.peple' doesn't exist\")",
            "Database query failed: Table 'shop.peple' doesn't exist",
        ),
        (
            "(1064, \"You have an error in your SQL syntax; check the manual "
            "near 'FORM people' at line 1\")",
            "Database query failed: You have an error in your SQL syntax; "
            "check the manual near 'FORM people'",
        ),
        (
            "Invalid column name 'nme'. (207) (SQLExecDirectW)",
            "Database query failed: Invalid column name 'nme'",
        ),
        (
            "Invalid object name 'peple'. (208)",
            "Database query failed: Invalid object name 'peple'",
        ),
        (
            "SQL compilation error: error line 1 at position 7\n"
            "invalid identifier 'NME'",
            "Database query failed: invalid identifier 'NME'",
        ),
        (
            'syntax error at or near "FORM"\nLINE 1: SELECT * FORM people',
            'Database query failed: syntax error at or near "FORM"',
        ),
        (
            'near "FORM": syntax error\n[SQL: SELECT * FORM people]',
            'Database query failed: near "FORM": syntax error',
        ),
        (
            'column "a" does not exist (server db.internal:5432)',
            'Database query failed: column "a" does not exist',
        ),
    ],
)
def test_database_classifier_publishes_only_the_safe_reason(driver_message, expected):
    assert TrainDataSourceNode._client_safe_database_error(
        RuntimeError(driver_message),
        has_bound_parameters=False,
    ) == expected


@pytest.mark.parametrize(
    "driver_message",
    [
        (
            'connection to server at "db.internal" (10.0.0.5), port 5432 failed: '
            'FATAL: password authentication failed for user "admin"'
        ),
        'FATAL: database "prod_db" does not exist',
        'FATAL: role "admin" does not exist',
        "permission denied for table salaries",
    ],
)
def test_database_classifier_keeps_connection_and_access_details_private(driver_message):
    public_error = TrainDataSourceNode._client_safe_database_error(
        RuntimeError(driver_message),
        has_bound_parameters=False,
    )
    assert public_error == (
        "Could not run the query on the selected data source. "
        "Check the query and connection settings."
    )
    assert "db.internal" not in public_error


@pytest.mark.asyncio
async def test_otel_span_uses_only_the_masked_train_data_source_diagnostic(
    monkeypatch,
):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(base_node_module, "is_otel_runtime_enabled", lambda: True)
    monkeypatch.setattr(
        base_node_module.trace,
        "get_tracer",
        lambda name: provider.get_tracer(name),
    )

    node = _node({})
    monkeypatch.setattr(
        node,
        "process",
        AsyncMock(
            side_effect=RuntimeError(
                "could not connect password=secret host=db.internal"
            )
        ),
    )

    await node.execute()

    (span,) = exporter.get_finished_spans()
    assert len(span.events) == 1
    event = next(event for event in span.events if event.name == "exception")
    recorded_text = " ".join(
        [span.status.description or ""]
        + [str(value) for value in event.attributes.values()]
    )

    assert "password=secret" not in recorded_text
    assert "password=***" in recorded_text
    assert "Traceback" not in recorded_text
    assert event.attributes["exception.type"] == "RuntimeError"
    assert ".py:" in event.attributes["genassist.exception.location"]
    public_error = node.state.node_execution_status[node.node_id]["error"]
    assert "secret" not in public_error
    assert public_error.endswith(get_error_message(ErrorKey.ML_EXTRACT_FAILED))

    provider.shutdown()
