from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.notification_orchestrator import NotificationOrchestratorService


@pytest.mark.asyncio
async def test_persist_notification_event_creates_notification_and_user_rows():
    notification_repo = AsyncMock()
    persisted_repo = AsyncMock()
    orchestrator = NotificationOrchestratorService(
        notification_repository=notification_repo,
        persisted_notification_repository=persisted_repo,
    )

    type_id = uuid4()
    notification_id = uuid4()
    recipients = [uuid4(), uuid4()]
    notification_repo.get_notification_type_by_key.return_value = SimpleNamespace(
        id=type_id, is_enabled=True
    )
    persisted_repo.get_by_event_key.return_value = None
    persisted_repo.create_notification.return_value = SimpleNamespace(
        id=notification_id,
        type_key="workflow_failed",
        title="Workflow Run Failed",
        description="Pipeline failed",
        level="error",
        action_url="/ml-models",
        created_at=None,
        group_id=None,
    )
    notification_repo.resolve_recipient_user_ids.return_value = recipients
    persisted_repo.create_user_notifications.return_value = [
        SimpleNamespace(id=uuid4()),
        SimpleNamespace(id=uuid4()),
    ]

    payload = await orchestrator.persist_notification_event(
        type_key="workflow_failed",
        level="error",
        title="Workflow Run Failed",
        description="Pipeline failed",
        action_url="/ml-models",
        event_key=f"workflow_failed:pipeline:{uuid4()}",
    )

    assert payload is not None
    assert payload["notification_id"] == str(notification_id)
    assert payload["type_key"] == "workflow_failed"
    assert set(payload["recipient_user_ids"]) == {str(r) for r in recipients}
    persisted_repo.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_notification_event_returns_none_when_type_missing():
    notification_repo = AsyncMock()
    persisted_repo = AsyncMock()
    orchestrator = NotificationOrchestratorService(
        notification_repository=notification_repo,
        persisted_notification_repository=persisted_repo,
    )
    notification_repo.get_notification_type_by_key.return_value = None

    payload = await orchestrator.persist_notification_event(
        type_key="unknown",
        level="info",
        title="Title",
        description="Description",
        action_url="/",
    )
    assert payload is None
