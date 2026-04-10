from uuid import UUID
from fastapi import APIRouter, Depends, Request
from fastapi_injector import Injected
from app.core.permissions.constants import Permissions as P
from app.auth.dependencies import auth, permissions, require_admin_user
from app.auth.utils import current_user_is_admin
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.filter import UserListFilter
from app.schemas.user import UserRead, UserCreate, UserUpdate
from app.services.roles import RolesService
from app.services.users import UserService

router = APIRouter()


@router.post(
    "",
    response_model=UserRead,
    dependencies=[Depends(auth), Depends(permissions(P.User.CREATE))],
)
async def create(
    user: UserCreate,
    service: UserService = Injected(UserService),
    role_service: RolesService = Injected(RolesService),
):
    roles = await role_service.get_all()
    internal_role_ids = [role.id for role in roles if role.role_type == "internal"]
    if any(role in internal_role_ids for role in user.role_ids):
        raise AppException(error_key=ErrorKey.CREATE_USER_TYPE_IN_MENU, status_code=400)
    created_user = await service.create(user)
    return created_user


@router.get(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(auth), Depends(permissions(P.User.READ))],
)
async def get(user_id: UUID, service: UserService = Injected(UserService)):
    user = await service.get_by_id(user_id)
    if not user:
        raise AppException(error_key=ErrorKey.USER_NOT_FOUND)
    return user


@router.get(
    "",
    response_model=list[UserRead],
    dependencies=[Depends(auth), Depends(permissions(P.User.READ))],
)
async def get_all(
    filter: UserListFilter = Depends(), service: UserService = Injected(UserService)
):
    filter.limit = 1000 if filter.limit == 20 else filter.limit
    if filter.deleted_only and not current_user_is_admin():
        raise AppException(
            error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
            status_code=403,
        )
    return await service.get_all(filter)


@router.put(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(auth), Depends(permissions(P.User.UPDATE))],
)
async def update(
    user_id: UUID, user_update: UserUpdate, service: UserService = Injected(UserService)
):
    return await service.update(user_id, user_update)


@router.post(
    "/{user_id}/restore",
    response_model=UserRead,
    dependencies=[Depends(auth), Depends(require_admin_user)],
)
async def restore_user(
    user_id: UUID,
    service: UserService = Injected(UserService),
):
    return await service.restore_soft_deleted(user_id)


@router.delete(
    "/{user_id}",
    dependencies=[Depends(auth), Depends(permissions(P.User.DELETE))],
)
async def delete_user(
    user_id: UUID,
    request: Request,
    service: UserService = Injected(UserService),
):
    current = getattr(request.state, "user", None)
    actor_id = current.id if current else None
    return await service.soft_delete(user_id, actor_user_id=actor_id)
