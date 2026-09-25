"""Unit tests: a queued agent turn frees its idle connection, an immediate one does not touch it"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.chat_turn_gate import ChatTurnGate
from app.core.exceptions.exception_classes import AppException
from app.core.utils import db_connection_utils
from app.modules.workflow import registry as registry_module
from app.modules.workflow.registry import RegistryItem


@pytest.fixture
def release_spy(monkeypatch):
    spy = AsyncMock(return_value=True)
    monkeypatch.setattr(db_connection_utils, "release_idle_connection", spy)
    return spy


@pytest.fixture
def gate(monkeypatch):
    gate = ChatTurnGate(max_inflight=1, queue_timeout_seconds=0.05)
    monkeypatch.setattr(registry_module, "chat_turn_gate", gate)
    return gate


def _item():
    return RegistryItem(SimpleNamespace(id="agent", name="Agent", workflow=None))


@pytest.mark.asyncio
async def test_queued_turn_releases_its_idle_connection(gate, release_spy):
    async with gate.slot("holder"):
        with pytest.raises(AppException) as rejected:
            await _item().execute("hello", {"thread_id": "t"})

    assert rejected.value.status_code == 503
    release_spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_immediate_turn_leaves_the_connection_alone(gate, release_spy):
    with pytest.raises(ValueError):  # no workflow assigned, raised after the gate
        await _item().execute("hello", {"thread_id": "t"})

    release_spy.assert_not_awaited()
