"""Unit tests for tagging chat traces with the conversation id.

genassist.conversation_id lets every request of one chat be found in tracing and
matched to its log lines. A local OTel SDK tracer stands in for Datadog's
(DD_TRACE_OTEL_ENABLED=true) so no global provider is set.
"""

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider

import app.api.v1.routes  # noqa: F401
from app.api.v1.routes import conversations as routes
from app.core.observability import set_conversation_span_attribute
from app.services.conversations import ConversationService
from app.use_cases import chat_as_client_use_case as use_case

CONVERSATION_ID = UUID("0199e3a0-0000-7000-8000-0000000000c1")
AGENT_ID = UUID("0199e3a0-0000-7000-8000-0000000000a1")

_tracer = TracerProvider().get_tracer(__name__)


class _Stop(Exception):
    pass


def test_tags_current_span_with_conversation_id():
    with _tracer.start_as_current_span("fastapi.request") as span:
        set_conversation_span_attribute(CONVERSATION_ID)

    assert span.attributes["genassist.conversation_id"] == str(CONVERSATION_ID)


def test_missing_conversation_id_is_not_tagged():
    with _tracer.start_as_current_span("fastapi.request") as span:
        set_conversation_span_attribute(None)

    assert "genassist.conversation_id" not in span.attributes


@pytest.mark.asyncio
async def test_start_route_tags_span_with_new_conversation(monkeypatch):
    agent = SimpleNamespace(id=AGENT_ID, workflow_id=None, name="Support", operator_id=None)
    request = SimpleNamespace(state=SimpleNamespace(agent=agent), headers={})
    model = SimpleNamespace(recaptcha_token=None, messages=[], conversation_id=None, operator_id=None)
    service = SimpleNamespace(
        start_in_progress_conversation=AsyncMock(return_value=SimpleNamespace(id=CONVERSATION_ID))
    )
    monkeypatch.setattr(routes, "verify_recaptcha_token", lambda *a, **k: (True, 1.0, None))
    monkeypatch.setattr(routes, "AgentRead", SimpleNamespace(model_validate=lambda a: a))

    def stop_after_create(*args, **kwargs):  # first call after the conversation is created
        raise _Stop

    monkeypatch.setattr(routes, "update_conversation_started", stop_after_create)
    start = inspect.unwrap(routes.start)  # skip the rate limiter decorators

    with _tracer.start_as_current_span("fastapi.request") as span:
        with pytest.raises(_Stop):
            await start(request, model, service, None, None, None)

    assert span.attributes["genassist.conversation_id"] == str(CONVERSATION_ID)


def _connection(conversation_id):
    return SimpleNamespace(path_params={} if conversation_id is None else {"conversation_id": conversation_id})


@pytest.mark.asyncio
async def test_router_dependency_tags_conversation_from_the_url():
    with _tracer.start_as_current_span("fastapi.request") as span:
        await routes.tag_trace_with_conversation(_connection(str(CONVERSATION_ID)))

    assert span.attributes["genassist.conversation_id"] == str(CONVERSATION_ID)


@pytest.mark.parametrize("raw", [None, "not-a-uuid", "../../etc"])
@pytest.mark.asyncio
async def test_router_dependency_ignores_missing_or_malformed_ids(raw):
    with _tracer.start_as_current_span("fastapi.request") as span:
        await routes.tag_trace_with_conversation(_connection(raw))

    assert "genassist.conversation_id" not in span.attributes


def test_every_conversation_route_tags_before_its_own_dependencies():
    """The tagger is the first dependency on every route with a conversation id, websockets included."""
    with_id = [r for r in routes.router.routes if "{conversation_id}" in r.path]
    assert {"/in-progress/update/{conversation_id}", "/in-progress/finalize/{conversation_id}", "/ws/{conversation_id}"} <= {
        r.path for r in with_id
    }
    for route in with_id:
        assert route.dependant.dependencies[0].call is routes.tag_trace_with_conversation, route.path


def test_router_dependency_runs_on_the_event_loop():
    """A plain def would make FastAPI hop to its threadpool on every request to this router."""
    assert inspect.iscoroutinefunction(routes.tag_trace_with_conversation)


def test_request_rejected_by_auth_is_still_tagged():
    """Router dependencies run before the route's own (auth, agent lookup), so a 401 is tagged too."""
    spans = []
    app = FastAPI()

    @app.middleware("http")
    async def trace(request, call_next):  # stands in for ddtrace's request span
        with _tracer.start_as_current_span("fastapi.request") as span:
            spans.append(span)
            return await call_next(request)

    def reject():
        raise HTTPException(status_code=401)

    router = APIRouter(dependencies=[Depends(routes.tag_trace_with_conversation)])

    @router.patch("/in-progress/update/{conversation_id}", dependencies=[Depends(reject)])
    async def update(conversation_id: UUID):
        return {}

    app.include_router(router)
    with TestClient(app) as client:
        assert client.patch(f"/in-progress/update/{CONVERSATION_ID}").status_code == 401

    assert spans[0].attributes["genassist.conversation_id"] == str(CONVERSATION_ID)


@pytest.mark.asyncio
async def test_reply_use_case_tags_span_before_loading_the_conversation(monkeypatch):
    """Covers voice and webhook replies, which call the use case directly."""
    services = {ConversationService: SimpleNamespace(get_conversation_by_id=AsyncMock(side_effect=_Stop))}
    monkeypatch.setattr(use_case, "injector", SimpleNamespace(get=lambda cls: services.get(cls, MagicMock())))

    with _tracer.start_as_current_span("fastapi.request") as span:
        with pytest.raises(_Stop):
            await use_case.process_conversation_update_with_agent(
                CONVERSATION_ID, MagicMock(), "tenant", UUID("0199e3a0-0000-7000-8000-000000000002")
            )

    assert span.attributes["genassist.conversation_id"] == str(CONVERSATION_ID)
