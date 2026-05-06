from uuid import UUID

from injector import inject
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tenant_notification_preference import TenantNotificationPreferenceModel
from app.db.models.user_notification_preference import UserNotificationPreferenceModel


@inject
class NotificationPreferencesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_preferences(self, user_id: UUID) -> UserNotificationPreferenceModel | None:
        query = select(UserNotificationPreferenceModel).where(
            UserNotificationPreferenceModel.user_id == user_id
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def upsert_user_preferences(
        self,
        *,
        user_id: UUID,
        conversation_started: bool | None = None,
        conversation_hostility: bool | None = None,
        conversation_finalized_hostility: bool | None = None,
    ) -> UserNotificationPreferenceModel:
        row = await self.get_user_preferences(user_id)
        if not row:
            row = UserNotificationPreferenceModel(user_id=user_id)
            self.db.add(row)

        if conversation_started is not None:
            row.conversation_started = conversation_started
        if conversation_hostility is not None:
            row.conversation_hostility = conversation_hostility
        if conversation_finalized_hostility is not None:
            row.conversation_finalized_hostility = conversation_finalized_hostility

        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def get_tenant_id_by_slug(self, slug: str) -> UUID | None:
        # Use raw SQL for resilience across tenant DBs with schema drift
        # (e.g. columns existing in model but missing in physical table).
        result = await self.db.execute(
            text(
                """
                SELECT id
                FROM tenants
                WHERE slug = :slug
                  AND is_deleted = 0
                LIMIT 1
                """
            ),
            {"slug": slug},
        )
        row = result.first()
        return row[0] if row else None

    async def get_tenant_preferences(self, tenant_id: UUID) -> TenantNotificationPreferenceModel | None:
        query = select(TenantNotificationPreferenceModel).where(
            TenantNotificationPreferenceModel.tenant_id == tenant_id
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def upsert_tenant_preferences(
        self,
        *,
        tenant_id: UUID,
        workflow_failed: bool | None = None,
    ) -> TenantNotificationPreferenceModel:
        row = await self.get_tenant_preferences(tenant_id)
        if not row:
            row = TenantNotificationPreferenceModel(tenant_id=tenant_id)
            self.db.add(row)

        if workflow_failed is not None:
            row.workflow_failed = workflow_failed

        await self.db.commit()
        await self.db.refresh(row)
        return row
