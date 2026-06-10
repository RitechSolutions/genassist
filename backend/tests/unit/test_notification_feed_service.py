from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.notification_feed import NotificationFeedService


@pytest.mark.asyncio
async def test_get_feed_reads_from_persisted_notifications():
    repo = AsyncMock()
    service = NotificationFeedService(persisted_notification_repository=repo)
    user_id = uuid4()
    user_notification_id = uuid4()
    notification_id = uuid4()

    repo.list_user_notifications.return_value = (
        [
            (
                SimpleNamespace(id=user_notification_id, is_read=False),
                SimpleNamespace(
                    id=notification_id,
                    type_key="conversation_started",
                    title="Conversation Started",
                    description="New conversation",
                    created_at=None,
                    level="info",
                    action_url="/transcripts?conversation=123",
                    group_id=None,
                ),
            )
        ],
        False,
    )
    repo.get_counters.return_value = 5

    items, has_more, unread_count = await service.get_feed(
        user_id=user_id,
        limit=20,
        skip=0,
    )

    assert has_more is False
    assert unread_count == 5
    assert len(items) == 1
    assert items[0].id == str(user_notification_id)
    assert items[0].notification_id == str(notification_id)
    assert items[0].type_key == "conversation_started"


@pytest.mark.asyncio
async def test_mark_read_commit_updates():
    repo = AsyncMock()
    service = NotificationFeedService(persisted_notification_repository=repo)
    user_id = uuid4()
    ids = [uuid4()]
    repo.mark_read.return_value = 1

    read_updated = await service.mark_read(user_id=user_id, notification_ids=ids, is_read=True)

    assert read_updated == 1
    assert repo.db.commit.await_count == 1
