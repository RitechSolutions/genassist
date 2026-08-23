import logging
import os
from sqlalchemy import create_engine, engine_from_config, inspect, text
from sqlalchemy.pool import NullPool


logger = logging.getLogger(__name__)

_EVENTS_TABLE = "llm_usage_events"
_RATES_TABLE = "llm_cost_rates"
_CACHE_TOKEN_COLUMNS = ("cache_read_tokens", "cache_creation_tokens")
_CACHE_RATE_COLUMNS = ("cache_read_per_1k", "cache_creation_per_1k")
LLM_USAGE_NON_NEGATIVE_CONSTRAINT = "ck_llm_usage_events_non_negative"
LLM_USAGE_NON_NEGATIVE_DEF = (
    "CHECK (((input_tokens >= 0) AND (output_tokens >= 0)"
    " AND (total_tokens >= 0) AND (call_index >= 0)"
    " AND (cache_read_tokens >= 0) AND (cache_creation_tokens >= 0)))"
)


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


def master_database_is_initialized() -> bool:
    """Whether the master database has a schema yet"""
    from app.core.config.settings import settings

    try:
        return "tenants" in get_table_names(settings.get_tenant_database_url_sync())
    except Exception as e:
        logger.error(f"Could not inspect the master database: {e}")
        return False


def active_tenant_slugs() -> list:
    """Slugs of every active tenant, read from the master database"""
    from app.core.config.settings import settings
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.get_tenant_database_url_sync())
    try:
        session = sessionmaker(bind=engine)()
        try:
            result = session.execute(text("SELECT slug FROM tenants WHERE is_active is True")).fetchall()
            return [r[0] for r in result]
        finally:
            session.close()
    finally:
        engine.dispose()


def run_migrations_for_all_tenants() -> bool:
    """
    Programmatically executes `alembic upgrade head` for all active tenant databases.
    This function is similar to run_migrations but runs migrations for each tenant.
    """
    from app.core.config.settings import settings

    """Async helper to get all tenants and run migrations"""
    try:
        # Check if multi-tenancy is enabled
        if not settings.MULTI_TENANT_ENABLED:
            logger.info("Multi-tenancy is disabled, skipping tenant migrations")
            return True

        if not master_database_is_initialized():
            logger.info("Master database is not initialized yet, skipping tenant migrations")
            return True

        tenants = active_tenant_slugs()

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


def _normalized_default(default: str) -> str:
    text_value = (default or "").strip()
    if "::" in text_value:
        text_value = text_value.split("::", 1)[0].strip()
    return text_value.strip("'")


def _column_facts(connection, table: str) -> dict:
    rows = connection.execute(
        text(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,"
            " pg_get_expr(d.adbin, d.adrelid)"
            " FROM pg_attribute a"
            " LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum"
            " WHERE a.attrelid = to_regclass(:table) AND a.attnum > 0 AND NOT a.attisdropped"
        ),
        {"table": table},
    ).fetchall()
    return {row[0]: (row[1], bool(row[2]), row[3]) for row in rows}


def _llm_usage_schema_problems(connection) -> list:
    """Everything wrong with this database's LLM-usage schema, empty when it is sound"""
    problems = []
    columns = {table: _column_facts(connection, table) for table in (_EVENTS_TABLE, _RATES_TABLE)}

    for table, facts in columns.items():
        if not facts:
            problems.append(f"table {table} is missing")

    for name in _CACHE_TOKEN_COLUMNS:
        facts = columns[_EVENTS_TABLE].get(name)
        if facts is None:
            problems.append(f"{_EVENTS_TABLE}.{name} is missing")
            continue
        column_type, not_null, default = facts
        if column_type != "bigint" or not not_null:
            problems.append(f"{_EVENTS_TABLE}.{name} is {column_type} {'NOT NULL' if not_null else 'NULL'}, expected bigint NOT NULL")
        if _normalized_default(default) != "0":
            problems.append(f"{_EVENTS_TABLE}.{name} has server default {default!r}, expected 0")

    for table in (_EVENTS_TABLE, _RATES_TABLE):
        for name in _CACHE_RATE_COLUMNS:
            facts = columns[table].get(name)
            if facts is None:
                problems.append(f"{table}.{name} is missing")
                continue
            column_type, not_null, default = facts
            if column_type != "numeric(18,10)" or not_null:
                problems.append(f"{table}.{name} is {column_type} {'NOT NULL' if not_null else 'NULL'}, expected numeric(18,10) NULL")
            if default is not None:
                problems.append(f"{table}.{name} has an unexpected server default {default!r}")

    constraint = connection.execute(
        text(
            "SELECT pg_get_constraintdef(oid), convalidated FROM pg_constraint"
            " WHERE conrelid = to_regclass(:table) AND conname = :name AND contype = 'c'"
        ),
        {"table": _EVENTS_TABLE, "name": LLM_USAGE_NON_NEGATIVE_CONSTRAINT},
    ).first()

    if constraint is None:
        problems.append(f"constraint {LLM_USAGE_NON_NEGATIVE_CONSTRAINT} is missing from {_EVENTS_TABLE}")
    else:
        definition = " ".join((constraint[0] or "").split())
        if definition.endswith(" NOT VALID"):
            definition = definition[: -len(" NOT VALID")]
        if definition != LLM_USAGE_NON_NEGATIVE_DEF:
            problems.append(
                f"constraint {LLM_USAGE_NON_NEGATIVE_CONSTRAINT} is {definition!r},"
                f" expected {LLM_USAGE_NON_NEGATIVE_DEF!r}"
            )
        elif not constraint[1]:
            problems.append(f"constraint {LLM_USAGE_NON_NEGATIVE_CONSTRAINT} is not validated")

    return problems


def verify_llm_usage_schema(url: str, label: str) -> bool:
    """Whether this database can record LLM usage. Any inspection failure counts as unverified"""
    engine = None
    try:
        engine = create_engine(url, poolclass=NullPool)
        with engine.connect() as connection:
            problems = _llm_usage_schema_problems(connection)
    except Exception as e:
        logger.error(f"LLM usage schema could not be inspected for {label}: {e}")
        return False
    finally:
        if engine is not None:
            engine.dispose()

    for problem in problems:
        logger.error(f"LLM usage schema check failed for {label}: {problem}")
    return not problems


def verify_llm_usage_schema_for_all_databases() -> bool:
    """The one entry point the API and the Celery workers both gate on"""
    from app.core.config.settings import settings

    verified = verify_llm_usage_schema(settings.DATABASE_URL_SYNC, "main")

    if not settings.MULTI_TENANT_ENABLED:
        return verified

    try:
        tenants = active_tenant_slugs()
    except Exception as e:
        logger.error(f"Could not list tenants for LLM usage schema verification: {e}")
        return False

    for tenant in tenants:
        if not verify_llm_usage_schema(settings.get_tenant_database_url_sync(tenant), f"tenant:({tenant})"):
            verified = False

    return verified


def migrate_and_verify_tenant(tenant: str) -> bool:
    """Bring one tenant database to head and confirm it can record LLM usage.

    Startup only covers active tenants, so a tenant that sat inactive through a
    deployment is still on its old schema when someone reactivates it.
    """
    from app.core.config.settings import settings

    url = settings.get_tenant_database_url_sync(tenant)
    label = f"tenant:({tenant})"
    try:
        if not run_migrations(url):
            logger.error(f"Migrations reported failure for {label}")
            return False
    except Exception as e:
        logger.error(f"Migrations failed for {label}: {e}")
        return False

    return verify_llm_usage_schema(url, label)

