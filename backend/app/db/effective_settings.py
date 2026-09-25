"""Reports what the database actually enforces next to what the app asked for."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# setting is in milliseconds.
STATEMENT_TIMEOUT_QUERY = text(
    "SELECT setting, source FROM pg_settings WHERE name = 'statement_timeout'"
)


async def log_effective_statement_timeout(engine: AsyncEngine) -> None:
    """Log the configured and effective statement_timeout with its source. Never raises."""
    try:
        async with engine.connect() as connection:
            row = (await connection.execute(STATEMENT_TIMEOUT_QUERY)).one()
        effective_seconds = int(row.setting) / 1000
    except Exception as error:
        logger.warning("Could not read the effective statement_timeout: %s", error)
        return

    logger.info(
        "DB statement_timeout: configured=%ss effective=%ss source=%s",
        settings.DB_STATEMENT_TIMEOUT,
        effective_seconds,
        row.source,
    )
