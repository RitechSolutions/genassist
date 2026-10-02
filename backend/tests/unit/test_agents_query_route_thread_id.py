import logging
from uuid import uuid4

import pytest

import app.api.v1.routes.agents as agents_route
from app.schemas.agent import QueryRequest

API_KEY = "test-api-key"


@pytest.fixture
def calls(monkeypatch):
    received = []

    async def fake_run_query_agent_logic(agent_service, agent_id, session_message, metadata=None, persist=True):
        received.append(metadata)
        return {"status": "success"}

    monkeypatch.setattr(agents_route, "run_query_agent_logic", fake_run_query_agent_logic)
    return received


async def _query(thread_id, api_key):
    return await agents_route.query_agent(
        agent_id=uuid4(),
        thread_id=thread_id,
        request=QueryRequest(query="hi"),
        agent_service=object(),
        api_key=api_key,
    )


@pytest.mark.asyncio
async def test_api_key_as_thread_id_warns_but_behaviour_is_unchanged(calls, caplog):
    with caplog.at_level(logging.WARNING, logger="app.api.v1.routes.agents"):
        response = await _query(API_KEY, API_KEY)

    assert response == {"status": "success"}
    assert calls[0]["thread_id"] == API_KEY
    assert sum("API key used as thread_id" in r.getMessage() for r in caplog.records) == 1
    assert API_KEY not in caplog.text


@pytest.mark.asyncio
async def test_distinct_thread_id_does_not_warn(calls, caplog):
    with caplog.at_level(logging.WARNING, logger="app.api.v1.routes.agents"):
        await _query(str(uuid4()), API_KEY)

    assert "API key used as thread_id" not in caplog.text


@pytest.mark.asyncio
async def test_non_ascii_thread_id_does_not_error(calls, caplog):
    with caplog.at_level(logging.WARNING, logger="app.api.v1.routes.agents"):
        await _query("thréad", API_KEY)

    assert calls[0]["thread_id"] == "thréad"
    assert "API key used as thread_id" not in caplog.text
