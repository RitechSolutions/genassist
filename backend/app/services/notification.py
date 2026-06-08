from uuid import UUID

from injector import inject

from app.auth.utils import current_user_is_admin
from app.db.models.notification_type import NotificationTypeModel
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.notification import NotificationRepository
from app.schemas.notification import (
    NotificationAdminTargetingRead,
    NotificationTypeTargetingRead,
    NotificationTypeTargetingUpdate,
    NotificationUserSettingsRead,
    NotificationUserSettingsUpdate,
)

TYPE_CONVERSATION_STARTED = "conversation_started"
TYPE_CONVERSATION_HOSTILITY = "conversation_hostility"
TYPE_CONVERSATION_FINALIZED_HOSTILITY = "conversation_finalized_hostility"
TYPE_WORKFLOW_FAILED = "workflow_failed"

TYPE_BY_FIELD = {
    "conversation_started": TYPE_CONVERSATION_STARTED,
    "conversation_hostility": TYPE_CONVERSATION_HOSTILITY,
    "conversation_finalized_hostility": TYPE_CONVERSATION_FINALIZED_HOSTILITY,
    "workflow_failed": TYPE_WORKFLOW_FAILED,
}


@inject
class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    @staticmethod
    def _user_setting_value(
        *,
        type_key: str,
        notification_types: dict[str, NotificationTypeModel],
        user_setting_by_type_key: dict[str, bool],
    ) -> bool:
        notification_type = notification_types[type_key]
        if notification_type.is_tenant:
            return bool(notification_type.is_enabled)
        return user_setting_by_type_key.get(type_key, True)

    async def get_user_settings(
        self,
        user_id: UUID,
        *,
        user_group_id: UUID | None = None,
        supervised_group_ids: list[UUID] | None = None,
    ) -> NotificationUserSettingsRead:
        notification_types = await self.repo.ensure_notification_types()
        user_setting_by_type_key = await self.repo.list_user_notification_settings(user_id)

        workflow_type = notification_types[TYPE_WORKFLOW_FAILED]
        workflow_manageable = current_user_is_admin() and workflow_type.is_tenant
        is_admin = current_user_is_admin()

        audience = await self.repo.build_audience_flags_for_user(
            user_id=user_id,
            user_group_id=user_group_id,
            supervised_group_ids=list(supervised_group_ids or []),
            bypass_audience_restrictions=is_admin,
        )

        def _non_tenant_effective(type_key: str) -> bool:
            if not audience.get(type_key, False):
                return False
            return self._user_setting_value(
                type_key=type_key,
                notification_types=notification_types,
                user_setting_by_type_key=user_setting_by_type_key,
            )

        return NotificationUserSettingsRead(
            conversation_started=_non_tenant_effective(TYPE_CONVERSATION_STARTED),
            conversation_hostility=_non_tenant_effective(TYPE_CONVERSATION_HOSTILITY),
            conversation_finalized_hostility=_non_tenant_effective(
                TYPE_CONVERSATION_FINALIZED_HOSTILITY
            ),
            workflow_failed=audience.get(TYPE_WORKFLOW_FAILED, False),
            can_manage_workflow_failed=workflow_manageable,
        )

    async def update_user_settings(
        self,
        user_id: UUID,
        dto: NotificationUserSettingsUpdate,
        *,
        user_group_id: UUID | None = None,
        supervised_group_ids: list[UUID] | None = None,
    ) -> NotificationUserSettingsRead:
        notification_types = await self.repo.ensure_notification_types()
        is_admin = current_user_is_admin()
        updates = dto.model_dump(exclude_none=True)

        for field_name, field_value in updates.items():
            type_key = TYPE_BY_FIELD.get(field_name)
            if not type_key:
                raise AppException(
                    status_code=400,
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail=f"Unknown notification settings field: {field_name}",
                )

            notification_type = notification_types[type_key]
            if notification_type.is_tenant:
                if not is_admin:
                    raise AppException(
                        status_code=403,
                        error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                        error_detail="Only admins can update tenant-level workflow notification settings.",
                    )
                await self.repo.set_notification_type_enabled(
                    notification_type, bool(field_value)
                )
            else:
                await self.repo.upsert_user_notification_setting(
                    user_id=user_id,
                    type_key=type_key,
                    is_enabled=bool(field_value),
                )

        return await self.get_user_settings(
            user_id,
            user_group_id=user_group_id,
            supervised_group_ids=supervised_group_ids,
        )

    async def get_admin_targeting(self) -> NotificationAdminTargetingRead:
        if not current_user_is_admin():
            raise AppException(
                status_code=403,
                error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                error_detail="Only admins can view notification targeting.",
            )
        rows = await self.repo.get_admin_targeting_rows()
        types = [
            NotificationTypeTargetingRead(
                type_key=nt.type,
                allow_all_tenant_users=nt.allow_all_tenant_users,
                user_ids=sorted(uids, key=str),
                group_ids=sorted(gids, key=str),
            )
            for nt, uids, gids in rows
        ]
        return NotificationAdminTargetingRead(types=types)

    async def update_admin_targeting(
        self,
        type_key: str,
        dto: NotificationTypeTargetingUpdate,
    ) -> NotificationTypeTargetingRead:
        if not current_user_is_admin():
            raise AppException(
                status_code=403,
                error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                error_detail="Only admins can update notification targeting.",
            )
        try:
            nt, user_ids_out, group_ids_out = await self.repo.set_admin_targeting(
                type_key=type_key,
                allow_all_tenant_users=dto.allow_all_tenant_users,
                user_ids=list(dto.user_ids),
                group_ids=list(dto.group_ids),
            )
        except ValueError as exc:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=str(exc),
            ) from exc
        return NotificationTypeTargetingRead(
            type_key=nt.type,
            allow_all_tenant_users=nt.allow_all_tenant_users,
            user_ids=sorted(user_ids_out, key=str),
            group_ids=sorted(group_ids_out, key=str),
        )
