#!/usr/bin/env python3
"""
Multi-tenant database management script.

This script helps manage tenant databases in a multi-tenant setup.
It can create, list, and manage tenant databases.
"""

import asyncio
import logging
import sys
import os
from typing import Optional
from sqlalchemy import create_engine, text

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config.settings import settings
from app.db.multi_tenant_session import multi_tenant_manager
from app.services.tenant import TenantService
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_db_identifier(identifier: str) -> str:
    """
    Validate and sanitize a PostgreSQL database identifier to prevent SQL injection.
    PostgreSQL identifiers must start with a letter or underscore and contain only
    alphanumeric characters and underscores.
    Raises ValueError if the identifier is invalid.
    """
    if not identifier:
        raise ValueError("Database identifier cannot be empty")

    # PostgreSQL identifier pattern: starts with letter/underscore, followed by alphanumeric/underscore
    # Max length is 63 characters
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]{0,62}$', identifier):
        raise ValueError(f"Invalid database identifier: {identifier}. Must start with a letter or underscore and contain only alphanumeric characters and underscores.")

    return identifier


async def create_master_database():
    """Create the master database for tenant management"""
    try:
        # Create master database - validate the name from settings
        master_db_name = validate_db_identifier(settings.DB_NAME)

        # Connect to postgres database to create the master database
        postgres_url = settings.POSTGRES_URL
        engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")

        with engine.connect() as conn:
            # Check if database exists using parameterized query
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": master_db_name}
            )
            if result.fetchone():
                logger.info(f"Master database '{master_db_name}' already exists")
            else:
                # Create database - DDL doesn't support parameters, but name is validated
                conn.execute(text(f'CREATE DATABASE "{master_db_name}"'))
                logger.info(f"Created master database: {master_db_name}")

        # Initialize multi-tenant manager
        await multi_tenant_manager.initialize()

        # Create schema in master database using Alembic migrations
        master_url = settings.DATABASE_URL_SYNC
        from migrations import run_migrations_for_database

        success = run_migrations_for_database(master_url, master_db_name)

        if success:
            logger.info("Master database setup complete")
            return True
        else:
            logger.error("Failed to run migrations for master database")
            return False

    except Exception as e:
        logger.error(f"Failed to create master database: {e}")
        return False


async def create_tenant(
    tenant_name: str,
    tenant_slug: str,
    description: Optional[str] = None,
    seed_data: bool = True,
):
    """Create a new tenant"""
    try:
        # Validate tenant_slug to prevent SQL injection in downstream database operations
        validated_slug = validate_db_identifier(tenant_slug)

        # Ensure settings are properly loaded
        from app.core.config.settings import settings

        print(f"DEBUG: MULTI_TENANT_ENABLED = {settings.MULTI_TENANT_ENABLED}")

        await multi_tenant_manager.initialize()

        # Get injector for seeding if requested
        injector = None
        if seed_data:
            try:
                from app.dependencies.injector import injector as app_injector

                injector = app_injector
            except Exception as e:
                logger.warning(f"Could not get injector for seeding: {e}")
                logger.info("Creating tenant without seeding...")
                seed_data = False

        tenant_service = TenantService()
        tenant = await tenant_service.create_tenant(
            name=tenant_name,
            slug=validated_slug,
            description=description,
            injector=injector,
        )

        if tenant:
            logger.info(f"Successfully created tenant: {tenant_name} ({validated_slug})")
            if seed_data and injector:
                logger.info(f"Tenant database seeded with initial data")
            return True
        else:
            logger.error(f"Failed to create tenant: {tenant_name}")
            return False

    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        return False


async def list_tenants():
    """List all tenants"""
    try:
        await multi_tenant_manager.initialize()

        tenant_service = TenantService()
        tenants = await tenant_service.get_all_tenants()

        if not tenants:
            logger.info("No tenants found")
            return

        logger.info("Active tenants:")
        for tenant in tenants:
            logger.info(f"  - {tenant.name} ({tenant.slug}) - {tenant.database_name}")

    except Exception as e:
        logger.error(f"Error listing tenants: {e}")


async def create_tenant_database(tenant_slug: str):
    """Create database for an existing tenant"""
    try:
        # Validate tenant_slug to prevent SQL injection
        validated_slug = validate_db_identifier(tenant_slug)
        validated_db_name = validate_db_identifier(settings.DB_NAME)

        await multi_tenant_manager.initialize()

        # Create the tenant database first - validate the combined name
        tenant_db_name = validate_db_identifier(f"{validated_db_name}_tenant_{validated_slug}")
        postgres_url = settings.POSTGRES_URL
        engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")

        with engine.connect() as conn:
            # Check if database exists using parameterized query
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": tenant_db_name}
            )
            if result.fetchone():
                logger.info(f"Tenant database '{tenant_db_name}' already exists")
            else:
                # Create database - DDL doesn't support parameters, but name is validated
                conn.execute(text(f'CREATE DATABASE "{tenant_db_name}"'))
                logger.info(f"Created tenant database: {tenant_db_name}")

        # Now create the schema in the tenant database
        # Input is validated via validate_db_identifier() at the start of this function
        # snyk-ignore: CWE-89 - Input validated via validate_db_identifier() above
        success = await multi_tenant_manager.create_tenant_database(
            validated_slug, validated_slug  # nosec B608 - input validated above
        )
        if success:
            logger.info(f"Successfully created database for tenant: {validated_slug}")
        else:
            logger.error(f"Failed to create database for tenant: {validated_slug}")

    except Exception as e:
        logger.error(f"Error creating tenant database: {e}")


def print_usage():
    """Print usage information"""
    print(
        """
Multi-tenant Database Management Script

Usage:
    python tenant_manager.py <command> [options]

Commands:
    init                    - Initialize master database
    create <name> <slug>    - Create a new tenant (with seeding by default)
    list                    - List all tenants
    create-db <slug>        - Create database for existing tenant
    help                    - Show this help message

Options:
    --no-seed              - Skip seeding when creating tenant

Examples:
    python tenant_manager.py init
    python tenant_manager.py create "Acme Corp" "acme"
    python tenant_manager.py create "Test Corp" "test" "Test tenant" --no-seed
    python tenant_manager.py list
    python tenant_manager.py create-db acme
    """
    )


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1].lower()

    if command == "init":
        success = await create_master_database()
        sys.exit(0 if success else 1)

    elif command == "create":
        if len(sys.argv) < 4:
            logger.error("Usage: create <name> <slug> [description] [--no-seed]")
            sys.exit(1)

        name = sys.argv[2]
        slug = sys.argv[3]
        description = (
            sys.argv[4]
            if len(sys.argv) > 4 and not sys.argv[4].startswith("--")
            else None
        )
        seed_data = "--no-seed" not in sys.argv

        success = await create_tenant(name, slug, description, seed_data)
        sys.exit(0 if success else 1)

    elif command == "list":
        await list_tenants()

    elif command == "create-db":
        if len(sys.argv) < 3:
            logger.error("Usage: create-db <slug>")
            sys.exit(1)

        slug = sys.argv[2]
        await create_tenant_database(slug)

    elif command == "help":
        print_usage()

    else:
        logger.error(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
