from uuid import UUID
from fastapi import APIRouter, Depends

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.user import UserRead, UserCreate, UserUpdate
<<<<<<< HEAD
=======
from app.services.roles import RolesService
>>>>>>> development
from app.services.users import UserService

router = APIRouter()


@router.post("/", response_model=UserRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:user"))
    ])
<<<<<<< HEAD
async def create(user: UserCreate, service: UserService = Depends()):
    return await service.create(user)
=======
async def create(user: UserCreate, service: UserService = Depends(), role_service: RolesService = Depends()):
    roles = await role_service.get_all()
    internal_role_ids = [role.id for role in roles if role.role_type == "internal"]
    if any(role in internal_role_ids for role in user.role_ids):
        raise AppException(error_key=ErrorKey.CREATE_USER_TYPE_IN_MENU, status_code=400)
    created_user =  await service.create(user)
    return created_user
>>>>>>> development



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

