import logging
import os
import time
from sqlalchemy import engine_from_config, inspect
from sqlalchemy.exc import OperationalError


logger = logging.getLogger(__name__)

# Postgres SQLSTATE raised when lock_timeout expires
LOCK_NOT_AVAILABLE = "55P03"
RETRY_BASE_DELAY_SECONDS = 2
RETRY_MAX_DELAY_SECONDS = 32


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


class MigrationLockRetriesExhausted(RuntimeError):
    """A migration could not take its lock within the configured retries."""


def _is_lock_timeout(error: Exception) -> bool:
    return getattr(getattr(error, "orig", None), "pgcode", None) == LOCK_NOT_AVAILABLE


def upgrade_head_with_lock_retry(alembic_cfg, database_name: str) -> None:
    """
    Run `alembic upgrade head`, retrying only when a migration could not take its lock.
    Each migration commits on its own, so a retry resumes at the migration that failed.
    """
    from alembic import command
    from app.core.config.settings import settings

    attempts = settings.MIGRATION_LOCK_RETRIES + 1
    for attempt in range(1, attempts + 1):
        try:
            command.upgrade(alembic_cfg, "head")
            return
        except OperationalError as error:
            if not _is_lock_timeout(error):
                raise
            is_last_attempt = attempt == attempts
            if is_last_attempt:
                raise MigrationLockRetriesExhausted(
                    f"Migration for {database_name} could not take its lock after {attempts} attempts"
                ) from error
            delay = min(RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1), RETRY_MAX_DELAY_SECONDS)
            logger.warning(
                "Migration for %s could not take its lock (attempt %s/%s), retrying in %ss",
                database_name,
                attempt,
                attempts,
                delay,
            )
            time.sleep(delay)


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

    from alembic.config import Config

    # Point Alembic at our alembic.ini configurations
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    # Extract database name from URL for logging
    import re

    db_name_match = re.search(r"/([^/?]+)(\?|$)", url)
    db_name = db_name_match.group(1) if db_name_match else "unknown"

    logger.info(f"Running database migrations for: {db_name}")
    upgrade_head_with_lock_retry(alembic_cfg, db_name)
    logger.info(f"Migrations complete for: {db_name}")
    return True


def run_migrations_for_database(url: str, database_name: str) -> bool:
    """
    Programmatically executes `alembic upgrade head` for a specific database.
    """
    try:
        from alembic.config import Config

        # Point Alembic at our alembic.ini configurations
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", url)

        logger.info(f"Running database migrations for {database_name}...")
        upgrade_head_with_lock_retry(alembic_cfg, database_name)
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

        result = session.execute(text("SELECT slug FROM tenants WHERE is_active is True")).fetchall()
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
                logger.info(
                    f"Starting migrations for tenant:({tenant})"
                )

                # Get tenant database URL (sync version for Alembic)
                tenant_url = settings.get_tenant_database_url_sync(tenant)

                # Run migrations for this tenant
                success = run_migrations(tenant_url)
                if success:
                    logger.info(
                        f"✓ Migrations completed for tenant: ({tenant})"
                    )
                    success_count += 1
                else:
                    logger.warning(
                        f"✗ Migrations failed for tenant: ({tenant})"
                    )
                    failed_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to run migrations for tenant ({tenant}): {e}"
                )
                failed_count += 1

        logger.info(
            f"Tenant migrations complete: {success_count} successful, {failed_count} failed"
        )
        return failed_count == 0

    except Exception as e:
        logger.error(f"Error running migrations for all tenants: {e}")
        return False


# A database host that does not answer must not stall the schema wait past its deadline
_CONNECT_ARGS = {"connect_timeout": 10}


class SchemaNotReadyError(RuntimeError):
    """The database did not reach this code's migration head in time."""


