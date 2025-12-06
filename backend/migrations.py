import logging
import os
from sqlalchemy import engine_from_config, inspect


logger = logging.getLogger(__name__)


def alembic_ensure_version() -> None:
    """
    Programmatically executes `alembic ensure_version`.
    """
    from alembic import command
    from alembic.config import Config

    # Point Alembic at our alembic.ini configurations
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))

    command.ensure_version(alembic_cfg)
    logger.info("Alembic ensure_version complete.")


def alembic_stamp_head() -> None:
    """
    Programmatically executes `alembic stamp head`.
    """
    from alembic import command
    from alembic.config import Config

    # Point Alembic at our alembic.ini configurations
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))

    command.stamp(alembic_cfg, "head")
    logger.info("Alembic stamp head complete.")


def get_table_names(url):
    from alembic.config import Config

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    config_section = alembic_cfg.get_section(alembic_cfg.config_ini_section)

    engine = engine_from_config(config_section, prefix="sqlalchemy.")
    inspector = inspect(engine)
    all_table_names = inspector.get_table_names()
    return all_table_names


def run_migrations(url) -> bool:
    """
    Programmatically executes `alembic upgrade head`.
    The call is idempotent – if you're already at head, nothing happens.
    """

    all_table_names = get_table_names(url)
    if (
        os.getenv("AUTO_MIGRATE", "true").lower() == "false"
        or "users" not in all_table_names
    ):
        logger.info("AUTO_MIGRATE is disabled – skipping Alembic.")
        from alembic.config import Config

        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", url)

        from alembic import command

        command.ensure_version(alembic_cfg)
        command.stamp(alembic_cfg, "head")
        return True

    from alembic import command
    from alembic.config import Config

    # Point Alembic at our alembic.ini configurations
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    # Extract database name from URL for logging
    import re

    db_name_match = re.search(r"/([^/?]+)(\?|$)", url)
    db_name = db_name_match.group(1) if db_name_match else "unknown"

    logger.info(f"Running database migrations for: {db_name}")
    command.upgrade(alembic_cfg, "head")
    logger.info(f"Migrations complete for: {db_name}")
    return True


def run_migrations_for_database(url: str, database_name: str) -> bool:
    """
    Programmatically executes `alembic upgrade head` for a specific database.
    """
    try:
        from alembic import command
        from alembic.config import Config

        # Point Alembic at our alembic.ini configurations
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", url)

        logger.info(f"Running database migrations for {database_name}...")
        command.upgrade(alembic_cfg, "head")
        logger.info(f"Migrations complete for {database_name}.")
        return True
    except Exception as e:
        logger.error(f"Failed to run migrations for {database_name}: {e}")
        return False


def run_migrations_for_all_tenants() -> bool:
    """
    Programmatically executes `alembic upgrade head` for all active tenant databases.
    This function is similar to run_migrations but runs migrations for each tenant.
    """
    from app.core.config.settings import settings
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    """Async helper to get all tenants and run migrations"""
    try:
        # Check if multi-tenancy is enabled
        if not settings.MULTI_TENANT_ENABLED:
            logger.info("Multi-tenancy is disabled, skipping tenant migrations")
            return True

        DATABASE_URL = settings.get_tenant_database_url_sync()

        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        result = session.execute(
            text("SELECT slug FROM tenants WHERE is_active is True")
        ).fetchall()
        tenants = [r[0] for r in result]

        if not tenants:
            logger.info("No active tenants found")
            return True

        logger.info(f"Found {len(tenants)} active tenant(s)")

        success_count = 0
        failed_count = 0

        # Run migrations for each tenant
        for tenant in tenants:
            try:
                logger.info(f"Starting migrations for tenant:({tenant})")

                # Get tenant database URL (sync version for Alembic)
                tenant_url = settings.get_tenant_database_url_sync(tenant)

                # Run migrations for this tenant
                success = run_migrations(tenant_url)
                if success:
                    logger.info(f"✓ Migrations completed for tenant: ({tenant})")
                    success_count += 1
                else:
                    logger.warning(f"✗ Migrations failed for tenant: ({tenant})")
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to run migrations for tenant ({tenant}): {e}")
                failed_count += 1

        logger.info(
            f"Tenant migrations complete: {success_count} successful, {failed_count} failed"
        )

        return failed_count == 0

    except Exception as e:
        logger.error(f"Error running migrations for all tenants: {e}")
        return False
