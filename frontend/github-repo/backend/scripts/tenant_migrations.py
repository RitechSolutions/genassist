#!/usr/bin/env python3
"""
Multi-tenant migration script.

This script applies migrations to all tenant databases in a multi-tenant setup.
"""

import asyncio
import logging
import subprocess
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.tenant import TenantRepository
from app.core.config.settings import settings
from app.db.multi_tenant_session import multi_tenant_manager
from app.services.tenant import TenantService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def apply_migrations_to_tenant(tenant_slug: str):
    """Apply migrations to a specific tenant database"""
    try:
        tenant_url = settings.get_tenant_database_url_sync(tenant_slug)

        # Run alembic upgrade head for the tenant database
        cmd = ["alembic", "-x", f"tenant_url={tenant_url}", "upgrade", "head"]

        logger.info(f"Applying migrations to tenant: {tenant_slug}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"Successfully applied migrations to tenant: {tenant_slug}")
            return True
        else:
            logger.error(
                f"Failed to apply migrations to tenant {tenant_slug}: {result.stderr}"
            )
            return False

    except Exception as e:
        logger.error(f"Error applying migrations to tenant {tenant_slug}: {e}")
        return False


async def apply_migrations_to_all_tenants():
    """Apply migrations to all tenant databases"""
    try:
        await multi_tenant_manager.initialize()

        session_factory = multi_tenant_manager.get_tenant_session_factory("master")
        async with session_factory() as session:
            repository = TenantRepository(session)
            tenant_service = TenantService(repository)
            tenants = await tenant_service.get_all_tenants()

            if not tenants:
                logger.info("No tenants found")
                return

            logger.info(f"Found {len(tenants)} tenants to migrate")

            success_count = 0
            for tenant in tenants:
                success = await apply_migrations_to_tenant(tenant.slug)
                if success:
                    success_count += 1

            logger.info(
                f"Migration completed: {success_count}/{len(tenants)} tenants migrated successfully"
            )

    except Exception as e:
        logger.error(f"Error applying migrations to all tenants: {e}")


async def apply_migrations_to_master():
    """Apply migrations to master database"""
    try:
        master_url = settings.DATABASE_URL_SYNC

        # Run alembic upgrade head for the master database
        cmd = ["alembic", "-x", f"master_url={master_url}", "upgrade", "head"]

        logger.info("Applying migrations to master database")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("Successfully applied migrations to master database")
            return True
        else:
            logger.error(
                f"Failed to apply migrations to master database: {result.stderr}"
            )
            return False

    except Exception as e:
        logger.error(f"Error applying migrations to master database: {e}")
        return False


def print_usage():
    """Print usage information"""
    print(
        """
Multi-tenant Migration Script

Usage:
    python tenant_migrations.py <command> [options]

Commands:
    master                  - Apply migrations to master database
    tenant <slug>           - Apply migrations to specific tenant
    all                     - Apply migrations to all tenants
    help                    - Show this help message

Examples:
    python tenant_migrations.py master
    python tenant_migrations.py tenant acme
    python tenant_migrations.py all
    """
    )


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1].lower()

    if command == "master":
        success = await apply_migrations_to_master()
        sys.exit(0 if success else 1)

    elif command == "tenant":
        if len(sys.argv) < 3:
            logger.error("Usage: tenant <slug>")
            sys.exit(1)

        slug = sys.argv[2]
        success = await apply_migrations_to_tenant(slug)
        sys.exit(0 if success else 1)

    elif command == "all":
        await apply_migrations_to_all_tenants()

    elif command == "help":
        print_usage()

    else:
        logger.error(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
