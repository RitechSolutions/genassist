"""
Permission management module.

Provides automatic permission discovery, constants, and database synchronization.
"""
import logging
from typing import Optional, Set
from app.core.permissions.constants import get_all_permission_constants

logger = logging.getLogger(__name__)


async def sync_permissions_on_startup() -> None:
    """
    Discover and sync permissions to all tenant databases on application startup.

    This function:
    1. Discovers all permissions from routes and constants
    2. Syncs them to the master database
    3. If multi-tenancy is enabled, syncs to all active tenant databases
    4. Logs statistics and warnings

    Args:
        app: FastAPI application instance

    Raises:
        Exception: If sync fails (logged but doesn't stop startup)
    """
    logger.info("Starting permission synchronization...")

    try:
        from app.core.permissions.sync import sync_permissions_to_db
        from app.db.multi_tenant_session import multi_tenant_manager
        from app.core.config.settings import settings

        # Discover all permissions from routes and constants
        all_permissions = discover_all_permissions()
        logger.info(f"Discovered {len(all_permissions)} total permissions")

        # Sync to master database
        logger.info("Syncing permissions to MASTER database...")
        master_session_factory = multi_tenant_manager.get_tenant_session_factory("master")
        async with master_session_factory() as session:
            master_stats = await sync_permissions_to_db(
                session,
                all_permissions,
                update_existing=False
            )

        logger.info(
            f"✓ Master database sync complete: "
            f"{master_stats['added']} added, {master_stats['updated']} updated, "
            f"{master_stats['orphaned']} orphaned"
        )

        # If multi-tenancy is enabled, sync to all tenant databases
        if settings.MULTI_TENANT_ENABLED:
            await _sync_permissions_to_all_tenants(all_permissions, multi_tenant_manager)
        else:
            logger.info("Multi-tenancy disabled, skipping tenant database sync")

        logger.info("✓ Permission synchronization complete")

    except Exception as e:
        logger.error(f"Failed to sync permissions: {e}", exc_info=True)
        # Don't fail startup if permission sync fails
        logger.warning("Continuing startup despite permission sync failure")
        # Don't re-raise to prevent startup failure


async def _sync_permissions_to_all_tenants(all_permissions: set, multi_tenant_manager) -> None:
    """
    Sync permissions to all active tenant databases.

    Args:
        all_permissions: Set of all discovered permissions
        multi_tenant_manager: Multi-tenant session manager instance
    """
    from sqlalchemy import text

    logger.info("Syncing permissions to all tenant databases...")

    try:
        # Get all active tenants from master database
        master_session_factory = multi_tenant_manager.get_tenant_session_factory("master")
        async with master_session_factory() as session:
            result = await session.execute(
                text("SELECT slug, name FROM tenants WHERE is_active = true")
            )
            tenants = result.fetchall()

        if not tenants:
            logger.info("No active tenants found")
            return

        logger.info(f"Found {len(tenants)} active tenant(s)")

        success_count = 0
        failed_count = 0

        # Sync permissions to each tenant database
        for tenant_slug, tenant_name in tenants:
            try:
                await sync_permissions_for_tenant(
                    tenant_slug=tenant_slug,
                    tenant_name=tenant_name,
                    all_permissions=all_permissions,
                    update_existing=False,
                    verbose=False,  # Less verbose for tenant syncs
                )
                success_count += 1

            except Exception as e:
                logger.error(f"  ✗ Failed to sync permissions to tenant {tenant_slug}: {e}")
                failed_count += 1

        logger.info(
            f"Tenant sync complete: {success_count} successful, {failed_count} failed"
        )

    except Exception as e:
        logger.error(f"Error syncing permissions to tenants: {e}", exc_info=True)


async def sync_permissions_for_tenant(
    tenant_slug: str,
    tenant_name: Optional[str] = None,
    all_permissions: Optional[Set[str]] = None,
    update_existing: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Sync permissions to a single tenant database.

    This can be called from other services to ensure a specific tenant is
    up-to-date with the latest permission definitions.

    Args:
        tenant_slug: The tenant slug to sync.
        tenant_name: Optional human-readable tenant name for logging.
        all_permissions: Optional pre-discovered permission set. If not provided,
            permissions will be discovered automatically.
        update_existing: Whether to update existing permissions.
        verbose: Whether to use verbose logging in the underlying sync.

    Returns:
        A stats dictionary from sync_permissions_to_db with keys:
        "added", "updated", and "orphaned".
    """
    from app.core.permissions.sync import sync_permissions_to_db
    from app.db.multi_tenant_session import multi_tenant_manager

    if all_permissions is None:
        all_permissions = discover_all_permissions()

    display_name = f"{tenant_name} ({tenant_slug})" if tenant_name else tenant_slug
    logger.info(f"Syncing permissions to tenant: {display_name}")

    tenant_session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_slug)
    async with tenant_session_factory() as session:
        stats = await sync_permissions_to_db(
            session,
            all_permissions,
            update_existing=update_existing,
            verbose=verbose,
        )

    logger.info(
        f"  ✓ Tenant {tenant_slug}: "
        f"{stats['added']} added, {stats['updated']} updated, "
        f"{stats['orphaned']} orphaned"
    )

    return stats


def discover_all_permissions() -> Set[str]:
    """
    Discover all permissions from constants.

    This is the main entry point for permission discovery.
    Permissions must be defined in app/core/permissions/constants.py

    Returns:
        Set of all discovered permission strings
    """
    # Get permissions from constants (single source of truth)
    all_permissions = get_all_permission_constants()
    logger.info(f"Found {len(all_permissions)} permissions in constants")

    return all_permissions