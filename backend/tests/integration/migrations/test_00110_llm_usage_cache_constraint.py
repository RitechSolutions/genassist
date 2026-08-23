"""Real-PostgreSQL resumability drill for migration 00110.

The constraint swap autocommits each statement, so a failure part-way through leaves real
DDL behind with the revision unrecorded. FakeOp tests prove the dispatch table; only a
real server proves the swap actually converges after being interrupted. Each case kills
the swap after a different statement, reruns it, and asserts the database ends up with the
extended constraint validated.

Isolation is deliberate and not negotiable: the connection comes only from
MIGRATION_TEST_DATABASE_URL (see this directory's conftest), never from settings, and
every object lives in a generated schema that is dropped afterwards. search_path is set
per SESSION rather than per transaction — SET LOCAL would die at the commit the autocommit
block issues, after which unqualified DDL would silently target public.
"""

import importlib.util
import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "00110_add_llm_usage_cache_tokens_to_non_negative_check.py"
)

_SCHEMA_PREFIX = "prompt_cache_migration_test_"
_TABLE = "llm_usage_events"
_CONSTRAINT = "ck_llm_usage_events_non_negative"
_TMP = f"{_CONSTRAINT}__tmp"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_00110_drill", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def drill_connection(drill_database_url):
    schema = f"{_SCHEMA_PREFIX}{uuid.uuid4().hex}"
    assert re.fullmatch(r"[a-z0-9_]+", schema), schema
    quoted = f'"{schema}"'

    engine = create_engine(drill_database_url, poolclass=NullPool)
    connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        connection.execute(text(f"CREATE SCHEMA {quoted}"))
        # SESSION, not LOCAL: the autocommit block's commit would end a transaction-scoped
        # setting and leave unqualified DDL pointing at public.
        connection.execute(text(f"SET SESSION search_path TO {quoted}"))
        yield connection, schema
    finally:
        connection.execute(text("SET SESSION search_path TO public"))
        connection.execute(text(f"DROP SCHEMA IF EXISTS {quoted} CASCADE"))
        connection.close()
        engine.dispose()


class _InjectedFailure(RuntimeError):
    pass


class _RealOp:
    """Runs 00110's statements against the drill schema, optionally dying after step N"""

    def __init__(self, connection, schema, fail_after=None):
        self._connection = connection
        self._schema = schema
        self._fail_after = fail_after
        self.executed = []

    def get_bind(self):
        return self._connection

    def get_context(self):
        return self

    def autocommit_block(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, statement):
        current = self._connection.execute(text("SELECT current_schema()")).scalar_one()
        assert current == self._schema, f"DDL would have hit {current!r}, not the drill schema"
        self._connection.execute(text(str(statement)))
        self.executed.append(str(statement))
        if self._fail_after is not None and len(self.executed) == self._fail_after:
            raise _InjectedFailure(f"injected failure after statement {self._fail_after}")


def _reset_to(connection, module, definition_expression):
    connection.execute(text(f"DROP TABLE IF EXISTS {_TABLE} CASCADE"))
    connection.execute(
        text(
            f"CREATE TABLE {_TABLE} ("
            " input_tokens bigint NOT NULL DEFAULT 0,"
            " output_tokens bigint NOT NULL DEFAULT 0,"
            " total_tokens bigint NOT NULL DEFAULT 0,"
            " call_index integer NOT NULL DEFAULT 0,"
            " cache_read_tokens bigint NOT NULL DEFAULT 0,"
            " cache_creation_tokens bigint NOT NULL DEFAULT 0,"
            f" CONSTRAINT {_CONSTRAINT} CHECK ({definition_expression})"
            ")"
        )
    )
    connection.execute(text(f"INSERT INTO {_TABLE} (input_tokens, cache_read_tokens) VALUES (5, 7)"))


def _observed(connection, name):
    row = connection.execute(
        text(
            "SELECT pg_get_constraintdef(oid), convalidated FROM pg_constraint"
            " WHERE conrelid = to_regclass(:table) AND conname = :name AND contype = 'c'"
        ),
        {"table": _TABLE, "name": name},
    ).first()
    return None if row is None else (" ".join(row[0].split()), bool(row[1]))


