"""Unit tests for the streamed (SSE) branch of the in-progress conversation update route"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.api.v1.routes import conversations as route
from app.core import turn_stream, turn_stream_response
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.middlewares.rate_limit_middleware import limiter
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware

CONVERSATION_ID = UUID("0199e3a0-0000-7000-8000-000000000001")
OPERATOR_ID = UUID("0199e3a0-0000-7000-8000-000000000002")
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
URL = f"/update/{CONVERSATION_ID}"
BODY = {"messages": []}
STREAM = {"Accept": "text/event-stream"}


def _saved_conversation():
    return SimpleNamespace(
        id=CONVERSATION_ID,
        operator_id=OPERATOR_ID,
        recording_id=None,
        conversation_date=NOW,
        created_at=NOW,
        updated_at=NOW,
        status="in_progress",
    )


@pytest.fixture
def turn(monkeypatch):
    state = SimpleNamespace(calls=[], fail=None, finished=False)

    async def attachments(**kwargs):
        state.calls.append("attachments")

    async def run(**kwargs):
        state.calls.append("turn")
        turn_stream.emit_activity("knowledge", "start")
        await asyncio.sleep(0.05)
        if state.fail:
            raise state.fail
        state.finished = True
        return _saved_conversation()

    async def invalidate(*args):
        state.calls.append("invalidate")

    @asynccontextmanager
    async def scope():
        state.calls.append("scope-enter")
        yield
        state.calls.append("scope-exit")

    async def remember(request):
        state.calls.append("remember")

    monkeypatch.setattr(route, "process_attachments_from_metadata", attachments)
    monkeypatch.setattr(route, "process_conversation_update_with_agent", run)
    monkeypatch.setattr(route, "invalidate_cache", invalidate)
    monkeypatch.setattr(turn_stream_response, "create_tenant_request_scope", scope)
    monkeypatch.setattr(ReadAfterWriteMiddleware, "remember_write", remember)
    monkeypatch.setattr(route, "injector", SimpleNamespace(get=lambda cls: None))
    monkeypatch.setattr(route, "verify_recaptcha_token", lambda token, agent=None: (True, 1.0, ""))
    monkeypatch.setattr(route, "get_current_user_id", lambda: None)
    monkeypatch.setattr(limiter, "enabled", False)

    async def with_agent(request: Request):
        request.state.agent = SimpleNamespace(security_settings=None)

    app = FastAPI()
    app.add_api_route("/update/{conversation_id}", route.update, methods=["PATCH"], dependencies=[Depends(with_agent)])
    return app, state


def _events(response):
    events = []
    for block in response.text.split("\n\n"):
        if block:
            name, data = block.split("\n")
            events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def test_without_accept_header_the_route_answers_json_in_the_request_scope(turn):
    app, state = turn

    response = TestClient(app).patch(URL, json=BODY)

    assert response.headers["content-type"] == "application/json"
    assert response.json()["id"] == str(CONVERSATION_ID)
    assert state.calls == ["attachments", "turn", "invalidate"]


def test_streamed_turn_runs_in_its_own_scope_and_done_carries_the_json_body(turn):
    app, state = turn
    client = TestClient(app)

    response = client.patch(URL, json=BODY, headers=STREAM)

    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert state.calls == ["scope-enter", "attachments", "turn", "invalidate", "scope-exit", "remember"]
    events = _events(response)
    assert [name for name, _ in events] == ["activity", "done"]
    assert events[0][1] == {"kind": "knowledge", "phase": "start"}
    assert events[1][1]["conversation"]["id"] == str(CONVERSATION_ID)
    assert events[1][1]["conversation"] == client.patch(URL, json=BODY).json()


def test_failed_streamed_turn_sends_the_error_envelope_and_does_not_pin(turn):
    app, state = turn
    state.fail = AppException(ErrorKey.CONVERSATION_FINALIZED)

    response = TestClient(app).patch(URL, json=BODY, headers=STREAM)

    assert response.status_code == 200
    assert _events(response)[-1] == (
        "error",
        {
            "error": "Conversation already finalized.",
            "error_code": 400,
            "error_key": "CONVERSATION_FINALIZED",
            "error_detail": None,
        },
    )
    assert state.calls == ["scope-enter", "attachments", "turn"]


def test_unexpected_failure_sends_a_generic_error_without_its_message(turn):
    app, state = turn
    state.fail = RuntimeError("password=hunter2")

    response = TestClient(app).patch(URL, json=BODY, headers=STREAM)

    assert _events(response)[-1] == (
        "error",
        {"error": "An internal server error occurred. Please try again later.", "error_code": 500},
    )


@pytest.mark.asyncio
async def test_request_stays_open_until_the_turn_ends_after_a_disconnect(turn):
    app, state = turn
    pending = [{"type": "http.request", "body": json.dumps(BODY).encode(), "more_body": False}]
    sent = []

    async def receive():
        return pending.pop(0) if pending else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "PATCH",
        "scheme": "http",
        "path": URL,
        "raw_path": URL.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"accept", b"text/event-stream"), (b"content-type", b"application/json")],
        "server": ("test", 80),
        "client": ("test", 1234),
    }

    await app(scope, receive, send)

    assert state.finished is True
    assert state.calls[-1] == "remember"
    assert b"event: done" not in b"".join(message.get("body", b"") for message in sent)
