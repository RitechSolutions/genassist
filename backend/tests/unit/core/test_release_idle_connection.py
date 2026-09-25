"""Unit tests for releasing a request's pooled connection only when nothing was written"""

from unittest.mock import AsyncMock

import pytest

from app.core.utils import db_connection_utils
from app.core.utils.db_connection_utils import release_idle_connection
from app.db.events.write_tracking import WROTE_IN_TRANSACTION


class FakeSession:
    def __init__(self, in_transaction=True, wrote=False, pending=False, commit_error=None):
        self._in_transaction = in_transaction
        self.info = {WROTE_IN_TRANSACTION: True} if wrote else {}
        self.new = {object()} if pending else set()
        self.dirty = set()
        self.deleted = set()
        self.commit = AsyncMock(side_effect=commit_error)
        self.rollback = AsyncMock()

    def in_transaction(self):
        return self._in_transaction


@pytest.mark.asyncio
async def test_read_only_transaction_is_committed_to_free_the_connection():
    session = FakeSession()

    assert await release_idle_connection(session=session) is True
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("session", [FakeSession(wrote=True), FakeSession(pending=True)], ids=["flushed", "pending"])
async def test_transaction_with_writes_keeps_its_connection(session):
    assert await release_idle_connection(session=session) is False
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_nothing_to_release_without_a_transaction():
    session = FakeSession(in_transaction=False)

    assert await release_idle_connection(session=session) is False
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_release_rolls_back_and_lets_the_turn_continue():
    session = FakeSession(commit_error=ConnectionResetError("connection lost"))

    assert await release_idle_connection(session=session) is False
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_request_session_is_not_an_error(monkeypatch):
    def no_scope(_):
        raise RuntimeError("outside a request scope")

    monkeypatch.setattr(db_connection_utils.injector, "get", no_scope)

    assert await release_idle_connection(context="test") is False
