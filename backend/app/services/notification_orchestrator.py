from datetime import datetime, timezone
from uuid import UUID

from injector import inject

from app.repositories.notification import NotificationRepository, PersistedNotificationRepository


@inject
class NotificationOrchestratorService:
    def __init__(
        self,
        notification_repository: NotificationRepository,
        persisted_notification_repository: PersistedNotificationRepository,
    ):
        self._notification_repo = notification_repository
        self._persisted_repo = persisted_notification_repository

    async def persist_notification_event(
        self,
        *,
        type_key: str,
        level: str,
        title: str,
        description: str,
        action_url: str,
        entity_kind: str | None = None,
        entity_id: UUID | None = None,
        event_key: str | None = None,
        metadata: dict | None = None,
        group_id: UUID | None = None,
    ) -> dict | None:
        notification_type = await self._notification_repo.get_notification_type_by_key(type_key)
        if not notification_type or not notification_type.is_enabled:
            return None

        notification_row = None
        if event_key:
            notification_row = await self._persisted_repo.get_by_event_key(event_key)
        if not notification_row:
            notification_row = await self._persisted_repo.create_notification(
                notification_type_id=notification_type.id,
                type_key=type_key,
                level=level,
                title=title,
                description=description,
                action_url=action_url,
                entity_kind=entity_kind,
                entity_id=entity_id,
                event_key=event_key,
                metadata_json=metadata,
                group_id=group_id,
            )

            recipient_user_ids = await self._notification_repo.resolve_recipient_user_ids(
                type_key=type_key,
                group_id=group_id,
            )
            user_rows = await self._persisted_repo.create_user_notifications(
                notification_id=notification_row.id,
                user_ids=recipient_user_ids,
            )
            await self._persisted_repo.db.commit()
            user_notification_ids = [str(r.id) for r in user_rows]
            recipient_user_id_strings = [str(uid) for uid in recipient_user_ids]
        else:
            user_notification_ids = []
            recipient_user_id_strings = []

        return {
            "id": str(notification_row.id),
            "notification_id": str(notification_row.id),
            "type_key": notification_row.type_key,
            "title": notification_row.title,
            "description": notification_row.description,
            "type": notification_row.level,
            "action_url": notification_row.action_url,
            "timestamp": (
                notification_row.created_at or datetime.now(timezone.utc)
            ).isoformat(),
            "group_id": str(notification_row.group_id) if notification_row.group_id else None,
            "user_notification_ids": user_notification_ids,
            "recipient_user_ids": recipient_user_id_strings,
            "is_read": False,
        }
