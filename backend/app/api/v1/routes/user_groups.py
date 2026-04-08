from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, require_admin_user
from app.schemas.user_group import UserGroupCreate, UserGroupRead, UserGroupUpdate
from app.services.user_groups import UserGroupService

router = APIRouter()


@router.get(
    "",
    response_model=list[UserGroupRead],
    dependencies=[Depends(auth), Depends(require_admin_user)],
)
async def get_all(service: UserGroupService = Injected(UserGroupService)):
    return await service.get_all()


@router.get(
    "/{group_id}",
    response_model=UserGroupRead,
    dependencies=[Depends(auth), Depends(require_admin_user)],
)
async def get(group_id: UUID, service: UserGroupService = Injected(UserGroupService)):
    return await service.get_by_id(group_id)


@router.post(
    "",
    response_model=UserGroupRead,
    dependencies=[Depends(auth), Depends(require_admin_user)],
)
async def create(
    data: UserGroupCreate,
    service: UserGroupService = Injected(UserGroupService),
):
    return await service.create(data)


@router.patch(
    "/{group_id}",
    response_model=UserGroupRead,
    dependencies=[Depends(auth), Depends(require_admin_user)],
)
async def update(
    group_id: UUID,
    data: UserGroupUpdate,
    service: UserGroupService = Injected(UserGroupService),
):
    return await service.update(group_id, data)


@router.delete(
    "/{group_id}",
    dependencies=[Depends(auth), Depends(require_admin_user)],
)
async def delete(
    group_id: UUID,
    service: UserGroupService = Injected(UserGroupService),
):
    return await service.delete(group_id)