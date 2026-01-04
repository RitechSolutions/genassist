from typing import Optional, List
from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.tenant import TenantModel


@inject
class TenantRepository:
    """Repository for tenant operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_slug(self, slug: str) -> Optional[TenantModel]:
        """Get tenant by slug"""
        result = await self.db.execute(
            select(TenantModel).where(TenantModel.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, tenant_id: UUID) -> Optional[TenantModel]:
        """Get tenant by ID"""
        return await self.db.get(TenantModel, tenant_id)

    async def get_active_tenants(self) -> List[TenantModel]:
        """Get all active tenants"""
        result = await self.db.execute(
            select(TenantModel).where(TenantModel.is_active == True)
        )
        return result.scalars().all()

    async def get_by_domain(self, domain: str) -> Optional[TenantModel]:
        """Get tenant by domain"""
        result = await self.db.execute(
            select(TenantModel).where(TenantModel.domain == domain)
        )
        return result.scalar_one_or_none()

    async def get_by_subdomain(self, subdomain: str) -> Optional[TenantModel]:
        """Get tenant by subdomain"""
        result = await self.db.execute(
            select(TenantModel).where(TenantModel.subdomain == subdomain)
        )
        return result.scalar_one_or_none()

    async def create(self, tenant: TenantModel) -> TenantModel:
        """Create a new tenant"""
        self.db.add(tenant)
        await self.db.flush()
        await self.db.refresh(tenant)
        return tenant

    async def update(self, tenant: TenantModel) -> TenantModel:
        """Update tenant"""
        await self.db.flush()
        await self.db.refresh(tenant)
        return tenant

    async def delete(self, tenant_id: UUID) -> bool:
        """Delete tenant (soft delete by setting is_active=False)"""
        tenant = await self.get_by_id(tenant_id)
        if tenant:
            tenant.is_active = False
            await self.update(tenant)
            return True
        return False
