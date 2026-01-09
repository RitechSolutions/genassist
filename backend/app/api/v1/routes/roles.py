from uuid import UUID
from fastapi import APIRouter, Depends

from typing import List

from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.schemas.filter import BaseFilterModel
from app.schemas.role import RoleCreate, RoleUpdate, RoleRead
from app.services.roles import RolesService


router = APIRouter()


@router.get("/", response_model=List[RoleRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:role"))
    ])
async def get_all(filter: BaseFilterModel = Depends(), service: RolesService = Injected(RolesService)):
    return await service.get_all(filter)


@router.get("/{role_id}", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:role"))
    ])
async def get(role_id: UUID, service: RolesService = Injected(RolesService)):
    return await service.get_by_id(role_id)


@router.post("/", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:role"))
    ])
async def create(role: RoleCreate, service: RolesService = Injected(RolesService)):
    return await service.create(role)

@router.patch("/{role_id}", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:role"))
    ])
async def update(role_id: UUID, role: RoleUpdate, service: RolesService = Injected(RolesService)):
    return await service.update_partial(role_id, role)


@router.delete("/{role_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:role"))
    ])
async def delete(role_id: UUID, service: RolesService = Injected(RolesService)):
    return await service.delete(role_id)
