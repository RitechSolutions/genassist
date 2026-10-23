"""Unit tests for withholding streamed reply text when the agent has hidden Chat Input keys"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

import app.api.v1.routes  # noqa: F401
from app.core.turn_stream import TurnStream, current_stream
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.schemas.conversation_transcript import InProgConvTranscrUpdate
from app.services.agent_config import AgentConfigService
from app.services.conversations import ConversationService
from app.use_cases import chat_as_client_use_case as use_case

CONVERSATION_ID = UUID("0199e3a0-0000-7000-8000-000000000001")
USER_ID = UUID("0199e3a0-0000-7000-8000-000000000002")


class _AgentRan(Exception):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hidden, withheld",
    [(True, True), (False, False)],
    ids=["hidden input withholds text", "no hidden input streams text"],
)
async def test_hidden_chat_input_values_cannot_leak_through_streamed_reply_text(monkeypatch, hidden, withheld):
    agent = SimpleNamespace(
        id="agent-1",
        workflow={"nodes": [{"type": "chatInputNode", "data": {"inputSchema": {"api_key": {"hidden": hidden}}}}]},
    )
    conversation = SimpleNamespace(status=ConversationStatus.IN_PROGRESS.value)
    services = {
        ConversationService: SimpleNamespace(get_conversation_by_id=AsyncMock(return_value=conversation)),
        AgentConfigService: SimpleNamespace(get_by_user_id=AsyncMock(return_value=agent)),
    }
    stream = TurnStream(str(CONVERSATION_ID))
    sinks = []

    async def run_agent(*args, **kwargs):
        sinks.append(stream.text_sink("n1"))
        raise _AgentRan

    monkeypatch.setattr(use_case, "injector", SimpleNamespace(get=lambda cls: services.get(cls, MagicMock())))
    monkeypatch.setattr(use_case, "send_message_to_socket", AsyncMock())
    monkeypatch.setattr(use_case, "release_idle_connection", AsyncMock())
    monkeypatch.setattr(use_case, "run_query_agent_logic", run_agent)
    monkeypatch.setattr(use_case._pii_redactor, "redact", lambda text: text)
    update = InProgConvTranscrUpdate(messages=[{"start_time": 0, "end_time": 0, "speaker": "customer", "text": "hi"}])

    token = current_stream.set(stream)
    try:
        with pytest.raises(_AgentRan):
            await use_case.process_conversation_update_with_agent(CONVERSATION_ID, update, "tenant", USER_ID)
    finally:
        current_stream.reset(token)

    assert (sinks[0] is None) is withheld
