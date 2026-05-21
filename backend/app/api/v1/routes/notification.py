from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi_injector import Injected

from app.auth.dependencies import auth
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.notification import (
    NotificationAdminTargetingRead,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
    NotificationTypeTargetingRead,
    NotificationTypeTargetingUpdate,
    NotificationUserSettingsRead,
    NotificationUserSettingsUpdate,
)
from app.services.notification import NotificationService

router = APIRouter()


def _user_group_context(request: Request) -> tuple[UUID | None, list[UUID]]:
    user = getattr(request.state, "user", None)
    if not user:
        return None, []
    gid = getattr(user, "group_id", None)
    supervised = list(getattr(user, "supervised_group_ids", None) or [])
    return gid, supervised


@router.get(
    "",
    response_model=NotificationUserSettingsRead,
    dependencies=[Depends(auth)],
)
async def get_notification_user_settings(
    request: Request,
    service: NotificationService = Injected(NotificationService),
) -> NotificationUserSettingsRead:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    gid, supervised = _user_group_context(request)
    return await service.get_user_settings(
        request.state.user.id,
        user_group_id=gid,
        supervised_group_ids=supervised,
    )


@router.post(
    "/reads",
    response_model=NotificationMarkReadResponse,
    dependencies=[Depends(auth)],
    summary="Mark notification instances as read",
    description=(
        "Persists read state per synthetic notification id for the current user. "
        "Does not affect future notifications of the same type."
    ),
)
async def mark_notifications_read(
    dto: NotificationMarkReadRequest,
    request: Request,
    service: NotificationService = Injected(NotificationService),
) -> NotificationMarkReadResponse:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    return await service.mark_notifications_read(
        request.state.user.id,
        dto.notification_ids,
    )


@router.patch(
    "",
    response_model=NotificationUserSettingsRead,
    dependencies=[Depends(auth)],
)
async def update_notification_user_settings(
    dto: NotificationUserSettingsUpdate,
    request: Request,
    service: NotificationService = Injected(NotificationService),
) -> NotificationUserSettingsRead:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    gid, supervised = _user_group_context(request)
    return await service.update_user_settings(
        request.state.user.id,
        dto,
        user_group_id=gid,
        supervised_group_ids=supervised,
    )


@router.get(
    "/admin/targeting",
    response_model=NotificationAdminTargetingRead,
    dependencies=[Depends(auth)],
)
async def get_notification_admin_targeting(
    request: Request,
    service: NotificationService = Injected(NotificationService),
) -> NotificationAdminTargetingRead:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    return await service.get_admin_targeting()


@router.put(
    "/admin/targeting/{type_key}",
    response_model=NotificationTypeTargetingRead,
    dependencies=[Depends(auth)],
)
async def put_notification_admin_targeting(
    type_key: str,
    dto: NotificationTypeTargetingUpdate,
    request: Request,
    service: NotificationService = Injected(NotificationService),
) -> NotificationTypeTargetingRead:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    return await service.update_admin_targeting(type_key, dto)
