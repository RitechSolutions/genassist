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
import app.modules.workflow.test_runs as test_runs
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import init_error_handlers
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware

WORKFLOW_ID = UUID("0199e3a0-0000-7000-8000-000000000003")
TEST_BODY = {"input_data": {"message": "hi"}, "workflow": {"name": "g", "version": "1", "nodes": [], "edges": []}}
NODE_BODY = {"node_type": "pythonToolNode", "node_config": {"code": "x"}, "input_data": {}}
KEEPALIVE = {"X-Keepalive": "1"}


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
    # The /test route runs the turn through run_workflow_test, which builds the router.
    monkeypatch.setattr(test_runs, "SubAgentTurnRouter", FakeTurnRouter)
    monkeypatch.setattr(keepalive, "create_tenant_request_scope", scope)
    monkeypatch.setattr(keepalive, "KEEPALIVE_SECONDS", 0.01)
    monkeypatch.setattr(ReadAfterWriteMiddleware, "remember_write", remember)

    app = FastAPI()
    init_error_handlers(app)
    app.state.injector = SimpleNamespace(get=lambda cls: FakeWorkflowService())
    app.add_api_route("/test", route.test_workflow, methods=["POST"])
    app.add_api_route("/test-node", route.test_individual_node, methods=["POST"])
    return TestClient(app, headers=KEEPALIVE), state


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


@pytest.mark.parametrize("url, body", [("/test", TEST_BODY), ("/test-node", NODE_BODY)])
def test_without_the_keepalive_header_a_run_failure_keeps_its_error_status(studio, url, body):
    client, state = studio
    client.headers.pop("X-Keepalive")
    state.fail = RuntimeError("boom")

    response = client.post(url, json=body)

    assert response.status_code == 500
    assert response.json() == {"detail": "boom"}


def test_without_the_keepalive_header_a_run_answers_plain_json(studio):
    client, state = studio
    client.headers.pop("X-Keepalive")

    response = client.post("/test", json=TEST_BODY)

    assert response.status_code == 200
    assert response.text == '{"status":"completed"}'
    assert state.calls == ["engine"]


# WB-3 (68392): a queued training job reaches the Studio through keepalive

QUEUED_JOB = {
    "job_id": "job-1",
    "status": "queued",
    "kind": "node",
    "progress": {"stage": "queued"},
    "result": None,
    "error": None,
}
TRAIN_NODE_BODY = {"node_type": "trainModelNode", "node_config": {"name": "Train Model"}, "input_data": {}}
TRAIN_WORKFLOW_BODY = {
    "input_data": {"message": "hi"},
    "workflow": {
        "name": "g",
        "version": "1",
        "nodes": [
            {"id": "in", "type": "chatInputNode", "data": {}},
            {"id": "train", "type": "trainModelNode", "data": {"name": "Train Model"}},
        ],
        "edges": [{"id": "e", "source": "in", "target": "train"}],
    },
}


@pytest.fixture
def queued_training(monkeypatch, studio):
    client, state = studio

    async def queue(kind, training_nodes, payload):
        state.calls.append(f"queued-{kind}")
        return {**QUEUED_JOB, "kind": kind}

    monkeypatch.setattr(route, "_queue_training_job", queue)
    return client, state


@pytest.mark.parametrize(
    "url, body, kind",
    [("/test-node", TRAIN_NODE_BODY, "node"), ("/test", TRAIN_WORKFLOW_BODY, "workflow")],
)
def test_a_queued_training_job_arrives_as_the_job_through_keepalive(queued_training, url, body, kind):
    client, state = queued_training

    response = client.post(url, json=body)

    assert response.status_code == 200
    data = response.json()
    # The job itself, as the Studio's isTrainingJob expects - never a Response's attributes.
    assert data == {**QUEUED_JOB, "kind": kind}
    assert not {"status_code", "body", "raw_headers", "background"} & set(data)
    assert f"queued-{kind}" in state.calls


@pytest.mark.parametrize(
    "url, body, kind",
    [("/test-node", TRAIN_NODE_BODY, "node"), ("/test", TRAIN_WORKFLOW_BODY, "workflow")],
)
def test_without_the_keepalive_header_a_queued_job_is_still_a_202(queued_training, url, body, kind):
    client, _ = queued_training
    client.headers.pop("X-Keepalive")

    response = client.post(url, json=body)

    assert response.status_code == 202
    assert response.json() == {**QUEUED_JOB, "kind": kind}


