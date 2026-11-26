"""Phone and query API turns record fired guardrail checks with no conversation"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routes import agents as agents_route
from app.api.v1.routes import internal, twilio_agents
from app.core.utils import background_tasks
from app.schemas.agent import QueryRequest
from app.services import guardrails
from app.services.guardrails import GuardrailService

AGENT_ID = UUID("0199e3a0-0000-7000-8000-0000000000a1")
BLOCKED = {
    "stage": "input",
    "check_type": "blocked_words",
    "category": "competitorx",
    "detector": "rules",
    "score": None,
    "mode": "block",
    "action": "blocked",
    "source": None,
}


class FakeSession:
    def __init__(self):
        self.calls = []

    async def commit(self):
        self.calls.append("commit")

    async def close(self):
        self.calls.append("close")


@pytest.fixture
def store(monkeypatch):
    rows = []
    session = FakeSession()

    class Repository:
        async def add_many(self, batch):
            rows.extend(batch)

    @asynccontextmanager
    async def scope():
        yield

    def get(cls):
        return {AsyncSession: session, GuardrailService: GuardrailService(Repository())}[cls]

    monkeypatch.setattr(guardrails, "create_tenant_request_scope", scope)
    monkeypatch.setattr(guardrails, "injector", SimpleNamespace(get=get))
    return SimpleNamespace(rows=rows, session=session)


class FakeAgentService:
    async def get_by_id_full(self, agent_id):
        return SimpleNamespace(id=agent_id, is_active=True)


def _registry_item(response=None, error=None):
    class FakeRegistryItem:
        def __init__(self, agent):
            pass

        async def execute(self, **kwargs):
            if error:
                raise error
            return response

    return FakeRegistryItem


def _assert_one_blocked_row(store):
    assert [(r.agent_id, r.conversation_id, r.transcript_message_id, r.check_type, r.action) for r in store.rows] == [
        (AGENT_ID, None, None, "blocked_words", "blocked")
    ]
    assert store.session.calls == ["commit", "close"]


async def _query_agent(monkeypatch, events):
    result = {"status": "success", "response": "Sorry", "row_agent_response": {"output": "Sorry", "guardrail_events": events}}

    async def fake_run_query_agent_logic(agent_service, agent_id, session_message, metadata=None, persist=True):
        return result

    monkeypatch.setattr(agents_route, "run_query_agent_logic", fake_run_query_agent_logic)
    reply = await agents_route.query_agent(
        agent_id=AGENT_ID, thread_id="thread", request=QueryRequest(query="hi"), agent_service=object(), api_key=None
    )
    await background_tasks.drain()
    return reply, result


@pytest.mark.asyncio
async def test_query_api_turn_records_its_blocked_check(store, monkeypatch):
    reply, result = await _query_agent(monkeypatch, [BLOCKED])

    assert reply is result
    _assert_one_blocked_row(store)


@pytest.mark.asyncio
async def test_query_api_turn_with_nothing_fired_writes_nothing(store, monkeypatch):
    await _query_agent(monkeypatch, [{**BLOCKED, "action": "passed"}])

    assert store.rows == []
    assert store.session.calls == []


@pytest.mark.asyncio
async def test_shared_query_logic_writes_nothing_so_chat_turns_are_not_counted_twice(store, monkeypatch):
    monkeypatch.setattr(agents_route, "RegistryItem", _registry_item({"status": "success", "output": "Sorry", "guardrail_events": [BLOCKED]}))
    monkeypatch.setattr(agents_route, "release_idle_connection", AsyncMock())

    await agents_route.run_query_agent_logic(FakeAgentService(), str(AGENT_ID), "hi", {"thread_id": "thread"})
    await background_tasks.drain()

    assert store.rows == []


@pytest.mark.asyncio
async def test_internal_voice_turn_records_its_blocked_check(store, monkeypatch):
    monkeypatch.setattr(internal, "verify_internal_secret", lambda secret: None)
    monkeypatch.setattr(internal, "RegistryItem", _registry_item({"output": "Sorry", "guardrail_events": [BLOCKED]}))
    body = SimpleNamespace(agent_id=str(AGENT_ID), thread_id="thread", text="hi")

    reply = await internal.execute_agent(body, _secret="x", agent_service=FakeAgentService())
    await background_tasks.drain()

    assert reply == {"success": True, "message": "Sorry"}
    _assert_one_blocked_row(store)


@pytest.mark.asyncio
async def test_internal_voice_turn_that_fails_writes_nothing_and_keeps_its_failure_body(store, monkeypatch):
    monkeypatch.setattr(internal, "verify_internal_secret", lambda secret: None)
    monkeypatch.setattr(internal, "RegistryItem", _registry_item(error=RuntimeError("boom")))
    body = SimpleNamespace(agent_id=str(AGENT_ID), thread_id="thread", text="hi")

    reply = await internal.execute_agent(body, _secret="x", agent_service=FakeAgentService())
    await background_tasks.drain()

    assert reply == {"success": False, "message": "boom"}
    assert store.rows == []


@pytest.mark.asyncio
async def test_twilio_turn_records_its_blocked_check(store, monkeypatch):
    monkeypatch.setattr(twilio_agents, "RegistryItem", _registry_item({"output": "Sorry", "guardrail_events": [BLOCKED]}))

    reply = await twilio_agents.process_with_agent(
        str(AGENT_ID), "thread", "hi", agent_service=FakeAgentService()
    )
    await background_tasks.drain()

    assert reply == {"success": True, "message": "Sorry"}
    _assert_one_blocked_row(store)
