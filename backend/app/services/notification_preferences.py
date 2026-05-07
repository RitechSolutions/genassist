from uuid import UUID

from injector import inject

from app.auth.utils import current_user_is_admin
from app.db.models.notification_type import NotificationTypeModel
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.notification_preferences import NotificationPreferencesRepository
from app.schemas.notification_preferences import (
    NotificationPreferencesRead,
    NotificationPreferencesUpdate,
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
class NotificationPreferencesService:
    def __init__(self, repo: NotificationPreferencesRepository):
        self.repo = repo

    @staticmethod
    def _user_pref_value(
        *,
        type_key: str,
        notification_types: dict[str, NotificationTypeModel],
        user_pref_by_type_id: dict[UUID, bool],
    ) -> bool:
        notification_type = notification_types[type_key]
        if notification_type.is_tenant:
            return bool(notification_type.is_enabled)
        return user_pref_by_type_id.get(notification_type.id, True)

    async def get_preferences(self, user_id: UUID) -> NotificationPreferencesRead:
        notification_types = await self.repo.ensure_notification_types()
        user_prefs = await self.repo.get_user_preferences(user_id)
        user_pref_by_type_id = {
            pref.notification_type_id: pref.is_enabled for pref in user_prefs
        }

        workflow_type = notification_types[TYPE_WORKFLOW_FAILED]
        workflow_manageable = current_user_is_admin() and workflow_type.is_tenant

        return NotificationPreferencesRead(
            conversation_started=self._user_pref_value(
                type_key=TYPE_CONVERSATION_STARTED,
                notification_types=notification_types,
                user_pref_by_type_id=user_pref_by_type_id,
            ),
            conversation_hostility=self._user_pref_value(
                type_key=TYPE_CONVERSATION_HOSTILITY,
                notification_types=notification_types,
                user_pref_by_type_id=user_pref_by_type_id,
            ),
            conversation_finalized_hostility=self._user_pref_value(
                type_key=TYPE_CONVERSATION_FINALIZED_HOSTILITY,
                notification_types=notification_types,
                user_pref_by_type_id=user_pref_by_type_id,
            ),
            workflow_failed=self._user_pref_value(
                type_key=TYPE_WORKFLOW_FAILED,
                notification_types=notification_types,
                user_pref_by_type_id=user_pref_by_type_id,
            ),
            can_manage_workflow_failed=workflow_manageable,
        )

    async def update_preferences(
        self,
        user_id: UUID,
        dto: NotificationPreferencesUpdate,
    ) -> NotificationPreferencesRead:
        notification_types = await self.repo.ensure_notification_types()
        is_admin = current_user_is_admin()
        updates = dto.model_dump(exclude_none=True)

        for field_name, field_value in updates.items():
            type_key = TYPE_BY_FIELD.get(field_name)
            if not type_key:
                raise AppException(
                    status_code=400,
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail=f"Unknown notification preference field: {field_name}",
                )

            notification_type = notification_types[type_key]
            if notification_type.is_tenant:
                if not is_admin:
                    raise AppException(
                        status_code=403,
                        error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                        error_detail="Only admins can update tenant-level notification preferences.",
                    )
                await self.repo.set_notification_type_enabled(
                    notification_type, bool(field_value)
                )
            else:
                await self.repo.upsert_user_preference(
                    user_id=user_id,
                    notification_type_id=notification_type.id,
                    is_enabled=bool(field_value),
                )

        return await self.get_preferences(user_id)