@pytest.mark.parametrize("keepalive", [True, False])
def test_a_second_training_test_is_refused_with_409(studio, monkeypatch, keepalive):
    client, _ = studio
    if not keepalive:
        client.headers.pop("X-Keepalive")

    async def queue(kind, training_nodes, payload):
        raise AppException(ErrorKey.ML_TRAINING_JOB_ALREADY_RUNNING, 409, "You already have a training test running.")

    monkeypatch.setattr(route, "_queue_training_job", queue)

    response = client.post("/test-node", json=TRAIN_NODE_BODY)

    if keepalive:
        # The stream has started, so the refusal is the error envelope the Studio turns into an error.
        assert response.status_code == 200
        assert response.json()["error_code"] == 409
        assert response.json()["error_key"] == "ML_TRAINING_JOB_ALREADY_RUNNING"
    else:
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_queue_training_job_returns_the_job_not_a_response(monkeypatch):
    class Store:
        async def start(self, tenant_id, owner, kind):
            return {"job_id": "job-9", "status": "queued", "kind": kind, "user_id": owner, "heartbeat": 9e12, "progress": {}}, None

    queued = []
    monkeypatch.setattr(route, "_training_job_store", lambda: Store())
    monkeypatch.setattr(route, "_training_job_owner", lambda: "user-1")
    monkeypatch.setattr(route, "get_tenant_context", lambda: "master")
    monkeypatch.setattr(route.training_jobs, "check_training_config", lambda node: None)
    import app.tasks.ml_training_job_tasks as tasks

    monkeypatch.setattr(tasks.run_training_job_task, "delay", lambda *args: queued.append(args))

    job = await route._queue_training_job("node", [{}], {"workflow_config": {}})

    assert isinstance(job, dict)
    assert job["job_id"] == "job-9" and job["status"] == "queued"
    assert "user_id" not in job and "heartbeat" not in job  # the public view
    assert queued and queued[0][0] == "job-9"


def _real_queue(monkeypatch, queued):
    """The real _queue_training_job, with the job store and the Celery task replaced."""

    class Store:
        async def start(self, tenant_id, owner, kind):
            job = {"job_id": "job-7", "status": "queued", "kind": kind, "user_id": owner, "heartbeat": 9e12,
                   "progress": {"stage": "queued"}, "result": None, "error": None,
                   "created_at": 1.0, "updated_at": 1.0}
            return job, None

    monkeypatch.setattr(route, "_training_job_store", lambda: Store())
    monkeypatch.setattr(route, "_training_job_owner", lambda: "user-1")
    monkeypatch.setattr(route, "get_tenant_context", lambda: "master")
    monkeypatch.setattr(route.training_jobs, "check_training_config", lambda node: None)
    import app.tasks.ml_training_job_tasks as tasks

    monkeypatch.setattr(tasks.run_training_job_task, "delay", lambda *args: queued.append(args))


@pytest.mark.parametrize("keepalive, status", [(True, 200), (False, 202)])
def test_the_real_queued_job_reaches_the_client_whole(studio, monkeypatch, keepalive, status):
    client, _ = studio
    if not keepalive:
        client.headers.pop("X-Keepalive")
    queued = []
    _real_queue(monkeypatch, queued)

    response = client.post("/test-node", json=TRAIN_NODE_BODY)

    assert response.status_code == status
    job = response.json()
    assert job["job_id"] == "job-7" and job["status"] == "queued" and job["progress"]
    assert "user_id" not in job and "heartbeat" not in job
    assert not {"status_code", "body", "raw_headers", "background"} & set(job)
    assert queued and queued[0][0] == "job-7"


def test_a_response_returned_through_keepalive_is_a_clear_error_not_its_attributes(studio, monkeypatch):
    from fastapi.responses import JSONResponse

    client, _ = studio

    async def queue(kind, training_nodes, payload):
        return JSONResponse(status_code=202, content=QUEUED_JOB)

    monkeypatch.setattr(route, "_queue_training_job", queue)

    response = client.post("/test-node", json=TRAIN_NODE_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["error_code"] == 500
    assert "raw_headers" not in response.text
