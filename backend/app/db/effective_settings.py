"""Reports what the database actually enforces next to what the app asked for."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# setting is in milliseconds; reset_val is the server-side default behind any session override.
STATEMENT_TIMEOUT_QUERY = text(
    "SELECT setting, reset_val, source FROM pg_settings WHERE name = 'statement_timeout'"
)


async def log_effective_statement_timeout(engine: AsyncEngine) -> None:
    """Log the configured, effective and server-default statement_timeout. Never raises."""
    try:
        async with engine.connect() as connection:
            row = (await connection.execute(STATEMENT_TIMEOUT_QUERY)).one()
        effective_seconds = int(row.setting) / 1000
        server_default_seconds = int(row.reset_val) / 1000
    except Exception as error:
        logger.warning("Could not read the effective statement_timeout: %s", error)
        return

    logger.info(
        "DB statement_timeout: configured=%ss effective=%ss source=%s server_default=%ss",
        settings.DB_STATEMENT_TIMEOUT,
        effective_seconds,
        row.source,
        server_default_seconds,
    )
