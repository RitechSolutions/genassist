"""Unit tests for the replica circuit breaker: a failing replica degrades to the writer"""

import socket

import pytest
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError, ProgrammingError
from sqlalchemy.exc import TimeoutError as SQLTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.db import replica_health as health_module
from app.db.replica_health import ReplicaSession, replica_health


def _db_error(cls):
    return cls("SELECT 1", {}, Exception("boom"))


@pytest.fixture(autouse=True)
def fresh_breaker(monkeypatch):
    monkeypatch.setattr(settings, "DB_READ_FAILURE_COOLDOWN_SECONDS", 30)
    replica_health.reset()
    try:
        yield replica_health
    finally:
        replica_health.reset()


def _session():
    """A ReplicaSession that never touches real connection machinery."""
    return ReplicaSession.__new__(ReplicaSession)


async def _execute_raising(monkeypatch, error):
    async def boom(self, *args, **kwargs):
        raise error

    monkeypatch.setattr(AsyncSession, "execute", boom)
    return _session()


def test_replica_starts_available(fresh_breaker):
    assert fresh_breaker.is_available() is True


def test_failure_opens_the_circuit(fresh_breaker):
    fresh_breaker.mark_failure(RuntimeError("replica down"))
    assert fresh_breaker.is_available() is False


def test_circuit_closes_again_once_the_cooldown_expires(fresh_breaker, monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(health_module.time, "monotonic", lambda: clock["now"])

    fresh_breaker.mark_failure(RuntimeError("replica down"))
    assert fresh_breaker.is_available() is False

    clock["now"] += settings.DB_READ_FAILURE_COOLDOWN_SECONDS - 1
    assert fresh_breaker.is_available() is False

    clock["now"] += 2
    assert fresh_breaker.is_available() is True


def test_cooldown_of_zero_keeps_reads_on_the_replica(fresh_breaker, monkeypatch):
    monkeypatch.setattr(settings, "DB_READ_FAILURE_COOLDOWN_SECONDS", 0)
    fresh_breaker.mark_failure(RuntimeError("replica down"))
    assert fresh_breaker.is_available() is True


@pytest.mark.asyncio
@pytest.mark.parametrize("error_class", [OperationalError, InterfaceError])
async def test_transport_faults_open_the_circuit_and_still_raise(monkeypatch, fresh_breaker, error_class):
    session = await _execute_raising(monkeypatch, _db_error(error_class))
    with pytest.raises(error_class):
        await session.execute("SELECT 1")
    assert fresh_breaker.is_available() is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [ConnectionRefusedError("refused"), socket.gaierror(-2, "Name or service not known"), TimeoutError("timed out")],
    ids=["refused", "dns", "socket-timeout"],
)
async def test_socket_level_faults_open_the_circuit(monkeypatch, fresh_breaker, error):
    """asyncpg raises these without a SQLAlchemy wrapper when the replica host is gone."""
    session = await _execute_raising(monkeypatch, error)
    with pytest.raises(OSError):
        await session.execute("SELECT 1")
    assert fresh_breaker.is_available() is False


@pytest.mark.asyncio
async def test_pool_exhaustion_does_not_open_the_circuit(monkeypatch, fresh_breaker):
    """A busy replica is a load condition. Diverting every read to the writer because
    the read pool filled up is how a busy replica becomes writer overload."""
    session = await _execute_raising(monkeypatch, SQLTimeoutError("QueuePool limit reached"))
    with pytest.raises(SQLTimeoutError):
        await session.execute("SELECT 1")
    assert fresh_breaker.is_available() is True


@pytest.mark.asyncio
async def test_a_statement_timeout_does_not_open_the_circuit(monkeypatch, fresh_breaker):
    """asyncpg surfaces a server-side statement timeout as a bare DBAPIError. It means
    the query was too slow, not that the replica is unusable."""
    session = await _execute_raising(monkeypatch, _db_error(DBAPIError))
    with pytest.raises(DBAPIError):
        await session.execute("SELECT pg_sleep(9999)")
    assert fresh_breaker.is_available() is True


@pytest.mark.asyncio
async def test_a_bad_statement_does_not_open_the_circuit(monkeypatch, fresh_breaker):
    """A malformed query fails the same way on the writer, so it says nothing about the replica."""
    session = await _execute_raising(monkeypatch, _db_error(ProgrammingError))
    with pytest.raises(ProgrammingError):
        await session.execute("SELECT nope")
    assert fresh_breaker.is_available() is True


@pytest.mark.asyncio
async def test_successful_reads_leave_the_circuit_closed(monkeypatch, fresh_breaker):
    async def ok(self, *args, **kwargs):
        return "rows"

    monkeypatch.setattr(AsyncSession, "execute", ok)
    assert await _session().execute("SELECT 1") == "rows"
    assert fresh_breaker.is_available() is True


@pytest.mark.asyncio
async def test_a_dead_connection_opens_the_circuit(monkeypatch, fresh_breaker):
    """A mid-query disconnect or an Aurora instance going away arrives as a DBAPIError
    that SQLAlchemy flags as invalidated, not as an OSError."""
    error = _db_error(DBAPIError)
    error.connection_invalidated = True
    session = await _execute_raising(monkeypatch, error)

    with pytest.raises(DBAPIError):
        await session.execute("SELECT 1")
    assert fresh_breaker.is_available() is False


@pytest.mark.asyncio
async def test_a_failed_read_never_touches_the_write_session(monkeypatch, fresh_breaker):
    """Rerunning it there would flush the request's pending writes early and could
    surface the replica fault as an unrelated error."""

    class WriterSpy:
        def __init__(self):
            self.calls = []

        async def execute(self, *args, **kwargs):
            self.calls.append(args)
            return "rows from the writer"

    spy = WriterSpy()
    session = await _execute_raising(monkeypatch, ConnectionRefusedError("replica gone"))
    session.writer_fallback = spy

    with pytest.raises(ConnectionRefusedError):
        await session.execute("SELECT 1")
    assert spy.calls == []


def test_routed_repositories_only_issue_sql_through_execute():
    """The fault detector wraps execute. scalar, get and stream bypass it, so a read
    added with one of those would silently stop feeding the circuit breaker."""
    import ast
    from pathlib import Path as _Path

    from app.repositories import analytics_read, conversations_read, dashboard, llm_usage_read

    bypassing = {"scalar", "get", "get_one", "stream", "stream_scalars", "refresh", "merge", "connection"}
    offenders = []
    for module in (analytics_read, conversations_read, dashboard, llm_usage_read):
        path = _Path(module.__file__)
        for node in ast.walk(ast.parse(path.read_text())):
            is_db_call = (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in bypassing
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "db"
            )
            if is_db_call:
                offenders.append(f"{path.name}:{node.lineno} self.db.{node.func.attr}()")
    assert offenders == [], offenders
