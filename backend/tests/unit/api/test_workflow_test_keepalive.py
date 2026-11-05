"""The Studio test routes answer at once and keep the connection busy until the run ends"""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.v1.routes.workflows as route
import app.core.keepalive_json_response as keepalive
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import init_error_handlers
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware

WORKFLOW_ID = UUID("0199e3a0-0000-7000-8000-000000000003")
TEST_BODY = {"input_data": {"message": "hi"}, "workflow": {"name": "g", "version": "1", "nodes": [], "edges": []}}
NODE_BODY = {"node_type": "pythonToolNode", "node_config": {"code": "x"}, "input_data": {}}


@pytest.fixture
def studio(monkeypatch):
    state = SimpleNamespace(calls=[], delay=0, fail=None, lookup_error=None)

    class FakeEngine:
        def __init__(self, workflow_config):
            self.workflow_id = workflow_config["id"]

        async def execute_from_node(self, **kwargs):
            state.calls.append("engine")
            await asyncio.sleep(state.delay)
            if state.fail:
                raise state.fail
            return SimpleNamespace(format_state_as_response=lambda: {"status": "completed"})

    class FakeTurnRouter:
        def __init__(self, engine, owner_id):
            pass

        def has_sub_agents(self):
            return False

        def finalize(self, response):
            return response

    class FakeWorkflowService:
        async def get_by_id(self, workflow_id):
            raise state.lookup_error

    @asynccontextmanager
    async def scope():
        state.calls.append("scope-enter")
        yield
        state.calls.append("scope-exit")

    async def remember(request):
        state.calls.append("remember")

    monkeypatch.setattr(route, "WorkflowEngine", FakeEngine)
    monkeypatch.setattr(route, "SubAgentTurnRouter", FakeTurnRouter)
    monkeypatch.setattr(keepalive, "create_tenant_request_scope", scope)
    monkeypatch.setattr(keepalive, "KEEPALIVE_SECONDS", 0.01)
    monkeypatch.setattr(ReadAfterWriteMiddleware, "remember_write", remember)

    app = FastAPI()
    init_error_handlers(app)
    app.state.injector = SimpleNamespace(get=lambda cls: FakeWorkflowService())
    app.add_api_route("/test", route.test_workflow, methods=["POST"])
    app.add_api_route("/test-node", route.test_individual_node, methods=["POST"])
    return TestClient(app), state


def test_a_long_run_answers_json_after_keepalive_bytes(studio):
    client, state = studio
    state.delay = 0.05

    response = client.post("/test", json=TEST_BODY)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text.startswith(" ")
    assert response.json() == {"status": "completed"}
    assert state.calls == ["scope-enter", "engine", "scope-exit", "remember"]


def test_an_engine_failure_after_the_start_is_a_200_envelope_with_its_text(studio):
    client, state = studio
    state.fail = RuntimeError("boom")

    response = client.post("/test", json=TEST_BODY)

    assert response.status_code == 200
    assert response.json() == {"error": "boom", "error_code": 500}
    assert state.calls == ["scope-enter", "engine"]


@pytest.mark.parametrize(
    "url, body, status, expected",
    [
        ("/test", {}, 400, {"detail": "Input message is required"}),
        (f"/test?workflow_id={WORKFLOW_ID}", {"input_data": {"message": "hi"}}, 404, "WORKFLOW_NOT_FOUND"),
        ("/test-node", {**NODE_BODY, "node_type": "nope"}, 400, None),
    ],
)
def test_pre_stream_refusals_keep_their_status(studio, url, body, status, expected):
    client, state = studio
    state.lookup_error = AppException(ErrorKey.WORKFLOW_NOT_FOUND, 404)

    response = client.post(url, json=body)

    assert response.status_code == status
    if isinstance(expected, dict):
        assert response.json() == expected
    elif expected:
        assert response.json()["error_key"] == expected
    assert state.calls == []


def test_a_node_test_failure_after_the_start_is_a_200_envelope(studio):
    client, state = studio
    state.fail = ValueError("bad config")

    response = client.post("/test-node", json=NODE_BODY)

    assert response.status_code == 200
    assert response.json() == {"error": "bad config", "error_code": 500}
    assert state.calls == ["scope-enter", "engine"]
