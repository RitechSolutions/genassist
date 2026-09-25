from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.filter import BaseFilterModel
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.schemas.role_permission import RolePermissionsSet, RolePermissionsSetResult
from app.services.role_permissions import RolePermissionsService
from app.services.roles import RolesService

router = APIRouter()


@router.get("", response_model=List[RoleRead], dependencies=[
    Depends(auth),
    Depends(permissions(P.Role.READ))
    ])
async def get_all(filter: BaseFilterModel = Depends(), service: RolesService = Injected(RolesService)):
    return await service.get_all(filter)


@router.get("/{role_id}", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.Role.READ))
    ])
async def get(role_id: UUID, service: RolesService = Injected(RolesService)):
    return await service.get_by_id(role_id)


@router.post("", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.Role.CREATE))
    ])
async def create(role: RoleCreate, service: RolesService = Injected(RolesService)):
    return await service.create(role)

@router.patch("/{role_id}", response_model=RoleRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.Role.UPDATE))
    ])
async def update(role_id: UUID, role: RoleUpdate, service: RolesService = Injected(RolesService)):
    return await service.update_partial(role_id, role)


@router.delete("/{role_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.Role.DELETE))
    ])
async def delete(role_id: UUID, service: RolesService = Injected(RolesService)):
    return await service.delete(role_id)


@router.get("/{role_id}/permissions", response_model=List[UUID], dependencies=[
    Depends(auth),
    Depends(permissions(P.RolePermission.READ))
    ])
async def get_permissions(
    role_id: UUID,
    service: RolePermissionsService = Injected(RolePermissionsService),
):
    """The permission IDs held by one role."""
    return await service.get_permission_ids_for_role(role_id)


@router.put("/{role_id}/permissions", response_model=RolePermissionsSetResult, dependencies=[
    Depends(auth),
    Depends(permissions(P.RolePermission.CREATE, P.RolePermission.DELETE))
    ])
async def set_permissions(
    role_id: UUID,
    data: RolePermissionsSet,
    service: RolePermissionsService = Injected(RolePermissionsService),
):
    """Replace a role's permissions in one transaction."""
    return await service.set_for_role(role_id, data.permission_ids)