def _code_head_revisions():
    """The head revision(s) of the migrations shipped with this code, and their script directory."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    here = os.path.dirname(os.path.abspath(__file__))
    alembic_cfg = Config(os.path.join(here, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(here, "alembic"))
    script = ScriptDirectory.from_config(alembic_cfg)
    return set(script.get_heads()), script


def _database_revisions(url: str) -> set:
    """The revision(s) recorded in a database's alembic_version table."""
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    engine = create_engine(url, poolclass=NullPool, connect_args=_CONNECT_ARGS)
    try:
        with engine.connect() as connection:
            return set(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()


def _active_tenant_urls() -> list:
    from app.core.config.settings import settings
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    engine = create_engine(
        settings.get_tenant_database_url_sync(), poolclass=NullPool, connect_args=_CONNECT_ARGS
    )
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT slug FROM tenants WHERE is_active is True")).fetchall()
    finally:
        engine.dispose()
    return [(f"tenant:({row[0]})", settings.get_tenant_database_url_sync(row[0])) for row in rows]


def _is_schema_ready(current: set, heads: set, script) -> bool:
    """
    True when the database is at this code's head, or ahead of it.
    A revision this code does not know comes from a newer release (for example
    during a rollback); the schema is then newer, not older, so it is not waited on.
    """
    if not current:
        return False
    known = {revision.revision for revision in script.walk_revisions()}
    if not current <= known:
        return True
    return current == heads


MAIN_DATABASE = "main"


def _is_database_behind(name: str, url: str, heads: set, script) -> bool:
    try:
        current = _database_revisions(url)
    except Exception as error:
        logger.info("Schema check for %s could not read its revision yet: %s", name, error)
        return True
    return not _is_schema_ready(current, heads, script)


def _databases_behind(heads: set, script) -> list:
    """Names of the databases that are not at this code's head yet."""
    from app.core.config.settings import settings

    behind = []
    if _is_database_behind(MAIN_DATABASE, settings.DATABASE_URL_SYNC, heads, script):
        behind.append(MAIN_DATABASE)
    if not settings.MULTI_TENANT_ENABLED:
        return behind

    try:
        tenants = _active_tenant_urls()
    except Exception as error:
        logger.info("Schema check could not list the tenants yet: %s", error)
        return behind + ["tenants"]
    for name, url in tenants:
        if _is_database_behind(name, url, heads, script):
            behind.append(name)
    return behind


# Set by the first worker that gave up waiting on stale tenants for a migration head.
# Later worker starts on the same head (crash restarts, scale-out) then skip the tenant
# wait instead of pausing every tenant's jobs again. A new release has a new head.
TENANT_WAIT_GIVEN_UP_KEY = "genassist:schema_gate:tenant_wait_given_up:{head}"
TENANT_WAIT_GIVEN_UP_TTL_SECONDS = 7 * 24 * 3600


def _redis_client():
    import redis
    from app.core.config.settings import settings

    return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=5, socket_timeout=5)


def _tenant_wait_given_up(head_names: str) -> bool:
    """Whether a worker already gave up waiting on stale tenants for this head."""
    try:
        return bool(_redis_client().exists(TENANT_WAIT_GIVEN_UP_KEY.format(head=head_names)))
    except Exception as error:
        logger.info("Schema check could not read the tenant wait marker; waiting as usual: %s", error)
        return False


def _remember_tenant_wait_given_up(head_names: str) -> None:
    try:
        _redis_client().set(
            TENANT_WAIT_GIVEN_UP_KEY.format(head=head_names),
            "1",
            ex=TENANT_WAIT_GIVEN_UP_TTL_SECONDS,
        )
    except Exception as error:
        logger.warning("Schema check could not save the tenant wait marker: %s", error)


