from collections import defaultdict
from uuid import UUID

from injector import inject
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import NotificationModel
from app.db.models.notification_recipient import NotificationRecipientModel
from app.db.models.user_notification import UserNotificationModel
from app.db.models.notification_type import NotificationTypeModel
from app.db.models.role import RoleModel
from app.db.models.user import UserModel
from app.db.models.user_role import UserRoleModel
from app.db.models.user_supervised_group import UserSupervisedGroupModel

NOTIFICATION_TYPE_DEFINITIONS: dict[str, dict[str, bool]] = {
    "conversation_started": {"is_tenant": False},
    "conversation_hostility": {"is_tenant": False},
    "conversation_finalized_hostility": {"is_tenant": False},
    "workflow_failed": {"is_tenant": True},
}

PRINCIPAL_USER = "user"
PRINCIPAL_GROUP = "group"


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

    async def _get_user(self, user_id: UUID) -> UserModel | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        return result.scalars().first()

    async def list_user_notification_settings(self, user_id: UUID) -> dict[str, bool]:
        user = await self._get_user(user_id)
        if not user or not isinstance(user.notification_settings, dict):
            return {}
        return {str(k): bool(v) for k, v in user.notification_settings.items()}

    async def upsert_user_notification_setting(
        self,
        *,
        user_id: UUID,
        type_key: str,
        is_enabled: bool,
    ) -> dict[str, bool]:
        user = await self._get_user(user_id)
        if not user:
            return {}
        current = (
            dict(user.notification_settings)
            if isinstance(user.notification_settings, dict)
            else {}
        )
        current[type_key] = bool(is_enabled)
        user.notification_settings = current
        await self.db.commit()
        await self.db.refresh(user)
        return {str(k): bool(v) for k, v in current.items()}

    async def set_notification_type_enabled(
        self, notification_type: NotificationTypeModel, is_enabled: bool
    ) -> NotificationTypeModel:
        notification_type.is_enabled = is_enabled
        await self.db.commit()
        await self.db.refresh(notification_type)
        return notification_type

    async def _recipients_by_type_id(
        self, type_ids: list[UUID]
    ) -> tuple[dict[UUID, set[UUID]], dict[UUID, set[UUID]]]:
        if not type_ids:
            return {}, {}
        stmt = select(
            NotificationRecipientModel.notification_type_id,
            NotificationRecipientModel.principal_type,
            NotificationRecipientModel.principal_id,
        ).where(
            NotificationRecipientModel.notification_type_id.in_(type_ids),
            NotificationRecipientModel.is_deleted == 0,
        )
        result = await self.db.execute(stmt)
        users_out: dict[UUID, set[UUID]] = defaultdict(set)
        groups_out: dict[UUID, set[UUID]] = defaultdict(set)
        for tid, principal_type, principal_id in result.all():
            if principal_type == PRINCIPAL_USER:
                users_out[tid].add(principal_id)
            elif principal_type == PRINCIPAL_GROUP:
                groups_out[tid].add(principal_id)
        return dict(users_out), dict(groups_out)

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
        users_map, groups_map = await self._recipients_by_type_id(type_ids)
        setting_by_type = await self.list_user_notification_settings(user_id)

        flags: dict[str, bool] = {}
        for k in ordered:
            nt = types[k]
            if bypass_audience_restrictions:
                # Admins always count as inside admin targeting (lists / allow-all),
                # but non-tenant types still honor per-user opt-out in users.notification_settings.
                if not nt.is_enabled:
                    flags[k] = False
                    continue
                if nt.is_tenant:
                    flags[k] = True
                    continue
                flags[k] = bool(setting_by_type.get(k, True))
                continue
            flags[k] = self._user_matches_audience(
                nt=nt,
                user_id=user_id,
                user_group_id=user_group_id,
                supervised_group_ids=list(supervised_group_ids or []),
                explicit_user_ids=users_map.get(nt.id, set()),
                explicit_group_ids=groups_map.get(nt.id, set()),
                user_setting_enabled=setting_by_type.get(k, True),
            )
        return flags

    async def get_admin_targeting_rows(self) -> list[tuple[NotificationTypeModel, set[UUID], set[UUID]]]:
        types = await self.ensure_notification_types()
        ordered = list(NOTIFICATION_TYPE_DEFINITIONS.keys())
        type_ids = [types[k].id for k in ordered]
        users_map, groups_map = await self._recipients_by_type_id(type_ids)
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
            delete(NotificationRecipientModel).where(
                NotificationRecipientModel.notification_type_id == nt.id
            )
        )

        for uid in user_ids:
            self.db.add(
                NotificationRecipientModel(
                    notification_type_id=nt.id,
                    principal_type=PRINCIPAL_USER,
                    principal_id=uid,
                )
            )
        for gid in group_ids:
            self.db.add(
                NotificationRecipientModel(
                    notification_type_id=nt.id,
                    principal_type=PRINCIPAL_GROUP,
                    principal_id=gid,
                )
            )

        await self.db.commit()
        await self.db.refresh(nt)
        users_map, groups_map = await self._recipients_by_type_id([nt.id])
        return nt, users_map.get(nt.id, set()), groups_map.get(nt.id, set())

    async def get_notification_type_by_key(
        self, type_key: str
    ) -> NotificationTypeModel | None:
        types = await self.ensure_notification_types()
        return types.get(type_key)

    async def resolve_recipient_user_ids(
        self,
        *,
        type_key: str,
        group_id: UUID | None = None,
    ) -> list[UUID]:
        types = await self.ensure_notification_types()
        nt = types.get(type_key)
        if not nt or not nt.is_enabled:
            return []

        users_map, groups_map = await self._recipients_by_type_id([nt.id])
        explicit_user_ids = set(users_map.get(nt.id, set()))
        explicit_group_ids = set(groups_map.get(nt.id, set()))
        admin_user_ids = set(
            (
                await self.db.execute(
                    select(UserModel.id)
                    .join(UserRoleModel, UserRoleModel.user_id == UserModel.id)
                    .join(RoleModel, RoleModel.id == UserRoleModel.role_id)
                    .where(
                        RoleModel.name == "admin",
                        UserModel.is_deleted == 0,
                    )
                )
            ).scalars().all()
        )

        if nt.allow_all_tenant_users:
            user_rows = (
                await self.db.execute(
                    select(UserModel.id, UserModel.group_id, UserModel.notification_settings).where(
                        UserModel.is_deleted == 0
                    )
                )
            ).all()
        else:
            user_rows: list[tuple[UUID, UUID | None, dict | None]] = []
            if explicit_user_ids:
                direct = (
                    await self.db.execute(
                        select(UserModel.id, UserModel.group_id, UserModel.notification_settings).where(
                            UserModel.id.in_(explicit_user_ids),
                            UserModel.is_deleted == 0,
                        )
                    )
                ).all()
                user_rows.extend(direct)
            if explicit_group_ids:
                group_members = (
                    await self.db.execute(
                        select(UserModel.id, UserModel.group_id, UserModel.notification_settings).where(
                            UserModel.group_id.in_(explicit_group_ids),
                            UserModel.is_deleted == 0,
                        )
                    )
                ).all()
                user_rows.extend(group_members)
                supervisors = (
                    await self.db.execute(
                        select(UserModel.id, UserModel.group_id, UserModel.notification_settings)
                        .join(
                            UserSupervisedGroupModel,
                            UserSupervisedGroupModel.user_id == UserModel.id,
                        )
                        .where(
                            UserSupervisedGroupModel.group_id.in_(explicit_group_ids),
                            UserModel.is_deleted == 0,
                        )
                    )
                ).all()
                user_rows.extend(supervisors)
            if admin_user_ids:
                admins = (
                    await self.db.execute(
                        select(UserModel.id, UserModel.group_id, UserModel.notification_settings).where(
                            UserModel.id.in_(admin_user_ids),
                            UserModel.is_deleted == 0,
                        )
                    )
                ).all()
                user_rows.extend(admins)

        dedup: dict[UUID, tuple[UUID | None, dict | None]] = {}
        for uid, user_group_id, settings in user_rows:
            dedup[uid] = (user_group_id, settings if isinstance(settings, dict) else {})

        if group_id:
            pre_group_filter = dict(dedup)
            supervisors_for_group = (
                await self.db.execute(
                    select(UserSupervisedGroupModel.user_id).where(
                        UserSupervisedGroupModel.group_id == group_id,
                        UserSupervisedGroupModel.is_deleted == 0,
                    )
                )
            ).scalars().all()
            supervisor_ids = set(supervisors_for_group)
            dedup = {
                uid: payload
                for uid, payload in dedup.items()
                if payload[0] == group_id or uid in supervisor_ids
            }
            # Admins should remain eligible by default in selected-users/group mode.
            for admin_id in admin_user_ids:
                if admin_id in pre_group_filter:
                    dedup[admin_id] = pre_group_filter[admin_id]
            # Do not drop the event completely if group-scoped filtering resolves to nobody.
            # In that case, keep the broader targeted audience so notifications still persist.
            if not dedup:
                dedup = pre_group_filter

        if not nt.is_tenant:
            dedup = {
                uid: payload
                for uid, payload in dedup.items()
                if bool((payload[1] or {}).get(type_key, True))
            }

        return sorted(dedup.keys(), key=str)


