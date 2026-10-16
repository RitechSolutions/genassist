import logging
import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, event
from sqlalchemy import pool
from alembic import context
from app.db.base import Base
from app.core.config.settings import settings


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.

if "revision" in sys.argv and os.getenv("MY_PROJECT_RUN_ALEMBIC") != "1":
    sys.exit(
        "ERROR: Do not run Alembic directly to generate a migration file with the revision command. "
        "Use the project's migration script instead inside scripts folder. (for more info read alembic/readme)"
    )


config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if (
    config.config_file_name
    and context.config.attributes.get("configure_logger", True)
    and os.getenv("ALEMBIC_SKIP_FILECONFIG") != "1"
):
    # don't blow away your Loguru/stdlib handlers
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# Load DB URL from environment variable if not already set
# This allows run_migrations_for_database to set a custom URL for tenant databases
if not config.get_main_option("sqlalchemy.url") or config.get_main_option("sqlalchemy.url") == "driver://user:pass@localhost/dbname":
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


def _is_autocommit(connection) -> bool:
    return connection.get_execution_options().get("isolation_level") == "AUTOCOMMIT"


def _dead_client_check_is_supported(connection) -> bool:
    """Best effort: a killed pod must not keep its running statement and its locks alive."""
    try:
        connection.exec_driver_sql("SET client_connection_check_interval = '1s'")
        supported = True
    except Exception as error:
        logging.getLogger("alembic.env").warning("client_connection_check_interval not applied: %s", error)
        supported = False
    # The statement opened a transaction; Alembic must find the connection outside one.
    connection.commit()
    return supported


def run_migrations_online() -> None:
    """Run migrations in 'online' mode, one transaction per migration.

    Lock waits inside a migration are capped by MIGRATION_LOCK_TIMEOUT_SECONDS; autocommit
    blocks run outside that cap, see alembic/README section 6.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"options": "-c statement_timeout=0"},
    )
    lock_timeout = f"{settings.MIGRATION_LOCK_TIMEOUT_SECONDS}s"

    with connectable.connect() as connection:
        dead_client_check = _dead_client_check_is_supported(connection)

        @event.listens_for(connection, "begin")
        def configure_this_transaction(begun_connection):
            if _is_autocommit(begun_connection):
                # A cancelled CREATE INDEX CONCURRENTLY leaves an invalid index, so let it finish
                if dead_client_check:
                    begun_connection.exec_driver_sql("SET client_connection_check_interval = 0")
                return
            if dead_client_check:
                begun_connection.exec_driver_sql("SET LOCAL client_connection_check_interval = '1s'")
            begun_connection.exec_driver_sql(f"SET LOCAL lock_timeout = '{lock_timeout}'")

        context.configure(
            connection=connection, target_metadata=target_metadata,
            compare_type=True,
            transaction_per_migration=True,
        )

        with context.begin_transaction():
            context.run_migrations()
        # Commits work Alembic leaves in an open transaction, such as ensure_version's table
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
