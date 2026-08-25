"""The two ways a real database arrives at the extended constraint, end to end.

Fresh databases are NOT built by Alembic here — the chain cannot replay from empty (an
early migration alters a `roles` table that does not exist yet), which is why
``run_migrations`` stamps head and ``create_all`` builds the schema at lifespan startup.
So the ORM and migration 00110 have to agree, and this drill proves both paths land the
same validated constraint against a real server:

  * cold start   — ``Base.metadata.create_all`` on an empty database
  * upgrade      — a 00109-era database carrying live cache data, migrated by Alembic

It also covers the downgrade interaction the unit tests cannot: 00110 reverts the
constraint, then 00109's data guard refuses to drop columns that still hold cache activity.

Gating and the throwaway-database rule live in this directory's conftest.
"""

import importlib
import importlib.util
import pkgutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from alembic import command
from alembic.config import Config

_BACKEND = Path(__file__).resolve().parents[3]
_VERSIONS = _BACKEND / "alembic" / "versions"

_EVENTS = "llm_usage_events"
_CONSTRAINT = "ck_llm_usage_events_non_negative"

_00109 = "d37941010920"
_00108 = "c41d7ab35f92"


def _load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _VERSIONS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def swap_migration():
    return _load("00110_add_llm_usage_cache_tokens_to_non_negative_check.py", "paths_00110")


@pytest.fixture(scope="module")
def engine(drill_database_url):
    engine = create_engine(drill_database_url, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def alembic_config(drill_database_url):
    config = Config(str(_BACKEND / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", drill_database_url)
    return config


@pytest.fixture
def empty_database(engine):
    """A bare database, as a first deployment would find it"""
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    return engine


def _cold_start(engine):
    """What multi_tenant_manager.initialize() does on a database with no tables"""
    import app.db.base as base
    import app.db.models as models_package

    for module in pkgutil.iter_modules(models_package.__path__):
        importlib.import_module(f"app.db.models.{module.name}")

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    base.Base.metadata.create_all(engine)


def _constraint(engine):
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid), convalidated FROM pg_constraint"
                " WHERE conrelid = to_regclass(:table) AND conname = :name AND contype = 'c'"
            ),
            {"table": _EVENTS, "name": _CONSTRAINT},
        ).first()
    return None if row is None else (" ".join(row[0].split()), bool(row[1]))


def _revert_constraint_to_00109(engine, swap_migration):
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {_EVENTS} DROP CONSTRAINT {_CONSTRAINT}"))
        connection.execute(
            text(f"ALTER TABLE {_EVENTS} ADD CONSTRAINT {_CONSTRAINT} CHECK ({swap_migration._ORIGINAL_CHECK})")
        )


def _stamp(engine, revision):
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": revision})


def _insert_cached_event(engine, execution_id="drill"):
    with engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO {_EVENTS} (id, execution_id, call_index, source_type, source,"
                " input_tokens, output_tokens, total_tokens, cache_read_tokens, cache_creation_tokens,"
                " pricing_status, occurred_at, is_deleted)"
                " VALUES (gen_random_uuid(), :eid, 0, 'workflow', 'wf', 10, 5, 15, 900, 3,"
                " 'unpriced', now(), 0)"
            ),
            {"eid": execution_id},
        )


def _cached_event_count(engine):
    with engine.connect() as connection:
        return connection.execute(text(f"SELECT count(*) FROM {_EVENTS} WHERE cache_read_tokens <> 0")).scalar_one()


class TestColdStartParity:
    """create_all is how fresh databases are really built, so the ORM must match 00110"""

    def test_a_cold_started_database_already_has_the_extended_constraint(self, empty_database, swap_migration):
        _cold_start(empty_database)

        assert _constraint(empty_database) == (swap_migration._EXTENDED_DEF, True)

    def test_the_constraint_actually_rejects_a_negative_cache_count(self, empty_database):
        _cold_start(empty_database)

        with pytest.raises(Exception) as excinfo:
            with empty_database.begin() as connection:
                connection.execute(text(f"UPDATE {_EVENTS} SET cache_read_tokens = -1"))
                connection.execute(
                    text(
                        f"INSERT INTO {_EVENTS} (id, execution_id, call_index, source_type, source,"
                        " input_tokens, output_tokens, total_tokens, cache_read_tokens,"
                        " pricing_status, occurred_at, is_deleted)"
                        " VALUES (gen_random_uuid(), 'neg', 0, 'workflow', 'wf', 0, 0, 0, -1,"
                        " 'unpriced', now(), 0)"
                    )
                )

        assert _CONSTRAINT in str(excinfo.value)


