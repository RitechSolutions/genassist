from uuid import UUID
from fastapi import APIRouter, Depends

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.user import UserRead, UserCreate, UserUpdate
from app.services.users import UserService

router = APIRouter()


@router.post("/", response_model=UserRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:user"))
    ])
async def create(user: UserCreate, service: UserService = Depends()):
    return await service.create(user)



@router.get("/{user_id}", response_model=UserRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:user"))
    ])
async def get(user_id: UUID, service: UserService = Depends()):
    user = await service.get_by_id(user_id)
    if not user:
        raise AppException(error_key=ErrorKey.USER_NOT_FOUND)
    return user


@router.get("/", response_model=list[UserRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:user"))
    ])
async def get_all(service: UserService = Depends()):
    return await service.get_all()


@router.put("/{user_id}", response_model=UserRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:user"))
    ])
async def update(
        user_id: UUID,
        user_update: UserUpdate,
        service: UserService = Depends()
        ):
    return await service.update(user_id, user_update)

