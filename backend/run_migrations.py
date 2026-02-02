"""
Dedicated script for running database migrations.
This script is intended to be run in an init container before the main application starts.
"""
import os
import sys
import logging

# Prefer HF_HOME over deprecated TRANSFORMERS_CACHE (Transformers v5+).
# Must run before any code that imports transformers/sentence_transformers.
if "TRANSFORMERS_CACHE" in os.environ:
    if "HF_HOME" not in os.environ:
        os.environ["HF_HOME"] = os.environ["TRANSFORMERS_CACHE"]
    del os.environ["TRANSFORMERS_CACHE"]

from app.core.config.settings import settings
from migrations import run_migrations, run_migrations_for_all_tenants

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Run migrations for the main database and all tenant databases.
    Exits with code 1 if migrations fail.
    """
    try:
        logger.info("Starting database migrations...")

        # Set Alembic env var
        os.environ.setdefault("ALEMBIC_SKIP_FILECONFIG", "1")

        # Run main database migrations
        logger.info("Running main database migrations...")
        success = run_migrations(settings.DATABASE_URL_SYNC)
        if not success:
            logger.error("Main database migrations failed")
            sys.exit(1)

        # Run tenant database migrations
        logger.info("Running tenant database migrations...")
        success = run_migrations_for_all_tenants()
        if not success:
            logger.error("Tenant database migrations failed")
            sys.exit(1)

        logger.info("All database migrations completed successfully")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Migration script failed with error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