@pytest.fixture(scope="module")
def module():
    return _load_migration()


def _run(module, connection, schema, direction, fail_after=None):
    fake_op = _RealOp(connection, schema, fail_after)
    original = module.op
    module.op = fake_op
    try:
        getattr(module, direction)()
    finally:
        module.op = original
    return fake_op


class TestUpgradeConverges:
    def test_a_clean_swap_lands_a_validated_extended_constraint(self, drill_connection, module):
        connection, schema = drill_connection
        _reset_to(connection, module, module._ORIGINAL_CHECK)

        op = _run(module, connection, schema, "upgrade")

        assert len(op.executed) == 4
        assert _observed(connection, _CONSTRAINT) == (module._EXTENDED_DEF, True)
        assert _observed(connection, _TMP) is None

    @pytest.mark.parametrize("fail_after", [1, 2, 3, 4])
    def test_it_resumes_after_a_failure_at_any_step(self, drill_connection, module, fail_after):
        connection, schema = drill_connection
        _reset_to(connection, module, module._ORIGINAL_CHECK)

        with pytest.raises(_InjectedFailure):
            _run(module, connection, schema, "upgrade", fail_after=fail_after)

        _run(module, connection, schema, "upgrade")

        assert _observed(connection, _CONSTRAINT) == (module._EXTENDED_DEF, True)
        assert _observed(connection, _TMP) is None

    def test_rerunning_a_finished_swap_changes_nothing(self, drill_connection, module):
        connection, schema = drill_connection
        _reset_to(connection, module, module._ORIGINAL_CHECK)
        _run(module, connection, schema, "upgrade")

        op = _run(module, connection, schema, "upgrade")

        assert op.executed == []
        assert _observed(connection, _CONSTRAINT) == (module._EXTENDED_DEF, True)

    def test_the_extended_constraint_actually_rejects_negative_cache_counts(self, drill_connection, module):
        connection, schema = drill_connection
        _reset_to(connection, module, module._ORIGINAL_CHECK)
        _run(module, connection, schema, "upgrade")

        with pytest.raises(Exception) as excinfo:
            connection.execute(text(f"INSERT INTO {_TABLE} (cache_read_tokens) VALUES (-1)"))

        assert _CONSTRAINT in str(excinfo.value)


class TestDowngradeConverges:
    def test_it_restores_the_original_constraint(self, drill_connection, module):
        connection, schema = drill_connection
        _reset_to(connection, module, module._EXTENDED_CHECK)

        _run(module, connection, schema, "downgrade")

        assert _observed(connection, _CONSTRAINT) == (module._ORIGINAL_DEF, True)
        assert _observed(connection, _TMP) is None

    @pytest.mark.parametrize("fail_after", [1, 2, 3, 4])
    def test_it_resumes_after_a_failure_at_any_step(self, drill_connection, module, fail_after):
        connection, schema = drill_connection
        _reset_to(connection, module, module._EXTENDED_CHECK)

        with pytest.raises(_InjectedFailure):
            _run(module, connection, schema, "downgrade", fail_after=fail_after)

        _run(module, connection, schema, "downgrade")

        assert _observed(connection, _CONSTRAINT) == (module._ORIGINAL_DEF, True)
        assert _observed(connection, _TMP) is None

    def test_a_round_trip_returns_to_the_original_definition(self, drill_connection, module):
        connection, schema = drill_connection
        _reset_to(connection, module, module._ORIGINAL_CHECK)

        _run(module, connection, schema, "upgrade")
        _run(module, connection, schema, "downgrade")

        assert _observed(connection, _CONSTRAINT) == (module._ORIGINAL_DEF, True)


class TestUnrecognizedStateRefuses:
    def test_a_foreign_constraint_definition_stops_the_swap(self, drill_connection, module):
        connection, schema = drill_connection
        _reset_to(connection, module, "input_tokens >= -1")

        with pytest.raises(RuntimeError) as excinfo:
            _run(module, connection, schema, "upgrade")

        assert "unrecognised constraint state" in str(excinfo.value)
