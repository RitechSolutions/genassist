from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from injector import inject
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification_type import NotificationTypeModel
from app.db.models.notification_type_recipient_group import NotificationTypeRecipientGroupModel
from app.db.models.notification_type_recipient_user import NotificationTypeRecipientUserModel
from app.db.models.user_notification_read import UserNotificationReadModel
from app.db.models.user_notification_setting import UserNotificationSettingModel

NOTIFICATION_TYPE_DEFINITIONS: dict[str, dict[str, bool]] = {
    "conversation_started": {"is_tenant": False},
    "conversation_hostility": {"is_tenant": False},
    "conversation_finalized_hostility": {"is_tenant": False},
    "workflow_failed": {"is_tenant": True},
}


@inject
class NotificationRepository:
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
                    allow_all_tenant_users=True,
                )
                self.db.add(row)
                by_key[key] = row
            await self.db.commit()
            for row in by_key.values():
                await self.db.refresh(row)

        return by_key

    async def list_user_notification_settings(
        self, user_id: UUID
    ) -> list[UserNotificationSettingModel]:
        query = select(UserNotificationSettingModel).where(
            UserNotificationSettingModel.user_id == user_id
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def upsert_user_notification_setting(
        self,
        *,
        user_id: UUID,
        notification_type_id: UUID,
        is_enabled: bool,
    ) -> UserNotificationSettingModel:
        query = select(UserNotificationSettingModel).where(
            UserNotificationSettingModel.user_id == user_id,
            UserNotificationSettingModel.notification_type_id == notification_type_id,
        )
        result = await self.db.execute(query)
        row = result.scalars().first()
        if not row:
            row = UserNotificationSettingModel(
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

    async def _recipient_users_by_type_id(
        self, type_ids: list[UUID]
    ) -> dict[UUID, set[UUID]]:
        if not type_ids:
            return {}
        stmt = select(
            NotificationTypeRecipientUserModel.notification_type_id,
            NotificationTypeRecipientUserModel.user_id,
        ).where(
            NotificationTypeRecipientUserModel.notification_type_id.in_(type_ids),
            NotificationTypeRecipientUserModel.is_deleted == 0,
        )
        result = await self.db.execute(stmt)
        out: dict[UUID, set[UUID]] = defaultdict(set)
        for tid, uid in result.all():
            out[tid].add(uid)
        return dict(out)

    async def _recipient_groups_by_type_id(
        self, type_ids: list[UUID]
    ) -> dict[UUID, set[UUID]]:
        if not type_ids:
            return {}
        stmt = select(
            NotificationTypeRecipientGroupModel.notification_type_id,
            NotificationTypeRecipientGroupModel.group_id,
        ).where(
            NotificationTypeRecipientGroupModel.notification_type_id.in_(type_ids),
            NotificationTypeRecipientGroupModel.is_deleted == 0,
        )
        result = await self.db.execute(stmt)
        out: dict[UUID, set[UUID]] = defaultdict(set)
        for tid, gid in result.all():
            out[tid].add(gid)
        return dict(out)

    @staticmethod
    def _user_matches_audience(
        *,
        nt: NotificationTypeModel,
        user_id: UUID,
        user_group_id: UUID | None,
        supervised_group_ids: list[UUID],
        explicit_user_ids: set[UUID],
        explicit_group_ids: set[UUID],
        user_setting_enabled: bool,
    ) -> bool:
        if not nt.is_enabled:
            return False

        if nt.is_tenant:
            if nt.allow_all_tenant_users:
                return True
            if user_id in explicit_user_ids:
                return True
            if user_group_id and user_group_id in explicit_group_ids:
                return True
            if explicit_group_ids and supervised_group_ids:
                if explicit_group_ids.intersection(supervised_group_ids):
                    return True
            return False

        if not user_setting_enabled:
            return False
        if nt.allow_all_tenant_users:
            return True
        if user_id in explicit_user_ids:
            return True
        if user_group_id and user_group_id in explicit_group_ids:
            return True
        if explicit_group_ids and supervised_group_ids:
            if explicit_group_ids.intersection(supervised_group_ids):
                return True
        return False

    async def build_audience_flags_for_user(
        self,
        *,
        user_id: UUID,
        user_group_id: UUID | None,
        supervised_group_ids: list[UUID],
        bypass_audience_restrictions: bool = False,
    ) -> dict[str, bool]:
        types = await self.ensure_notification_types()
        ordered = list(NOTIFICATION_TYPE_DEFINITIONS.keys())
        type_ids = [types[k].id for k in ordered]
        users_map = await self._recipient_users_by_type_id(type_ids)
        groups_map = await self._recipient_groups_by_type_id(type_ids)
        rows = await self.list_user_notification_settings(user_id)
        setting_by_type = {r.notification_type_id: r.is_enabled for r in rows}

        flags: dict[str, bool] = {}
        for k in ordered:
            nt = types[k]
            if bypass_audience_restrictions:
                # Admins always count as inside admin targeting (lists / allow-all),
                # but non-tenant types still honor per-user opt-out in user_notification_settings.
                if not nt.is_enabled:
                    flags[k] = False
                    continue
                if nt.is_tenant:
                    flags[k] = True
                    continue
                flags[k] = bool(setting_by_type.get(nt.id, True))
                continue
            flags[k] = self._user_matches_audience(
                nt=nt,
                user_id=user_id,
                user_group_id=user_group_id,
                supervised_group_ids=list(supervised_group_ids or []),
                explicit_user_ids=users_map.get(nt.id, set()),
                explicit_group_ids=groups_map.get(nt.id, set()),
                user_setting_enabled=setting_by_type.get(nt.id, True),
            )
        return flags

    async def get_admin_targeting_rows(self) -> list[tuple[NotificationTypeModel, set[UUID], set[UUID]]]:
        types = await self.ensure_notification_types()
        ordered = list(NOTIFICATION_TYPE_DEFINITIONS.keys())
        type_ids = [types[k].id for k in ordered]
        users_map = await self._recipient_users_by_type_id(type_ids)
        groups_map = await self._recipient_groups_by_type_id(type_ids)
        return [
            (
                types[k],
                users_map.get(types[k].id, set()),
                groups_map.get(types[k].id, set()),
            )
            for k in ordered
        ]

    async def set_admin_targeting(
        self,
        *,
        type_key: str,
        allow_all_tenant_users: bool,
        user_ids: list[UUID],
        group_ids: list[UUID],
    ) -> tuple[NotificationTypeModel, set[UUID], set[UUID]]:
        if type_key not in NOTIFICATION_TYPE_DEFINITIONS:
            raise ValueError(f"Unknown notification type: {type_key}")

        types = await self.ensure_notification_types()
        nt = types[type_key]
        nt.allow_all_tenant_users = allow_all_tenant_users

        await self.db.execute(
            delete(NotificationTypeRecipientUserModel).where(
                NotificationTypeRecipientUserModel.notification_type_id == nt.id
            )
        )
        await self.db.execute(
            delete(NotificationTypeRecipientGroupModel).where(
                NotificationTypeRecipientGroupModel.notification_type_id == nt.id
            )
        )

        for uid in user_ids:
            self.db.add(
                NotificationTypeRecipientUserModel(
                    notification_type_id=nt.id,
                    user_id=uid,
                )
            )
        for gid in group_ids:
            self.db.add(
                NotificationTypeRecipientGroupModel(
                    notification_type_id=nt.id,
                    group_id=gid,
                )
            )

        await self.db.commit()
        await self.db.refresh(nt)
        users_map = await self._recipient_users_by_type_id([nt.id])
        groups_map = await self._recipient_groups_by_type_id([nt.id])
        return nt, users_map.get(nt.id, set()), groups_map.get(nt.id, set())

    async def get_read_notification_ids(
        self,
        user_id: UUID,
        notification_ids: list[str] | None = None,
    ) -> set[str]:
        stmt = select(UserNotificationReadModel.notification_id).where(
            UserNotificationReadModel.user_id == user_id,
            UserNotificationReadModel.is_deleted == 0,
        )
        if notification_ids is not None:
            if not notification_ids:
                return set()
            stmt = stmt.where(
                UserNotificationReadModel.notification_id.in_(notification_ids)
            )
        result = await self.db.execute(stmt)
        return set(result.scalars().all())

    async def mark_notifications_read(
        self, user_id: UUID, notification_ids: list[str]
    ) -> int:
        if not notification_ids:
            return 0

        existing = await self.get_read_notification_ids(user_id, notification_ids)
        now = datetime.now(timezone.utc)
        added = 0
        for notification_id in notification_ids:
            if notification_id in existing:
                continue
            self.db.add(
                UserNotificationReadModel(
                    user_id=user_id,
                    notification_id=notification_id,
                    read_at=now,
                )
            )
            added += 1

        if added:
            await self.db.commit()
        return added
