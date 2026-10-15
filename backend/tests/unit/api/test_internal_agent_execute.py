"""Unit tests for the internal agent execute route used by the voice bridge"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.routes import internal
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException


class FakeAgentService:
    async def get_by_id_full(self, agent_id):
        return SimpleNamespace(id=agent_id, name="agent", workflow=None)


def _registry_item_raising(error):
    class FakeRegistryItem:
        def __init__(self, agent):
            pass

        async def execute(self, **kwargs):
            raise error

    return FakeRegistryItem


def _body():
    return SimpleNamespace(agent_id=str(uuid4()), thread_id="thread", text="hello")


@pytest.fixture
def route(monkeypatch):
    monkeypatch.setattr(internal, "verify_internal_secret", lambda secret: None)
    return internal


@pytest.mark.asyncio
async def test_unexpected_errors_still_answer_with_a_failure_body(route, monkeypatch):
    monkeypatch.setattr(route, "RegistryItem", _registry_item_raising(RuntimeError("boom")))

    reply = await route.execute_agent(_body(), _secret="x", agent_service=FakeAgentService())

    assert reply == {"success": False, "message": "boom"}


@pytest.mark.asyncio
async def test_other_application_errors_still_answer_with_a_failure_body(route, monkeypatch):
    not_found = AppException(error_key=ErrorKey.AGENT_NOT_FOUND, status_code=404)
    monkeypatch.setattr(route, "RegistryItem", _registry_item_raising(not_found))

    reply = await route.execute_agent(_body(), _secret="x", agent_service=FakeAgentService())

    assert reply == {"success": False, "message": str(not_found)}
