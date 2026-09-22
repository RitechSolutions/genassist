"""Unit tests for routing the conversation list and count queries to the read-only session"""

import typing
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.tenant_scope import clear_tenant_context, set_tenant_context
from app.db import multi_tenant_session as mts
from app.db.read_routing import allow_replica_reads, reset_replica_reads
from app.db.session_types import ReadOnlySession
from app.repositories.conversations import ConversationRepository
from app.repositories.conversations_read import ConversationReadRepository
from app.services import conversations as conversations_service_module
from app.services.conversations import ConversationService


def _build_service(read_repo):
    return ConversationService(
        operator_statistics_service=MagicMock(),
        conversation_repo=MagicMock(spec=ConversationRepository),
        conversation_read_repo=read_repo,
        transcript_message_repo=MagicMock(),
        audit_log_repo=MagicMock(),
        recordings_repo=MagicMock(),
        conversation_read_receipt_repo=MagicMock(),
        thread_rag=MagicMock(),
        gpt_kpi_analyzer_service=MagicMock(),
        conversation_analysis_service=MagicMock(),
        llm_analyst_service=MagicMock(),
    )


def _session_type_of(repository_class):
    return typing.get_type_hints(repository_class.__init__, include_extras=True)["db"]


def test_conversation_read_repository_asks_for_the_read_session():
    assert _session_type_of(ConversationReadRepository) == ReadOnlySession


def test_write_repository_stays_on_the_write_session_and_no_longer_lists():
    assert _session_type_of(ConversationRepository) == AsyncSession
    assert not hasattr(ConversationRepository, "fetch_conversations_with_relations")
    assert not hasattr(ConversationRepository, "count_conversations")


@pytest.mark.asyncio
async def test_injector_builds_the_read_repository_with_the_read_session(monkeypatch):
    from fastapi_injector import RequestScopeFactory
    from injector import Injector

    from app.dependencies.dependency_injection import Dependencies

    write_session, read_session = object(), object()
    monkeypatch.setattr(settings, "DB_READ_HOST", "reader.internal")
    monkeypatch.setattr(mts.multi_tenant_manager, "get_tenant_session_factory", lambda tenant="master": lambda: write_session)
    monkeypatch.setattr(mts.multi_tenant_manager, "get_tenant_read_session_factory", lambda tenant="master": lambda: read_session)
    inj = Injector([Dependencies()])
    set_tenant_context("acme-co")
    scope_token = allow_replica_reads()
    try:
        async with inj.get(RequestScopeFactory).create_scope():
            assert inj.get(ConversationReadRepository).db is read_session
            assert inj.get(ConversationRepository).db is write_session
    finally:
        reset_replica_reads(scope_token)
        clear_tenant_context()


@pytest.mark.asyncio
async def test_count_conversations_uses_the_read_repository():
    read_repo = AsyncMock(spec=ConversationReadRepository)
    read_repo.count_conversations.return_value = 42
    service = _build_service(read_repo)
    conversation_filter = MagicMock()

    assert await service.count_conversations(conversation_filter) == 42
    read_repo.count_conversations.assert_awaited_once_with(conversation_filter)


@pytest.mark.asyncio
async def test_get_conversations_uses_the_read_repository(monkeypatch):
    monkeypatch.setattr(conversations_service_module, "is_current_user_supervisor_or_admin", lambda: True)
    monkeypatch.setattr(conversations_service_module, "null_unloaded_attributes", lambda models: None)
    read_repo = AsyncMock(spec=ConversationReadRepository)
    models = [MagicMock(), MagicMock()]
    read_repo.fetch_conversations_with_relations.return_value = models
    service = _build_service(read_repo)
    conversation_filter = MagicMock(include_messages=False)

    assert await service.get_conversations(conversation_filter) == models
    read_repo.fetch_conversations_with_relations.assert_awaited_once_with(conversation_filter, include_messages=False)
