from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.schemas.user import UserTypeRead, UserTypeCreate, UserTypeUpdate
from app.services.user_types import UserTypesService


router = APIRouter()


@router.get("/{user_type_id}", response_model=UserTypeRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:user_type"))
    ])
async def get(user_type_id: UUID, service: UserTypesService = Injected(UserTypesService)):
    return await service.get_by_id(user_type_id)


@router.get("/", response_model=list[UserTypeRead],dependencies=[
    Depends(auth),
    Depends(permissions("read:user_type"))
    ])
async def get_all(service: UserTypesService = Injected(UserTypesService)):
    return await service.get_all()


@router.post("/", response_model=UserTypeRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:user_type"))
    ])
async def create(
        user_type: UserTypeCreate,
        service: UserTypesService = Injected(UserTypesService)
        ):
    return await service.create(user_type)


@router.delete("/{user_type_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:user_type"))
    ])
async def delete(
        user_type_id: UUID,
        service: UserTypesService = Injected(UserTypesService)
        ):
    return await service.delete(user_type_id)


@router.patch("/{user_type_id}", response_model=UserTypeRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:user_type"))
    ])
async def update(
        user_type_id: UUID,
        user_type: UserTypeUpdate,
        service: UserTypesService = Injected(UserTypesService)
        ):
    return await service.update(user_type_id, user_type)
