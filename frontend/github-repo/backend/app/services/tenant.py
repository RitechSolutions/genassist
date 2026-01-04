import logging
from typing import Optional, List
from uuid import UUID
from injector import inject
from app.db.models.tenant import TenantModel
from app.db.multi_tenant_session import multi_tenant_manager
from app.core.config.settings import settings
from app.repositories.tenant import TenantRepository

logger = logging.getLogger(__name__)


@inject
class TenantService:
    """Service for managing tenants"""

    def __init__(self, repository: TenantRepository):
        self.repository = repository

    async def get_tenant_by_slug(self, tenant_slug: str) -> Optional[TenantModel]:
        """Get tenant by slug"""
        if not settings.MULTI_TENANT_ENABLED:
            return None

        return await self.repository.get_by_slug(tenant_slug)

    async def get_tenant_by_id(self, tenant_id: UUID) -> Optional[TenantModel]:
        """Get tenant by ID"""
        if not settings.MULTI_TENANT_ENABLED:
            return None

        return await self.repository.get_by_id(tenant_id)

    async def get_all_tenants(self) -> List[TenantModel]:
        """Get all active tenants"""
        if not settings.MULTI_TENANT_ENABLED:
            return []

        return await self.repository.get_active_tenants()

    async def create_tenant(
        self,
        name: str,
        slug: str,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        subdomain: Optional[str] = None,
    ) -> Optional[TenantModel]:
        """Create a new tenant using injected repository and transactional flow."""
        if not settings.MULTI_TENANT_ENABLED:
            logger.warning("Multi-tenancy is disabled, cannot create tenant")
            return None

        # Check if tenant already exists
        existing_tenant = await self.repository.get_by_slug(slug)
        if existing_tenant:
            logger.warning(f"Tenant with slug '{slug}' already exists")
            return None

        # Prepare tenant model (no commit yet)
        sanitized_slug = slug.replace("-", "_")
        tenant = TenantModel(
            name=name,
            slug=slug,
            database_name=f"{settings.DB_NAME}_tenant_{sanitized_slug}",
            description=description,
            domain=domain,
            subdomain=subdomain,
        )

        committed = False
        try:
            # Add to master metadata first (flush to get ID)
            tenant = await self.repository.create(tenant)

            # Create tenant database
            success = await multi_tenant_manager.create_tenant_database(slug)
            if not success:
                logger.error(f"Failed to create database for tenant {slug}")
                return None

            seed_success = await multi_tenant_manager.seed_tenant_database(slug)
            if not seed_success:
                logger.warning(
                    f"Failed to seed tenant database {slug}, but tenant was created"
                )
            else:
                logger.info(f"Successfully seeded tenant database: {slug}")

            await self.repository.db.commit()
            committed = True
            await self.repository.db.refresh(tenant)
            logger.info(f"Created tenant: {name} ({slug})")
            return tenant
        finally:
            if not committed:
                await self.repository.db.rollback()

    async def update_tenant(self, tenant_id: UUID, **updates) -> Optional[TenantModel]:
        """Update tenant information"""
        if not settings.MULTI_TENANT_ENABLED:
            return None

        tenant = await self.repository.get_by_id(tenant_id)
        if not tenant:
            return None

        for key, value in updates.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)

        await self.repository.update(tenant)
        await self.repository.db.commit()
        await self.repository.db.refresh(tenant)
        return tenant

    async def deactivate_tenant(self, tenant_id: UUID) -> bool:
        """Deactivate a tenant"""
        if not settings.MULTI_TENANT_ENABLED:
            return False

        success = await self.repository.delete(tenant_id)
        if success:
            await self.repository.db.commit()
        return success
