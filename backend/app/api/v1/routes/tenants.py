from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_injector import Injected
from app.core.permissions.constants import Permissions as P
from app.auth.dependencies import auth, permissions
from app.schemas.tenants import TenantCreate, TenantResponse, TenantUpdate
from app.services.tenant import TenantService

router = APIRouter()


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Tenant.CREATE))],
)
async def create_tenant(
    tenant_data: TenantCreate,
    service: TenantService = Injected(TenantService),
):
    """Create a new tenant"""

    tenant = await service.create_tenant(
        name=tenant_data.name,
        slug=tenant_data.slug,
        description=tenant_data.description,
        domain=tenant_data.domain,
        subdomain=tenant_data.subdomain,
    )

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create tenant. Tenant may already exist.",
        )

    return tenant


@router.get(
    "",
    response_model=List[TenantResponse],
    dependencies=[Depends(auth), Depends(permissions(P.Tenant.READ))],
)
async def list_tenants(
    service: TenantService = Injected(TenantService),
):
    """List all active tenants"""
    tenants = await service.get_all_tenants()
    return tenants


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Tenant.READ))],
)
async def get_tenant(
    tenant_id: UUID,
    service: TenantService = Injected(TenantService),
):
    """Get a specific tenant by ID"""
    tenant = await service.get_tenant_by_id(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    return tenant


@router.get(
    "/slug/{tenant_slug}",
    response_model=TenantResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Tenant.READ))],
)
async def get_tenant_by_slug(
    tenant_slug: str,
    service: TenantService = Injected(TenantService),
):
    """Get a specific tenant by slug"""
    tenant = await service.get_tenant_by_slug(tenant_slug)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    return tenant


@router.put(
    "/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Tenant.UPDATE))],
)
async def update_tenant(
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    service: TenantService = Injected(TenantService),
):
    """Update tenant information"""

    updates = {k: v for k, v in tenant_data.dict().items() if v is not None}
    tenant = await service.update_tenant(tenant_id, **updates)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    return tenant


@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Tenant.DELETE))],
)
async def deactivate_tenant(
    tenant_id: UUID,
    service: TenantService = Injected(TenantService),
):
    """Deactivate a tenant (soft delete)"""
    success = await service.deactivate_tenant(tenant_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
