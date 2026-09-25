"""Unit tests for the internal agent execute route used by the voice bridge"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.routes import internal
from app.auth.dependencies import expose_request_to_turn_gate
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
@pytest.mark.parametrize(
    "error_key, status_code",
    [(ErrorKey.CHAT_TURN_CAPACITY_EXCEEDED, 503), (ErrorKey.CHAT_TURN_CLIENT_DISCONNECTED, 499)],
)
async def test_turn_rejections_keep_their_status(route, monkeypatch, error_key, status_code):
    rejection = AppException(error_key=error_key, status_code=status_code)
    monkeypatch.setattr(route, "RegistryItem", _registry_item_raising(rejection))

    with pytest.raises(AppException) as raised:
        await route.execute_agent(_body(), _secret="x", agent_service=FakeAgentService())

    assert raised.value.status_code == status_code


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


def test_route_exposes_its_request_to_the_turn_gate():
    route = next(r for r in internal.router.routes if getattr(r, "path", None) == "/agents/execute")

    assert any(dep.call is expose_request_to_turn_gate for dep in route.dependant.dependencies)
