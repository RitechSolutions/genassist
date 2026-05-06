from uuid import UUID

from injector import inject
import logging

from app.auth.utils import current_user_is_admin
from app.core.tenant_scope import get_tenant_context
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.notification_preferences import NotificationPreferencesRepository
from app.schemas.notification_preferences import (
    NotificationPreferencesRead,
    NotificationPreferencesUpdate,
)


logger = logging.getLogger(__name__)


@inject
class NotificationPreferencesService:
    def __init__(self, repo: NotificationPreferencesRepository):
        self.repo = repo

    async def _get_current_tenant_id(self) -> UUID | None:
        tenant_slug = get_tenant_context()
        if not tenant_slug:
            return None

        try:
            tenant_id = await self.repo.get_tenant_id_by_slug(tenant_slug)
        except Exception as exc:
            await self.repo.db.rollback()
            logger.warning(
                "Unable to resolve tenant by slug '%s' for notification preferences: %s",
                tenant_slug,
                type(exc).__name__,
            )
            return None

        if not tenant_id:
            return None
        return tenant_id

    async def get_preferences(self, user_id: UUID) -> NotificationPreferencesRead:
        tenant_id = await self._get_current_tenant_id()
        workflow_failed_supported = tenant_id is not None
        user_prefs = await self.repo.get_user_preferences(user_id)
        tenant_prefs = (
            await self.repo.get_tenant_preferences(tenant_id)
            if tenant_id
            else None
        )

        return NotificationPreferencesRead(
            conversation_started=(
                user_prefs.conversation_started if user_prefs else True
            ),
            conversation_hostility=(
                user_prefs.conversation_hostility if user_prefs else True
            ),
            conversation_finalized_hostility=(
                user_prefs.conversation_finalized_hostility if user_prefs else True
            ),
            workflow_failed=(tenant_prefs.workflow_failed if tenant_prefs else True),
            can_manage_workflow_failed=(
                current_user_is_admin() and workflow_failed_supported
            ),
        )

    async def update_preferences(
        self,
        user_id: UUID,
        dto: NotificationPreferencesUpdate,
    ) -> NotificationPreferencesRead:
        is_admin = current_user_is_admin()
        if dto.workflow_failed is not None and not is_admin:
            raise AppException(
                status_code=403,
                error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                error_detail="Only admins can update tenant-level workflow failed notifications.",
            )

        if any(
            value is not None
            for value in (
                dto.conversation_started,
                dto.conversation_hostility,
                dto.conversation_finalized_hostility,
            )
        ):
            await self.repo.upsert_user_preferences(
                user_id=user_id,
                conversation_started=dto.conversation_started,
                conversation_hostility=dto.conversation_hostility,
                conversation_finalized_hostility=dto.conversation_finalized_hostility,
            )

        if dto.workflow_failed is not None:
            tenant_id = await self._get_current_tenant_id()
            if not tenant_id:
                raise AppException(
                    status_code=400,
                    error_key=ErrorKey.MISSING_PARAMETER,
                    error_detail="Tenant context is required to update tenant-level notification preferences.",
                )
            await self.repo.upsert_tenant_preferences(
                tenant_id=tenant_id,
                workflow_failed=dto.workflow_failed,
            )

        return await self.get_preferences(user_id)