@inject
class PersistedNotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_event_key(self, event_key: str) -> NotificationModel | None:
        result = await self.db.execute(
            select(NotificationModel).where(
                NotificationModel.event_key == event_key,
                NotificationModel.is_deleted == 0,
            )
        )
        return result.scalars().first()

    async def create_notification(
        self,
        *,
        notification_type_id: UUID,
        type_key: str,
        level: str,
        title: str,
        description: str,
        action_url: str,
        entity_kind: str | None = None,
        entity_id: UUID | None = None,
        event_key: str | None = None,
        metadata_json: dict | None = None,
        group_id: UUID | None = None,
    ) -> NotificationModel:
        row = NotificationModel(
            notification_type_id=notification_type_id,
            type_key=type_key,
            level=level,
            title=title,
            description=description,
            action_url=action_url,
            entity_kind=entity_kind,
            entity_id=entity_id,
            event_key=event_key,
            metadata_json=metadata_json or {},
            group_id=group_id,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def create_user_notifications(
        self,
        *,
        notification_id: UUID,
        user_ids: list[UUID],
    ) -> list[UserNotificationModel]:
        if not user_ids:
            return []
        rows = [
            UserNotificationModel(
                notification_id=notification_id,
                user_id=user_id,
            )
            for user_id in user_ids
        ]
        self.db.add_all(rows)
        await self.db.flush()
        return rows

    async def list_user_notifications(
        self,
        *,
        user_id: UUID,
        limit: int,
        skip: int,
        type_keys: list[str] | None = None,
        levels: list[str] | None = None,
        is_read: bool | None = None,
    ) -> tuple[list[tuple[UserNotificationModel, NotificationModel]], bool]:
        stmt = (
            select(UserNotificationModel, NotificationModel)
            .join(NotificationModel, NotificationModel.id == UserNotificationModel.notification_id)
            .where(
                UserNotificationModel.user_id == user_id,
                UserNotificationModel.is_deleted == 0,
                NotificationModel.is_deleted == 0,
            )
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
            .offset(skip)
            .limit(limit + 1)
        )
        if type_keys:
            stmt = stmt.where(NotificationModel.type_key.in_(type_keys))
        if levels:
            stmt = stmt.where(NotificationModel.level.in_(levels))
        if is_read is not None:
            stmt = stmt.where(UserNotificationModel.is_read == is_read)

        rows = (await self.db.execute(stmt)).all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def get_counters(self, *, user_id: UUID) -> int:
        unread_stmt = select(func.count()).select_from(UserNotificationModel).where(
            UserNotificationModel.user_id == user_id,
            UserNotificationModel.is_deleted == 0,
            UserNotificationModel.is_read.is_(False),
        )
        unread = (await self.db.execute(unread_stmt)).scalar_one()
        return int(unread)

    async def mark_read(
        self, *, user_id: UUID, user_notification_ids: list[UUID], is_read: bool
    ) -> int:
        if not user_notification_ids:
            return 0
        stmt = (
            update(UserNotificationModel)
            .where(
                UserNotificationModel.user_id == user_id,
                UserNotificationModel.id.in_(user_notification_ids),
                UserNotificationModel.is_deleted == 0,
            )
            .values(is_read=is_read)
        )
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)
