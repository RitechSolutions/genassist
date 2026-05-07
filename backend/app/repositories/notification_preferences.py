from uuid import UUID

from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification_type import NotificationTypeModel
from app.db.models.user_notification_preference import UserNotificationPreferenceModel

NOTIFICATION_TYPE_DEFINITIONS: dict[str, dict[str, bool]] = {
    "conversation_started": {"is_tenant": False},
    "conversation_hostility": {"is_tenant": False},
    "conversation_finalized_hostility": {"is_tenant": False},
    "workflow_failed": {"is_tenant": True},
}


@inject
class NotificationPreferencesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_notification_types(self) -> dict[str, NotificationTypeModel]:
        keys = list(NOTIFICATION_TYPE_DEFINITIONS.keys())
        result = await self.db.execute(
            select(NotificationTypeModel).where(NotificationTypeModel.type.in_(keys))
        )
        rows = list(result.scalars().all())
        by_key = {row.type: row for row in rows}

        missing = [key for key in keys if key not in by_key]
        if missing:
            for key in missing:
                row = NotificationTypeModel(
                    type=key,
                    is_tenant=NOTIFICATION_TYPE_DEFINITIONS[key]["is_tenant"],
                    is_enabled=True,
                )
                self.db.add(row)
                by_key[key] = row
            await self.db.commit()
            for row in by_key.values():
                await self.db.refresh(row)

        return by_key

    async def get_user_preferences(
        self, user_id: UUID
    ) -> list[UserNotificationPreferenceModel]:
        query = select(UserNotificationPreferenceModel).where(
            UserNotificationPreferenceModel.user_id == user_id
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def upsert_user_preference(
        self,
        *,
        user_id: UUID,
        notification_type_id: UUID,
        is_enabled: bool,
    ) -> UserNotificationPreferenceModel:
        query = select(UserNotificationPreferenceModel).where(
            UserNotificationPreferenceModel.user_id == user_id,
            UserNotificationPreferenceModel.notification_type_id == notification_type_id,
        )
        result = await self.db.execute(query)
        row = result.scalars().first()
        if not row:
            row = UserNotificationPreferenceModel(
                user_id=user_id,
                notification_type_id=notification_type_id,
                is_enabled=is_enabled,
            )
            self.db.add(row)
        else:
            row.is_enabled = is_enabled

        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def set_notification_type_enabled(
        self, notification_type: NotificationTypeModel, is_enabled: bool
    ) -> NotificationTypeModel:
        notification_type.is_enabled = is_enabled
        await self.db.commit()
        await self.db.refresh(notification_type)
        return notification_type