def wait_for_schema_at_head(timeout_seconds: int, interval_seconds: int) -> None:
    """
    Block until the databases are at the migration head this code ships with.

    Celery workers start alongside the API, which is the process that runs the
    migrations. Without this wait they can query new columns before the migration
    has added them (see migration 00126, files_upload_sessions.upload_purpose).

    After timeout_seconds:
    * main database still behind -> SchemaNotReadyError, so the container exits and
      is restarted instead of running against an old schema;
    * only tenant databases behind -> log an error naming them and start anyway.
      The API treats a failed tenant migration as non-fatal, and one broken tenant
      must not stop background jobs for every other tenant. The give-up is recorded
      in Redis for this head, so later worker starts do not wait on those tenants again.
    """
    heads, script = _code_head_revisions()
    head_names = ", ".join(sorted(heads))
    tenant_wait_given_up = _tenant_wait_given_up(head_names)
    deadline = time.monotonic() + timeout_seconds
    while True:
        behind = _databases_behind(heads, script)
        if not behind:
            logger.info("Database schema is at head %s; starting.", head_names)
            return
        only_tenants_behind = MAIN_DATABASE not in behind
        if only_tenants_behind and tenant_wait_given_up:
            logger.error(
                "Tenant databases are still not at head %s; an earlier worker already "
                "waited for them, so starting now. Tasks for these tenants may fail "
                "until their migrations run: %s",
                head_names,
                ", ".join(behind),
            )
            return
        if time.monotonic() >= deadline:
            if not only_tenants_behind:
                raise SchemaNotReadyError(
                    f"Database schema is not at head {head_names} after {timeout_seconds}s; "
                    f"behind: {', '.join(behind)}. Check that the migrations ran."
                )
            _remember_tenant_wait_given_up(head_names)
            logger.error(
                "Tenant databases are not at head %s after %ss; starting anyway. "
                "Tasks for these tenants may fail until their migrations run: %s",
                head_names,
                timeout_seconds,
                ", ".join(behind),
            )
            return
        logger.info(
            "Waiting for migrations to reach head %s (behind: %s)",
            head_names,
            ", ".join(behind),
        )
        time.sleep(interval_seconds)


def stamp_head_for_all_tenants() -> bool:
    """
    Programmatically executes `alembic stamp head` for the main database and all
    active tenant databases.

    Unlike run_migrations_for_all_tenants, this does NOT run any migration code –
    it only records the head revision in each `alembic_version` table. Use it when
    the schema is already in the head state and only the recorded revision needs
    correcting (e.g. after resolving a migration-history/head conflict). Running an
    upgrade in that situation would re-execute already-applied DDL and fail.
    """
    from app.core.config.settings import settings
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from alembic import command
    from alembic.config import Config

    def _stamp(url: str, database_name: str) -> None:
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", url)
        logger.info(f"Stamping head for: {database_name}")
        command.stamp(alembic_cfg, "head")
        logger.info(f"Stamp head complete for: {database_name}")

    try:
        # Main database
        _stamp(settings.DATABASE_URL_SYNC, "main")

        # Check if multi-tenancy is enabled
        if not settings.MULTI_TENANT_ENABLED:
            logger.info("Multi-tenancy is disabled, skipping tenant stamps")
            return True

        DATABASE_URL = settings.get_tenant_database_url_sync()

        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        result = session.execute(text("SELECT slug FROM tenants WHERE is_active is True")).fetchall()
        tenants = [r[0] for r in result]

        if not tenants:
            logger.info("No active tenants found")
            return True

        logger.info(f"Found {len(tenants)} active tenant(s)")

        success_count = 0
        failed_count = 0

        # Stamp head for each tenant
        for tenant in tenants:
            try:
                tenant_url = settings.get_tenant_database_url_sync(tenant)
                _stamp(tenant_url, f"tenant:({tenant})")
                success_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to stamp head for tenant ({tenant}): {e}"
                )
                failed_count += 1

        logger.info(
            f"Tenant stamps complete: {success_count} successful, {failed_count} failed"
        )

        return failed_count == 0

    except Exception as e:
        logger.error(f"Error stamping head for all tenants: {e}")
        return False

