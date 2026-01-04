from fastapi import APIRouter, Depends, Request
from typing import List
from uuid import UUID

from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.schemas.filter import BaseFilterModel
from app.schemas.permission import PermissionRead, PermissionCreate, PermissionUpdate
from app.services.permissions import PermissionsService

router = APIRouter()

@router.post("/", response_model=PermissionRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:permission"))
])
async def create(
    request: Request,
    permission_data: PermissionCreate,
    service: PermissionsService = Injected(PermissionsService)
):
    return await service.create(permission_data)

@router.get("/", response_model=List[PermissionRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:permission"))
])
async def get_all(filter: BaseFilterModel = Depends(),
    service: PermissionsService = Injected(PermissionsService)
):
    return await service.get_all(filter)

@router.get("/{permission_id}", response_model=PermissionRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:permission"))
])
async def get(
    permission_id: UUID,
    service: PermissionsService = Injected(PermissionsService)
):
    return await service.get_by_id(permission_id)

@router.delete("/{permission_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:permission"))
])
async def delete(
    permission_id: UUID,
    service: PermissionsService = Injected(PermissionsService)
):
    return await service.delete(permission_id)

@router.patch("/{permission_id}", response_model=PermissionRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:permission"))
])
async def update(
    permission_id: UUID,
    permission_data: PermissionUpdate,
    service: PermissionsService = Injected(PermissionsService)
):
    return await service.update(permission_id, permission_data)
