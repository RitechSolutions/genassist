from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from injector import inject
from app.repositories.notification import PersistedNotificationRepository
from app.schemas.notification import NotificationItem

NotificationTypeFilter = Literal[
    "all",
    "conversation_started",
    "conversation_hostility",
    "conversation_finalized_hostility",
    "workflow_failed",
]


@inject
class NotificationFeedService:
    def __init__(
        self,
        persisted_notification_repository: PersistedNotificationRepository,
    ):
        self._persisted_repo = persisted_notification_repository

    async def get_feed(
        self,
        *,
        user_id: UUID,
        limit: int = 50,
        skip: int = 0,
        include_conversation_started: bool = True,
        include_conversation_hostility: bool = True,
        include_conversation_finalized_hostility: bool = True,
        include_workflow_failed: bool = True,
        notification_type: NotificationTypeFilter = "all",
        notification_level: str = "all",
        is_read: bool | None = None,
    ) -> tuple[list[NotificationItem], bool, int]:
        type_keys = self._build_type_filter(
            include_conversation_started=include_conversation_started,
            include_conversation_hostility=include_conversation_hostility,
            include_conversation_finalized_hostility=include_conversation_finalized_hostility,
            include_workflow_failed=include_workflow_failed,
            notification_type=notification_type,
        )
        rows, has_more = await self._persisted_repo.list_user_notifications(
            user_id=user_id,
            limit=limit,
            skip=skip,
            type_keys=type_keys,
            levels=self._build_level_filter(notification_level),
            is_read=is_read,
        )
        unread_count = await self._persisted_repo.get_counters(user_id=user_id)
        items: list[NotificationItem] = []
        for user_row, notification_row in rows:
            items.append(
                NotificationItem(
                    id=str(user_row.id),
                    notification_id=str(notification_row.id),
                    type_key=notification_row.type_key,
                    title=notification_row.title,
                    description=notification_row.description,
                    timestamp=notification_row.created_at or datetime.now(timezone.utc),
                    type=notification_row.level,
                    action_url=notification_row.action_url,
                    group_id=str(notification_row.group_id) if notification_row.group_id else None,
                    is_read=bool(user_row.is_read),
                )
            )
        return items, has_more, unread_count

    async def get_counters(self, *, user_id: UUID) -> int:
        return await self._persisted_repo.get_counters(user_id=user_id)

    async def mark_read(
        self, *, user_id: UUID, notification_ids: list[UUID], is_read: bool
    ) -> int:
        count = await self._persisted_repo.mark_read(
            user_id=user_id,
            user_notification_ids=notification_ids,
            is_read=is_read,
        )
        await self._persisted_repo.db.commit()
        return count

    @staticmethod
    def _build_type_filter(
        *,
        include_conversation_started: bool,
        include_conversation_hostility: bool,
        include_conversation_finalized_hostility: bool,
        include_workflow_failed: bool,
        notification_type: NotificationTypeFilter,
    ) -> list[str] | None:
        if notification_type != "all":
            return [notification_type]
        type_keys: list[str] = []
        if include_conversation_started:
            type_keys.append("conversation_started")
        if include_conversation_hostility:
            type_keys.append("conversation_hostility")
        if include_conversation_finalized_hostility:
            type_keys.append("conversation_finalized_hostility")
        if include_workflow_failed:
            type_keys.append("workflow_failed")
        return type_keys or None

    @staticmethod
    def _build_level_filter(notification_level: str) -> list[str] | None:
        if notification_level == "all":
            return None
        return [notification_level]
