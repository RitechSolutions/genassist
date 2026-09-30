"""Unit tests for the in-progress hostility gate and its message window, without a database"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import app.services.conversations as conversations_module
from app.core.config.settings import settings
from app.core.utils.transcript_utils import CONVERSATIONAL_MESSAGE_TYPES
from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.conversation_transcript import InProgConvTranscrUpdate, TranscriptSegmentInput
from app.services.conversations import ConversationService

STORED = {"in_progress_hostility_score": 30, "topic": "Billing Questions", "negative_reason": "Other"}


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setattr(conversations_module, "get_current_user_id", lambda: None)
    monkeypatch.setattr(conversations_module, "null_unloaded_attributes", lambda obj: None)
    monkeypatch.setattr("app.core.utils.db_connection_utils.release_idle_connection", AsyncMock())

    conversation = SimpleNamespace(id=uuid4(), status="in_progress", word_count=0, agent_ratio=0,
                                   customer_ratio=0, duration=0, updated_by=None, **STORED)
    conversation_repo = AsyncMock()
    conversation_repo.fetch_conversation_by_id.return_value = conversation
    conversation_repo.update_conversation.side_effect = lambda conv: conv
    conversation_repo.fetch_conversation_by_id_with_operator_agent.return_value = SimpleNamespace(agent_id=uuid4())

    message_repo = AsyncMock()
    message_repo.get_message_count.return_value = 2
    message_repo.get_latest_messages_by_types.return_value = [
        SimpleNamespace(speaker="customer", text="hi", create_time=None),
        SimpleNamespace(speaker="agent", text="hello", create_time=None),
    ]

    analyst_service = AsyncMock()
    analyst_service.get_by_id.return_value = SimpleNamespace(is_active=True)
    analyzer = MagicMock()
    analyzer.partial_hostility_analysis = AsyncMock(
        return_value={"hostile_score": 72, "topic": "Complaints", "negative_reason": "Bad Communication"})

    service = ConversationService(
        operator_statistics_service=MagicMock(),
        conversation_repo=conversation_repo,
        conversation_read_repo=AsyncMock(),
        transcript_message_repo=message_repo,
        audit_log_repo=AsyncMock(),
        recordings_repo=AsyncMock(),
        conversation_read_receipt_repo=AsyncMock(),
        thread_rag=AsyncMock(),
        gpt_kpi_analyzer_service=analyzer,
        conversation_analysis_service=MagicMock(),
        llm_analyst_service=analyst_service,
    )
    return SimpleNamespace(service=service, conversation=conversation, conversation_repo=conversation_repo,
                           message_repo=message_repo, analyst_service=analyst_service,
                           analyze=analyzer.partial_hostility_analysis)


async def _send(h, *segments):
    update = InProgConvTranscrUpdate(messages=[
        TranscriptSegmentInput(start_time=0, end_time=0, speaker=speaker, text=text, type=type)
        for speaker, text, type in segments
    ])
    await h.service.update_in_progress_conversation(h.conversation.id, update)


def _stored(conversation):
    return {key: getattr(conversation, key) for key in STORED}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "segments, scored",
    [
        ([("customer", "this is ridiculous", "message"), ("agent", "sorry about that", "message")], True),
        ([("agent", "Hi! How can I help?", "message")], False),
    ],
    ids=["customer-turn", "agent-only"],
)
async def test_only_turns_with_new_customer_text_are_scored(harness, segments, scored):
    await _send(harness, *segments)

    assert harness.analyze.await_count == int(scored)
    assert harness.message_repo.get_latest_messages_by_types.await_count == int(scored)
    if not scored:
        assert _stored(harness.conversation) == STORED


@pytest.mark.asyncio
async def test_a_scored_turn_sends_the_window_as_lines_and_stores_the_result(harness):
    await _send(harness, ("customer", "hi", "message"))

    harness.message_repo.get_latest_messages_by_types.assert_awaited_once_with(
        harness.conversation.id, CONVERSATIONAL_MESSAGE_TYPES, settings.HOSTILITY_SCORE_MESSAGE_COUNT)
    assert harness.analyze.await_args.args[0] == "customer: hi\nagent: hello"
    assert _stored(harness.conversation) == {
        "in_progress_hostility_score": 72, "topic": "Complaints", "negative_reason": "Bad Communication"}


@pytest.mark.asyncio
async def test_a_failed_analysis_keeps_the_stored_score(harness):
    harness.analyze.return_value = None

    await _send(harness, ("customer", "hi", "message"))

    harness.analyze.assert_awaited_once()
    assert _stored(harness.conversation) == STORED
    harness.conversation_repo.update_conversation.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("analyst", [None, SimpleNamespace(is_active=False)], ids=["missing", "inactive"])
async def test_a_missing_or_inactive_analyst_skips_scoring(harness, analyst):
    harness.analyst_service.get_by_id.return_value = analyst

    await _send(harness, ("customer", "hi", "message"))

    harness.message_repo.get_latest_messages_by_types.assert_not_awaited()
    harness.analyze.assert_not_awaited()
    assert _stored(harness.conversation) == STORED


@pytest.mark.asyncio
async def test_an_empty_window_skips_the_call(harness):
    harness.message_repo.get_latest_messages_by_types.return_value = []

    await _send(harness, ("customer", "hi", "message"))

    harness.analyze.assert_not_awaited()
    assert _stored(harness.conversation) == STORED


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_window_query_returns_the_latest_rows_oldest_first_without_audio_blobs():
    result = MagicMock()
    result.scalars.return_value.all.return_value = ["third", "second", "first"]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    repo = TranscriptMessageRepository(db)

    rows = await repo.get_latest_messages_by_types(uuid4(), CONVERSATIONAL_MESSAGE_TYPES, 20)
    await repo.get_latest_messages_by_types(uuid4(), CONVERSATIONAL_MESSAGE_TYPES, 0)

    assert rows == ["first", "second", "third"]
    limited, unlimited = (_sql(call.args[0]) for call in db.execute.await_args_list)
    assert "transcript_messages.type IN (" in limited and "'message'" in limited and "'audio'" in limited
    assert "audio_data" not in limited
    assert "ORDER BY transcript_messages.sequence_number DESC" in limited
    assert limited.endswith("LIMIT 20")
    assert "LIMIT" not in unlimited
