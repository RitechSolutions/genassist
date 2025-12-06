import logging
from typing import AsyncGenerator
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.multi_tenant_session import multi_tenant_manager
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


async def get_tenant_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session for the current tenant"""
    tenant_id = getattr(request.state, "tenant_id", None)

    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        logger.debug(f"Session closed for tenant_id: {tenant_id}")


async def pre_wormup_tenant_singleton() -> None:
    from app.core.tenant_scope import (
        set_tenant_context,
        clear_tenant_context,
    )
    from app.dependencies.injector import injector

    # Pre-warm tenant-scoped singletons for all tenants on startup
    try:
        from app.modules.workflow.registry import AgentRegistry

        set_tenant_context("master")
        try:
            ag = injector.get(AgentRegistry)
            await ag.initialize()
            logger.info("Pre-warmed tenant-scoped singletons for tenant: master")
        finally:
            clear_tenant_context()
        if settings.MULTI_TENANT_ENABLED:
            # Query active tenants from master DB and initialize their tenant-scoped singletons
            from sqlalchemy import select
            from app.db.models.tenant import TenantModel
            from app.modules.workflow.registry import AgentRegistry
            from app.modules.workflow.llm.provider import LLMProvider
            from app.modules.data.manager import AgentRAGServiceManager

            master_session_factory = multi_tenant_manager.get_tenant_session_factory(
                "master"
            )
            async with master_session_factory() as session:
                result = await session.execute(
                    select(TenantModel).where(TenantModel.is_active.is_(True))
                )
                tenants = list(result.scalars().all())

            # Always ensure master is pre-warmed as well
            all_tenant_slugs: list[str] = [t.slug for t in tenants if t.slug]

            for tenant_slug in all_tenant_slugs:
                try:
                    set_tenant_context(tenant_slug)
                    # Resolving these triggers per-tenant initialization
                    ag = injector.get(AgentRegistry)
                    await ag.initialize()
                    _ = injector.get(LLMProvider)
                    _ = injector.get(AgentRAGServiceManager)
                    logger.info(
                        f"Pre-warmed tenant-scoped singletons for tenant: {tenant_slug}"
                    )
                except Exception as inner_e:
                    logger.error(
                        f"Failed pre-warming tenant-scoped singletons for {tenant_slug}: {inner_e}"
                    )
                finally:
                    clear_tenant_context()

    except Exception as e:
        logger.error(f"Tenant pre-warm failed: {e}")
