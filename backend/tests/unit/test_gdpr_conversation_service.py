"""Unit tests for ``ConversationService.gdpr_delete_conversation``.

These tests exercise the three GDPR delete modes (``soft``, ``anonymize``,
``hard``) against a mocked ``ConversationRepository`` so they can run fast
without a database. The goal is to validate:

- the right repository operations are called,
- the PII namespace inside ``custom_attributes`` is scrubbed in soft/anonymize,
- ``pii_redacted_at`` is stamped only in anonymize,
- transcript message text is redacted only in anonymize,
- the service raises ``CONVERSATION_NOT_FOUND`` if the conversation is missing.

Email-search filter behavior at the repository level is covered by an
integration-style assertion that constructs a ``ConversationFilter`` with the
new ``email`` parameter and verifies the schema accepts it; the actual JSONB
SQL is exercised by full-stack tests when a Postgres database is available.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.gdpr_delete_mode_enum import GdprDeleteMode
from app.repositories.conversations import ConversationRepository
from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.filter import ConversationFilter
from app.services.conversations import ConversationService


def _build_service(conversation_repo, transcript_repo=None):
    """Construct a ``ConversationService`` with mocked collaborators.

    The service has several collaborators that are unrelated to the GDPR path
    (operator stats, KPI analyzer, conversation analysis service, llm
    analyst service). They're stubbed with ``MagicMock`` because the GDPR
    code path never touches them.
    """
    return ConversationService(
        operator_statistics_service=MagicMock(),
        conversation_repo=conversation_repo,
        transcript_message_repo=transcript_repo or AsyncMock(spec=TranscriptMessageRepository),
        gpt_kpi_analyzer_service=MagicMock(),
        conversation_analysis_service=MagicMock(),
        llm_analyst_service=MagicMock(),
    )


def _build_conversation(*, with_messages=False, custom_attributes=None):
    conversation = MagicMock()
    conversation.id = uuid4()
    conversation.is_deleted = 0
    conversation.custom_attributes = custom_attributes or {
        "region": "EU",
        "pii": {
            "requester_email": "user@example.com",
            "requester_name": "User Example",
        },
    }
    conversation.pii_redacted_at = None
    conversation.feedback = "user@example.com left a complaint"
    conversation.negative_reason = None
    if with_messages:
        msg1 = MagicMock()
        msg1.text = "Please contact me at user@example.com or call 555-123-4567."
        msg2 = MagicMock()
        msg2.text = "Thanks, your SSN 123-45-6789 has been received."
        conversation.messages = [msg1, msg2]
    else:
        conversation.messages = []
    return conversation


@pytest.fixture
def mock_repository():
    repo = AsyncMock(spec=ConversationRepository)
    return repo


@pytest.mark.asyncio
async def test_gdpr_delete_conversation_not_found_raises(mock_repository):
    mock_repository.fetch_conversation_by_id.return_value = None
    service = _build_service(mock_repository)

    with pytest.raises(AppException) as exc_info:
        await service.gdpr_delete_conversation(uuid4(), GdprDeleteMode.SOFT)

    assert exc_info.value.error_key == ErrorKey.CONVERSATION_NOT_FOUND


@pytest.mark.asyncio
async def test_gdpr_delete_conversation_soft_scrubs_pii_and_flags_deleted(mock_repository):
    conversation = _build_conversation()
    mock_repository.fetch_conversation_by_id.return_value = conversation
    service = _build_service(mock_repository)

    result = await service.gdpr_delete_conversation(conversation.id, GdprDeleteMode.SOFT)

    assert result["mode"] == "soft"
    assert conversation.is_deleted == 1
    assert "pii" not in (conversation.custom_attributes or {})
    assert conversation.custom_attributes == {"region": "EU"}
    mock_repository.update_conversation.assert_awaited_once_with(conversation)
    mock_repository.delete_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_gdpr_delete_conversation_anonymize_redacts_messages_and_stamps_timestamp(
    mock_repository,
):
    conversation = _build_conversation(with_messages=True)
    mock_repository.fetch_conversation_by_id.return_value = conversation
    service = _build_service(mock_repository)

    result = await service.gdpr_delete_conversation(conversation.id, GdprDeleteMode.ANONYMIZE)

    assert result["mode"] == "anonymize"
    assert conversation.is_deleted == 0
    assert "pii" not in (conversation.custom_attributes or {})
    assert conversation.pii_redacted_at is not None
    assert "user@example.com" not in conversation.feedback
    for message in conversation.messages:
        assert "user@example.com" not in message.text
        assert "123-45-6789" not in message.text
    mock_repository.update_conversation.assert_awaited_once_with(conversation)
    mock_repository.delete_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_gdpr_delete_conversation_hard_calls_repository_delete(mock_repository):
    conversation = _build_conversation()
    mock_repository.fetch_conversation_by_id.return_value = conversation
    service = _build_service(mock_repository)

    result = await service.gdpr_delete_conversation(conversation.id, GdprDeleteMode.HARD)

    assert result["mode"] == "hard"
    mock_repository.delete_conversation.assert_awaited_once_with(conversation)
    mock_repository.update_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_gdpr_delete_conversation_soft_with_no_pii_namespace_is_noop_safe(mock_repository):
    """Conversations without the ``pii`` key should still soft-delete cleanly."""
    conversation = _build_conversation(custom_attributes={"region": "EU"})
    mock_repository.fetch_conversation_by_id.return_value = conversation
    service = _build_service(mock_repository)

    result = await service.gdpr_delete_conversation(conversation.id, GdprDeleteMode.SOFT)

    assert result["mode"] == "soft"
    assert conversation.is_deleted == 1
    assert conversation.custom_attributes == {"region": "EU"}


def test_conversation_filter_accepts_email_param():
    """Smoke check that the new ``email`` filter parameter is exposed."""
    f = ConversationFilter(email="USER@example.com")
    assert f.email == "USER@example.com"


def test_conversation_filter_email_default_none():
    f = ConversationFilter()
    assert f.email is None
