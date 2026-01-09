from typing import List
from fastapi import APIRouter, Depends, Request
from fastapi_injector import Injected
from app.auth.dependencies import auth, permissions
from app.schemas.role_permission import RolePermissionRead, RolePermissionCreate, RolePermissionUpdate
from app.services.role_permissions import RolePermissionsService
from uuid import UUID
router = APIRouter()

@router.post("/", response_model=RolePermissionRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:role_permission"))
])
async def create(
    data: RolePermissionCreate,
    service: RolePermissionsService = Injected(RolePermissionsService)
):
    return await service.create(data)

@router.get("/", response_model=List[RolePermissionRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:role_permission"))
])
async def get_all(
    service: RolePermissionsService = Injected(RolePermissionsService)
):
    return await service.get_all()

@router.get("/{rp_id}", response_model=RolePermissionRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:role_permission"))
])
async def get(
    rp_id: UUID,
    service: RolePermissionsService = Injected(RolePermissionsService)
):
    return await service.get_by_id(rp_id)

@router.patch("/{rp_id}", response_model=RolePermissionRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:role_permission"))
])
async def update(
    rp_id: UUID,
    data: RolePermissionUpdate,
    service: RolePermissionsService = Injected(RolePermissionsService)
):
    return await service.update(rp_id, data)

@router.delete("/{rp_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:role_permission"))
])
async def delete(
    rp_id: UUID,
    service: RolePermissionsService = Injected(RolePermissionsService)
):
    return await service.delete(rp_id)
