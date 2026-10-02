"""Unit tests for filling a missing conversation topic from the saved analysis, without a database"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import app.services.conversations as conversations_module
from app.db.models.conversation import ConversationAnalysisModel
from app.services.conversations import ConversationService


def _analysis(topic="Billing Questions"):
    return ConversationAnalysisModel(
        conversation_id=uuid4(), topic=topic, summary="", negative_sentiment=0, positive_sentiment=0,
        neutral_sentiment=0, tone="", customer_satisfaction=0, operator_knowledge=0, resolution_rate=0,
        llm_analyst_id=uuid4(), efficiency=0, response_time=0, quality_of_service=0)


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setattr(conversations_module, "invalidate_conversation_cache", AsyncMock())

    conversation = SimpleNamespace(id=uuid4(), status="in_progress", in_progress_hostility_score=0,
                                   operator_id=uuid4(), duration=0, zendesk_ticket_id=None, updated_at=None,
                                   topic=None)
    conversation_repo = AsyncMock()
    conversation_repo.fetch_conversation_by_id.return_value = conversation
    conversation_repo.update_conversation.side_effect = lambda conv: conv
    analysis_service = AsyncMock()
    analysis_service.create_conversation_analysis.return_value = _analysis()

    service = ConversationService(
        operator_statistics_service=AsyncMock(),
        conversation_repo=conversation_repo,
        conversation_read_repo=AsyncMock(),
        transcript_message_repo=AsyncMock(),
        audit_log_repo=AsyncMock(),
        recordings_repo=AsyncMock(),
        conversation_read_receipt_repo=AsyncMock(),
        thread_rag=AsyncMock(),
        gpt_kpi_analyzer_service=MagicMock(),
        conversation_analysis_service=analysis_service,
        llm_analyst_service=MagicMock(),
    )
    service._analyze_transcript = AsyncMock(return_value=MagicMock())
    return SimpleNamespace(service=service, conversation=conversation, conversation_repo=conversation_repo,
                           analysis_service=analysis_service)


@pytest.mark.asyncio
async def test_finalize_fills_the_topic_from_the_analysis(harness):
    await harness.service.finalize_in_progress_conversation(harness.conversation.id)

    harness.conversation_repo.fill_topic_if_missing.assert_awaited_once_with(harness.conversation.id,
                                                                            "Billing Questions")
    harness.conversation_repo.update_conversation.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_skips_the_fill_when_the_analysis_has_no_topic(harness):
    harness.analysis_service.create_conversation_analysis.return_value = _analysis(topic="")

    await harness.service.finalize_in_progress_conversation(harness.conversation.id)

    harness.conversation_repo.fill_topic_if_missing.assert_not_awaited()


@pytest.mark.asyncio
async def test_re_analyze_fills_the_topic_from_the_analysis(harness):
    harness.analysis_service.get_by_conversation_id.return_value = None

    await harness.service.re_analyze_conversation(harness.conversation.id)

    harness.conversation_repo.fill_topic_if_missing.assert_awaited_once_with(harness.conversation.id,
                                                                            "Billing Questions")
    harness.conversation_repo.update_conversation.assert_not_awaited()
