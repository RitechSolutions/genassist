from uuid import UUID
from fastapi import APIRouter, Depends

from typing import List

from app.auth.dependencies import auth, permissions
from app.schemas.role import RoleCreate, RoleUpdate, RoleRead
from app.services.roles import RolesService


router = APIRouter()


@router.get("/", response_model=List[RoleRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:role"))
    ])
async def get_all(service: RolesService = Depends()):
    return await service.get_all()


@router.get("/{role_id}", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:role"))
    ])
async def get(role_id: UUID, service: RolesService = Depends()):
    return await service.get_by_id(role_id)


@router.post("/", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:role"))
    ])
async def create(role: RoleCreate, service: RolesService = Depends()):
    return await service.create(role)

@router.patch("/{role_id}", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:role"))
    ])
async def update(role_id: UUID, role: RoleUpdate, service: RolesService = Depends()):
<<<<<<< HEAD
    return await service.update(role_id, role)
=======
    return await service.update_partial(role_id, role)
>>>>>>> development


@router.delete("/{role_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:role"))
    ])
async def delete(role_id: UUID, service: RolesService = Depends()):
    return await service.delete(role_id)
