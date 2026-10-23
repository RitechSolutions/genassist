"""Unit tests for seeding an empty database: services resolved through DI must get a session"""

import asyncio
import contextvars
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_scope import require_tenant_context
from app.db.multi_tenant_session import multi_tenant_manager


class _FakeConnection:
    async def run_sync(self, _fn):
        return None


class _FakeBegin:
    async def __aenter__(self):
        return _FakeConnection()

    async def __aexit__(self, *_exc):
        return False


def _fake_session():
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def fake_master_db(monkeypatch):
    """An engine that creates no tables and a session factory that hands out fake sessions."""
    engine = MagicMock()
    engine.begin = lambda: _FakeBegin()
    sessions = []

    def session_factory():
        session = _fake_session()
        sessions.append(session)
        return session

    monkeypatch.setattr(multi_tenant_manager, "get_tenant_engine", lambda tenant: engine)
    monkeypatch.setattr(multi_tenant_manager, "get_tenant_session_factory", lambda tenant: session_factory)
    return sessions


def _run_without_tenant_context(coro):
    """Run the coroutine the way app startup does: before any tenant context is set."""
    loop = asyncio.get_event_loop()
    return loop.create_task(coro, context=contextvars.Context())


@pytest.mark.asyncio
async def test_cold_start_seeds_through_di_without_a_tenant_context(monkeypatch, fake_master_db):
    seen = {}

    async def fake_seed_data(session, injector):
        # Seeding resolves services through DI, which asks for the request-scoped session
        seen["tenant"] = require_tenant_context()
        seen["di_session"] = injector.get(AsyncSession)
        seen["session"] = session

    monkeypatch.setattr("app.db.seed.seed.seed_data", fake_seed_data)

    await _run_without_tenant_context(multi_tenant_manager.cold_start_db("master"))

    assert seen["tenant"] == "master"
    # The seed function and the services it calls share one session, which is committed
    assert seen["di_session"] is seen["session"]
    assert len(fake_master_db) == 1
    fake_master_db[0].commit.assert_awaited_once()
    fake_master_db[0].rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_cold_start_fails_loudly_and_rolls_back_when_seeding_fails(monkeypatch, fake_master_db):
    async def failing_seed_data(session, injector):
        raise RuntimeError("seed failed")

    monkeypatch.setattr("app.db.seed.seed.seed_data", failing_seed_data)

    with pytest.raises(RuntimeError, match="seed failed"):
        await _run_without_tenant_context(multi_tenant_manager.cold_start_db("master"))

    fake_master_db[0].rollback.assert_awaited_once()
    fake_master_db[0].commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_seed_tenant_database_still_reports_failure_instead_of_raising(monkeypatch, fake_master_db):
    async def failing_seed_data(session, injector):
        raise RuntimeError("seed failed")

    monkeypatch.setattr("app.db.seed.seed.seed_data", failing_seed_data)

    assert await _run_without_tenant_context(multi_tenant_manager.seed_tenant_database("acme")) is False