class TestUpgradeFrom00109:
    """The shared-environment case: a database already carrying cache data"""

    @pytest.fixture
    def database_at_00109(self, empty_database, swap_migration):
        _cold_start(empty_database)
        _revert_constraint_to_00109(empty_database, swap_migration)
        _stamp(empty_database, _00109)
        _insert_cached_event(empty_database)
        return empty_database

    def test_alembic_upgrades_it_to_a_validated_extended_constraint(
        self, database_at_00109, alembic_config, swap_migration
    ):
        command.upgrade(alembic_config, "head")

        assert _constraint(database_at_00109) == (swap_migration._EXTENDED_DEF, True)

    def test_the_live_cache_data_survives_the_upgrade(self, database_at_00109, alembic_config):
        command.upgrade(alembic_config, "head")

        assert _cached_event_count(database_at_00109) == 1

    def test_upgrading_twice_is_a_no_op(self, database_at_00109, alembic_config, swap_migration):
        command.upgrade(alembic_config, "head")
        command.upgrade(alembic_config, "head")

        assert _constraint(database_at_00109) == (swap_migration._EXTENDED_DEF, True)


class TestDowngradeInteraction:
    """00110 reverts the constraint, then 00109 refuses to drop columns holding cache data"""

    @pytest.fixture
    def database_at_head(self, empty_database, swap_migration):
        _cold_start(empty_database)
        _revert_constraint_to_00109(empty_database, swap_migration)
        _stamp(empty_database, _00109)
        return empty_database

    def test_recorded_cache_activity_refuses_the_downgrade(self, database_at_head, alembic_config):
        command.upgrade(alembic_config, "head")
        _insert_cached_event(database_at_head)

        with pytest.raises(RuntimeError) as excinfo:
            command.downgrade(alembic_config, _00108)

        assert "non-reproducible" in str(excinfo.value)

    def test_the_refused_downgrade_keeps_every_cache_column_and_row(self, database_at_head, alembic_config, engine):
        command.upgrade(alembic_config, "head")
        _insert_cached_event(database_at_head)

        with pytest.raises(RuntimeError):
            command.downgrade(alembic_config, _00108)

        with engine.connect() as connection:
            remaining = connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns"
                    " WHERE table_name = :t AND column_name LIKE 'cache%'"
                ),
                {"t": _EVENTS},
            ).scalar_one()
        assert remaining == 4
        assert _cached_event_count(database_at_head) == 1

    def test_the_documented_recovery_repairs_the_reverted_constraint(
        self, database_at_head, alembic_config, swap_migration
    ):
        """A refused guard leaves 00110's swap reverted while the revision still reads 00110"""
        command.upgrade(alembic_config, "head")
        _insert_cached_event(database_at_head)
        with pytest.raises(RuntimeError):
            command.downgrade(alembic_config, _00108)

        assert _constraint(database_at_head) == (swap_migration._ORIGINAL_DEF, True)

        command.downgrade(alembic_config, _00109)
        command.upgrade(alembic_config, "head")

        assert _constraint(database_at_head) == (swap_migration._EXTENDED_DEF, True)

    def test_an_empty_ledger_downgrades_cleanly(self, database_at_head, alembic_config, engine):
        command.upgrade(alembic_config, "head")

        command.downgrade(alembic_config, _00108)

        with engine.connect() as connection:
            remaining = connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns"
                    " WHERE table_name = :t AND column_name LIKE 'cache%'"
                ),
                {"t": _EVENTS},
            ).scalar_one()
        assert remaining == 0
