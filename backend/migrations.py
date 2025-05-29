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

def run_migrations(url) -> None:
    """
    Programmatically executes `alembic upgrade head`.
    The call is idempotent – if you're already at head, nothing happens.
    """

    all_table_names = get_table_names(url)
    if os.getenv("AUTO_MIGRATE", "true").lower() == "false" or "users" not in all_table_names:
        logger.info("AUTO_MIGRATE is disabled – skipping Alembic.")
        alembic_ensure_version()
        alembic_stamp_head()
        return

    from alembic import command
    from alembic.config import Config

    # Point Alembic at our alembic.ini configurations
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))

    logger.info("Running database migrations …")
    command.upgrade(alembic_cfg, "head")
    logger.info("Migrations complete.")