from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi_injector import Injected

from app.auth.dependencies import auth
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.notification import (
    NotificationAdminTargetingRead,
    NotificationCountersResponse,
    NotificationStateUpdate,
    NotificationStateUpdateResponse,
    NotificationTypeTargetingRead,
    NotificationTypeTargetingUpdate,
    NotificationUserSettingsRead,
    NotificationUserSettingsUpdate,
)
from app.services.notification_feed import NotificationFeedService
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


@router.get(
    "/state/counters",
    response_model=NotificationCountersResponse,
    dependencies=[Depends(auth)],
)
async def get_notification_counters(
    request: Request,
    service: NotificationFeedService = Injected(NotificationFeedService),
) -> NotificationCountersResponse:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    unread_count = await service.get_counters(user_id=request.state.user.id)
    return NotificationCountersResponse(unread_count=unread_count)


@router.patch(
    "/state/read",
    response_model=NotificationStateUpdateResponse,
    dependencies=[Depends(auth)],
)
async def patch_notification_read_state(
    dto: NotificationStateUpdate,
    request: Request,
    service: NotificationFeedService = Injected(NotificationFeedService),
) -> NotificationStateUpdateResponse:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    is_read = bool(dto.is_read) if dto.is_read is not None else True
    updated = await service.mark_read(
        user_id=request.state.user.id,
        notification_ids=list(dto.notification_ids),
        is_read=is_read,
    )
    return NotificationStateUpdateResponse(updated_count=updated)
