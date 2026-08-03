"""Unit tests for migration 00103's non-destructive downgrade"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "00103_widen_llm_usage_source_type_for_evaluations.py"
)

EVENTS = "llm_usage_events"
RECEIPTS = "llm_usage_capture_runs"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_00103", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBind:

    def __init__(self, counts):
        self._counts = counts
        self.statements = []

    def execute(self, statement):
        sql = str(statement)
        self.statements.append(sql)
        table = next(name for name in self._counts if f"FROM {name}" in sql)
        return SimpleNamespace(scalar_one=lambda: self._counts[table])


class FakeAutocommitBlock:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeContext:
    def autocommit_block(self):
        return FakeAutocommitBlock()


class FakeOp:
    def __init__(self, bind):
        self._bind = bind
        self.executed = []

    def get_bind(self):
        return self._bind

    def get_context(self):
        return FakeContext()

    def execute(self, statement):
        self.executed.append(str(statement))


@pytest.fixture
def migration(monkeypatch):
    def _install(**counts):
        module = _load_migration()
        bind = FakeBind({EVENTS: counts.get("events", 0), RECEIPTS: counts.get("receipts", 0)})
        fake_op = FakeOp(bind)
        monkeypatch.setattr(module, "op", fake_op)
        return module, fake_op, bind

    return _install


def test_recorded_judge_events_block_the_downgrade(migration):
    module, fake_op, bind = migration(events=3)

    with pytest.raises(RuntimeError) as excinfo:
        module.downgrade()

    assert EVENTS in str(excinfo.value) and "3" in str(excinfo.value)
    assert fake_op.executed == [], "the narrow constraint is never restored over live rows"
    assert not any("DELETE" in sql for sql in bind.statements), "judge spend is never deleted"


def test_a_receipt_without_its_events_still_blocks_the_downgrade(migration):
    module, fake_op, bind = migration(events=0, receipts=1)

    with pytest.raises(RuntimeError) as excinfo:
        module.downgrade()

    assert RECEIPTS in str(excinfo.value)
    assert [EVENTS in sql for sql in bind.statements] == [True, False], "both tables are checked, in order"
    assert fake_op.executed == []


def test_an_empty_ledger_downgrades_to_the_narrow_constraint(migration):
    module, fake_op, _ = migration()

    module.downgrade()

    def _statements_for(table, name, condition):
        tmp = f"{name}__tmp"
        return [
            f"ALTER TABLE {table} ADD CONSTRAINT {tmp} CHECK ({condition}) NOT VALID",
            f"ALTER TABLE {table} DROP CONSTRAINT {name}",
            f"ALTER TABLE {table} VALIDATE CONSTRAINT {tmp}",
            f"ALTER TABLE {table} RENAME CONSTRAINT {tmp} TO {name}",
        ]

    assert fake_op.executed == [
        *_statements_for(EVENTS, "ck_llm_usage_events_source_type", module._ORIGINAL),
        *_statements_for(RECEIPTS, "ck_llm_usage_capture_runs_source_type", module._ORIGINAL),
    ]
    assert "evaluation" not in module._ORIGINAL


def test_downgrade_never_holds_the_drop_lock_through_the_scan(migration):
    """DROP and VALIDATE must be separate statements (so DROP's brief lock is
    released before VALIDATE's table scan starts) — collapsing them into one
    ALTER TABLE, or one un-autocommitted transaction, reintroduces the write
    lock the split is meant to avoid."""
    module, fake_op, _ = migration()

    module.downgrade()

    drop_index = fake_op.executed.index(f"ALTER TABLE {EVENTS} DROP CONSTRAINT ck_llm_usage_events_source_type")
    validate_index = fake_op.executed.index(
        "ALTER TABLE llm_usage_events VALIDATE CONSTRAINT ck_llm_usage_events_source_type__tmp"
    )
    assert validate_index == drop_index + 1, "no other statement (i.e. no shared transaction) between them"


def test_upgrade_widens_both_constraints_without_reading_rows(migration):
    module, fake_op, bind = migration(events=5)

    module.upgrade()

    add_statements = [s for s in fake_op.executed if "ADD CONSTRAINT" in s]
    assert len(add_statements) == 2
    assert all(module._WIDENED in s for s in add_statements)
    assert bind.statements == []
