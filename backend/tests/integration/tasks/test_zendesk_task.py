import asyncio
import logging
from fastapi_injector import RequestScopeFactory
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json
from sqlalchemy import text

from app.dependencies.injector import injector
from app.core.utils.enums.conversation_type_enum import ConversationType
from app.core.utils.enums.transcript_message_type import TranscriptMessageType
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.tasks.conversations_tasks import cleanup_stale_conversations_async
from app.db.seed.seed_data_config import seed_test_data
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.zendesk_tasks import analyze_zendesk_tickets_async_with_scope


logger = logging.getLogger(__name__)


@pytest.mark.asyncio(scope="session")
async def test_zendesk_task():
    result = await analyze_zendesk_tickets_async_with_scope()
    assert result is not None, "Zendesk task should return a result"
    assert result.get("status") == "completed", "Zendesk task should complete successfully"

