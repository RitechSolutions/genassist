import logging
from typing import Dict
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy import NullPool, create_engine, text
from app.core.config.settings import settings
from app.db.base import Base


from app.db import models  # noqa: F401

logger = logging.getLogger(__name__)


class MultiTenantSessionManager:
    """Manages database sessions for multi-tenant applications"""

    _engines: Dict[str, AsyncEngine] = {}
    _session_factories: Dict[str, async_sessionmaker] = {}


    async def initialize(self):
        """Initialize the multi-tenant session manager"""
        await self.run_db_init_actions("master")


    def get_tenant_engine(self, tenant: str | None = None) -> AsyncEngine:
        """Get or create engine for a specific tenant"""
        logger.debug(f"get_tenant_engine called with tenant_id: {tenant}")
        if tenant is None:
            tenant = "master"
        ktenant = tenant if not settings.BACKGROUND_TASK else tenant + "_background"

        if ktenant not in self._engines:
            tenant_url = settings.get_tenant_database_url(tenant)
            logger.debug(
                    f"Creating new engine for tenant {tenant} with URL: {tenant_url}"
                    )

            if settings.BACKGROUND_TASK:
                # Use NullPool for Celery - no connection pooling
                logger.info(f"🔧 Creating NullPool engine for Celery, tenant: {tenant}")
                self._engines[ktenant] = create_async_engine(
                        tenant_url,
                        echo=False,
                        poolclass=NullPool,  # Creates fresh connection each time
                        pool_pre_ping=True,
                        )

                # Print all engines
                logger.info("=== Current Engines (BACKGROUND_TASK) ===")
                for tenant_name, engine in self._engines.items():
                    logger.info(f"Tenant: {tenant_name}, Engine: {engine}")

            else:
                # Normal pooling for FastAPI
                logger.info(f"🔧 Creating pooled engine for FastAPI, tenant: {tenant}")
                self._engines[ktenant] = create_async_engine(
                        tenant_url,
                        echo=False,
                        future=True,
                        pool_size=settings.DB_POOL_SIZE,
                        max_overflow=settings.DB_MAX_OVERFLOW,
                        pool_timeout=settings.DB_POOL_TIMEOUT,
                        pool_recycle=settings.DB_POOL_RECYCLE,
                        pool_pre_ping=True,
                        )

                # Print all engines
                logger.info("=== Current Engines (FastAPI) ===")
                for tenant_name, engine in self._engines.items():
                    print(f"Tenant: {tenant_name}, Engine: {engine}")

            logger.info(f"Created engine for tenant: {tenant}")

        return self._engines[ktenant]

    def get_tenant_session_factory(self, tenant: str = "master") -> async_sessionmaker:
        """Get or create session factory for a specific tenant"""
        logger.debug(f"get_tenant_session_factory called with tenant: {tenant}")

        if tenant not in self._session_factories:
            engine = self.get_tenant_engine(tenant)
            self._session_factories[tenant] = async_sessionmaker(
                bind=engine,
                expire_on_commit=False,
            )
            logger.info(f"Created session factory for tenant: {tenant}")

        return self._session_factories[tenant]

    async def create_tenant_database(self, tenant: str = "master") -> bool:
        """Create a new tenant database with the same schema as master using Alembic (async version)"""
        try:
            # First create the database (sanitize tenant_id for database name)
            tenant_db_name = settings.get_tenant_database_name(tenant)

            # Use sync engine for database creation (still needed for CREATE DATABASE)
            postgres_url = settings.POSTGRES_URL
            engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")

            with engine.connect() as conn:
                # Check if database exists
                result = conn.execute(
                    text(
                        f"SELECT 1 FROM pg_database WHERE datname = '{tenant_db_name}'"
                    )
                )
                if result.fetchone():
                    logger.info(f"Tenant database '{tenant_db_name}' already exists")
                else:
                    # Create database
                    conn.execute(text(f"CREATE DATABASE {tenant_db_name}"))
                    logger.info(f"Created tenant database: {tenant_db_name}")

            # Now create the schema in the tenant database using async engine
            tenant_url = settings.get_tenant_database_url(tenant)
            logger.info(f"Creating schema for tenant database with URL: {tenant_url}")

            # Create all tables from Base.metadata using async engine
            async_engine = create_async_engine(tenant_url, echo=False)
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info(f"Created all base tables for tenant: {tenant_db_name}")

            # Stamp the database at head to mark it as fully migrated
            # We don't run actual migrations because Base.metadata.create_all() creates tables with current schema
            from alembic.config import Config
            from alembic import command
            import os

            # Point Alembic at our alembic.ini configurations (same pattern as migrations.py)
            # Get the project root relative to this file
            current_file = os.path.abspath(__file__)  # app/db/multi_tenant_session.py
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(current_file))
            )  # project root
            alembic_ini_path = os.path.join(project_root, "alembic.ini")
            logger.info(f"Alembic ini path: {alembic_ini_path}")

            # Use sync URL for Alembic (Alembic commands are sync)
            tenant_url_sync = settings.get_tenant_database_url_sync(tenant)

            # Create Config with the ini file path and set the URL
            alembic_cfg = Config(alembic_ini_path)
            alembic_cfg.set_main_option("sqlalchemy.url", tenant_url_sync)

            # Ensure version table exists and stamp at head
            command.ensure_version(alembic_cfg)
            command.stamp(alembic_cfg, "head")
            logger.info(f"Stamped tenant database at head: {tenant_db_name}")

            # Dispose the async engine
            await async_engine.dispose()

            logger.info(
                f"Created database schema for tenant:  ({tenant}) using Alembic"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create database for tenant {tenant}: {e}")
            return False

    async def seed_tenant_database(self, tenant: str = "master") -> bool:
        """Seed a tenant database with initial data"""
        try:
            # Set tenant context so that dependency injection uses the tenant session
            from app.core.tenant_scope import set_tenant_context, clear_tenant_context

            set_tenant_context(tenant)

            try:
                # Import and run the seed function inside a request scope so DI shares the same session
                from app.db.seed.seed import seed_data
                from app.dependencies.injector import injector
                from fastapi_injector import RequestScopeFactory
                from sqlalchemy.ext.asyncio import AsyncSession

                request_scope_factory = injector.get(RequestScopeFactory)
                async with request_scope_factory.create_scope():
                    # Resolve the request-scoped session so all DI usages share it
                    di_session = injector.get(AsyncSession)
                    try:
                        await seed_data(di_session, injector)
                    finally:
                        try:
                            await di_session.close()
                        except Exception:
                            pass

                logger.info(f"Successfully seeded tenant database: {tenant}")
                return True
            finally:
                # Clear tenant context after seeding
                clear_tenant_context()

        except Exception as e:
            logger.error(f"Failed to seed tenant database {tenant}: {e}")
            # Ensure tenant context is cleared even on error
            from app.core.tenant_scope import clear_tenant_context

            clear_tenant_context()
            return False

    async def close_all(self):
        """Close all database connections"""
        for engine in self._engines.values():
            await engine.dispose()

        logger.info("All database connections closed")

    async def cold_start_db(
        self,
        tenant: str = "master",
    ):
        engine = self.get_tenant_engine(tenant)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        from app.dependencies.injector import injector

        from .seed.seed import seed_data

        session_factory = self.get_tenant_session_factory(tenant)
        async with session_factory() as session:
            await seed_data(session, injector)

    async def get_all_table_names_async(self, tenant: str = "master") -> list[str]:
        """Introspect tables with the *current* session’s bind."""
        session_factory = self.get_tenant_session_factory(tenant)
        async with session_factory() as session:

            def sync_get_names(sync_session):
                from sqlalchemy import inspect

                return inspect(sync_session.connection()).get_table_names()

            return await session.run_sync(sync_get_names)

    async def run_db_init_actions(self, tenant: str = "master"):
        """
        Handles database initialization
        """

        all_table_names = await self.get_all_table_names_async(tenant)
        logger.info(f"Detected tables: {tenant} : {all_table_names}")

        if settings.CREATE_DB or "users" not in all_table_names:
            logger.info("Cold starting DB...")
            await self.cold_start_db(tenant)


# Global instance
multi_tenant_manager = MultiTenantSessionManager()
