from fastapi import APIRouter, Depends, Request
from fastapi_injector import Injected

from app.auth.dependencies import auth
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.notification_preferences import (
    NotificationPreferencesRead,
    NotificationPreferencesUpdate,
)
from app.services.notification_preferences import NotificationPreferencesService

router = APIRouter()


@router.get(
    "",
    response_model=NotificationPreferencesRead,
    dependencies=[Depends(auth)],
)
async def get_notification_preferences(
    request: Request,
    service: NotificationPreferencesService = Injected(NotificationPreferencesService),
) -> NotificationPreferencesRead:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    return await service.get_preferences(request.state.user.id)


@router.patch(
    "",
    response_model=NotificationPreferencesRead,
    dependencies=[Depends(auth)],
)
async def update_notification_preferences(
    dto: NotificationPreferencesUpdate,
    request: Request,
    service: NotificationPreferencesService = Injected(NotificationPreferencesService),
) -> NotificationPreferencesRead:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    return await service.update_preferences(request.state.user.id, dto)
