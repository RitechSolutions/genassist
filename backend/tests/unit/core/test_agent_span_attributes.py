"""Unit tests for tagging chat traces with the agent and workflow.

The chat endpoints find the agent from the API key, so traces only tell agents apart
through the genassist.agent_id / genassist.workflow_id attributes. A local OTel SDK
tracer stands in for Datadog's (DD_TRACE_OTEL_ENABLED=true) so no global provider is set.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import inspect

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider

import app.api.v1.routes  # noqa: F401
from app.api.v1.routes import conversations as routes
from app.core.exceptions.exception_classes import AppException
from app.core.config.settings import settings
from app.core.observability import datadog_observability
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.schemas.conversation import AgentMinimalForCache, ConversationWithOperatorAgentRead
from app.schemas.conversation_transcript import InProgConvTranscrUpdate
from app.services.agent_config import AgentConfigService
from app.services.conversations import ConversationService
from app.use_cases import chat_as_client_use_case as use_case

AGENT_ID = UUID("0199e3a0-0000-7000-8000-0000000000a1")
WORKFLOW_ID = UUID("0199e3a0-0000-7000-8000-0000000000b1")

_tracer = TracerProvider().get_tracer(__name__)


@pytest.fixture(autouse=True)
def _datadog_on(monkeypatch):
    """The tags are part of the Datadog integration, which is off unless DATADOG_ENABLED."""
    monkeypatch.setattr(settings, "DATADOG_ENABLED", True)


def test_tags_current_span_with_agent_and_workflow():
    with _tracer.start_as_current_span("fastapi.request") as span:
        datadog_observability.tag_agent(AGENT_ID, WORKFLOW_ID)

    assert span.attributes["genassist.agent_id"] == str(AGENT_ID)
    assert span.attributes["genassist.workflow_id"] == str(WORKFLOW_ID)


def test_agent_without_workflow_only_tags_agent():
    with _tracer.start_as_current_span("fastapi.request") as span:
        datadog_observability.tag_agent(AGENT_ID, None)

    assert span.attributes["genassist.agent_id"] == str(AGENT_ID)
    assert "genassist.workflow_id" not in span.attributes


def test_no_active_span_is_a_no_op():
    # Outside any span (or with tracing off) the OTel API returns a no-op span.
    assert not otel_trace.get_current_span().is_recording()
    datadog_observability.tag_agent(AGENT_ID, WORKFLOW_ID)
    assert not otel_trace.get_current_span().is_recording()


class _AgentRan(Exception):
    pass


@pytest.mark.asyncio
async def test_chat_reply_tags_span_with_agent_and_workflow(monkeypatch):
    agent = SimpleNamespace(id=AGENT_ID, workflow_id=WORKFLOW_ID, workflow=None)
    conversation = SimpleNamespace(status=ConversationStatus.IN_PROGRESS.value)
    services = {
        ConversationService: SimpleNamespace(get_conversation_by_id=AsyncMock(return_value=conversation)),
        AgentConfigService: SimpleNamespace(get_by_user_id=AsyncMock(return_value=agent)),
    }

    async def run_agent(*args, **kwargs):
        raise _AgentRan

    monkeypatch.setattr(use_case, "injector", SimpleNamespace(get=lambda cls: services.get(cls, MagicMock())))
    monkeypatch.setattr(use_case, "send_message_to_socket", AsyncMock())
    monkeypatch.setattr(use_case, "release_idle_connection", AsyncMock())
    monkeypatch.setattr(use_case, "run_query_agent_logic", run_agent)
    monkeypatch.setattr(use_case._pii_redactor, "redact", lambda text: text)
    update = InProgConvTranscrUpdate(messages=[{"start_time": 0, "end_time": 0, "speaker": "customer", "text": "hi"}])

    with _tracer.start_as_current_span("fastapi.request") as span:
        with pytest.raises(_AgentRan):
            await use_case.process_conversation_update_with_agent(
                UUID("0199e3a0-0000-7000-8000-000000000001"), update, "tenant", UUID("0199e3a0-0000-7000-8000-000000000002")
            )

    assert span.attributes["genassist.agent_id"] == str(AGENT_ID)
    assert span.attributes["genassist.workflow_id"] == str(WORKFLOW_ID)


def _agent_request(agent=None):
    if agent is None:
        agent = SimpleNamespace(id=AGENT_ID, workflow_id=WORKFLOW_ID, name="Support", operator_id=None)
    return SimpleNamespace(state=SimpleNamespace(agent=agent), headers={})


def _cached_agent():
    """The agent the reply route really gets: the cached conversation's operator agent."""
    orm_conversation = SimpleNamespace(
        id=UUID("0199e3a0-0000-7000-8000-000000000001"),
        operator_id=UUID("0199e3a0-0000-7000-8000-000000000003"),
        operator=SimpleNamespace(
            id=UUID("0199e3a0-0000-7000-8000-000000000003"),
            agent=SimpleNamespace(
                id=AGENT_ID, name="Support", is_active=True, workflow_id=WORKFLOW_ID, security_settings=None
            ),
        ),
    )
    return ConversationWithOperatorAgentRead.model_validate(orm_conversation).operator.agent


@pytest.mark.asyncio
async def test_start_route_tags_span_before_validation(monkeypatch):
    """A start rejected by reCAPTCHA is still counted under its agent."""
    tagged = []
    monkeypatch.setattr(routes.datadog_observability, "tag_agent", lambda *ids: tagged.append(ids))
    monkeypatch.setattr(routes, "verify_recaptcha_token", lambda *a, **k: (False, 0.0, "bad token"))
    start = inspect.unwrap(routes.start)  # skip the rate limiter decorators

    with pytest.raises(AppException):
        await start(_agent_request(), SimpleNamespace(recaptcha_token="t"), None, None, None, None)

    assert tagged == [(AGENT_ID, WORKFLOW_ID)]


@pytest.mark.asyncio
async def test_reply_route_tags_span_before_reading_the_body(monkeypatch):
    """A reply that fails validation is still counted under its agent."""
    tagged = []
    monkeypatch.setattr(routes.datadog_observability, "tag_agent", lambda *ids: tagged.append(ids))
    request = _agent_request(_cached_agent())

    async def bad_body():
        raise ValueError("invalid JSON")

    request.json = bad_body
    update = inspect.unwrap(routes.update)

    with pytest.raises(ValueError):
        await update(request, UUID("0199e3a0-0000-7000-8000-000000000001"))

    assert tagged == [(AGENT_ID, WORKFLOW_ID)]


@pytest.mark.asyncio
async def test_reply_route_handles_agent_cached_before_workflow_id_existed(monkeypatch):
    """Entries pickled before the deploy have no workflow_id; the reply must still go through."""
    tagged = []
    monkeypatch.setattr(routes.datadog_observability, "tag_agent", lambda *ids: tagged.append(ids))
    agent = AgentMinimalForCache(id=AGENT_ID, name="Support")
    del agent.__dict__["workflow_id"]  # what unpickling an old cache entry gives
    request = _agent_request(agent)

    async def bad_body():
        raise ValueError("invalid JSON")

    request.json = bad_body
    update = inspect.unwrap(routes.update)

    with pytest.raises(ValueError):
        await update(request, UUID("0199e3a0-0000-7000-8000-000000000001"))

    assert tagged == [(AGENT_ID, None)]
