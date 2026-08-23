"""Unit tests for migration 00109's refusal to drop columns that still carry cache data"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "00109_add_llm_usage_cache_tokens_and_cache_rates.py"
)

EVENTS = "llm_usage_events"
RATES = "llm_cost_rates"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_00109", _MIGRATION_PATH)
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


class FakeOp:
    def __init__(self, bind):
        self._bind = bind
        self.dropped = []
        self.added = []

    def get_bind(self):
        return self._bind

    def drop_column(self, table, column):
        self.dropped.append((table, column))

    def add_column(self, table, column):
        self.added.append((table, column.name))


@pytest.fixture
def migration(monkeypatch):
    def _install(**counts):
        module = _load_migration()
        bind = FakeBind({EVENTS: counts.get("events", 0), RATES: counts.get("rates", 0)})
        fake_op = FakeOp(bind)
        monkeypatch.setattr(module, "op", fake_op)
        return module, fake_op, bind

    return _install


def test_recorded_cache_activity_blocks_the_downgrade(migration):
    module, fake_op, _ = migration(events=4)

    with pytest.raises(RuntimeError) as excinfo:
        module.downgrade()

    assert EVENTS in str(excinfo.value) and "4" in str(excinfo.value)
    assert fake_op.dropped == [], "no column is dropped once the guard has fired"


def test_the_events_refusal_offers_no_escape_hatch(migration):
    module, _, _ = migration(events=1)

    with pytest.raises(RuntimeError) as excinfo:
        module.downgrade()

    assert "non-reproducible" in str(excinfo.value)
    assert "CSV" not in str(excinfo.value)


def test_configured_cache_rates_block_the_downgrade_and_name_the_escape_hatch(migration):
    module, fake_op, bind = migration(events=0, rates=2)

    with pytest.raises(RuntimeError) as excinfo:
        module.downgrade()

    assert RATES in str(excinfo.value) and "CSV" in str(excinfo.value)
    assert [EVENTS in sql for sql in bind.statements] == [True, False], "events are checked first"
    assert fake_op.dropped == []


def test_negative_counts_block_the_downgrade_too(migration):
    module, _, bind = migration(events=1)

    with pytest.raises(RuntimeError):
        module.downgrade()

    assert "<> 0" in bind.statements[0]
    assert "> 0" not in bind.statements[0].replace("<> 0", "")


def test_the_guard_reads_every_cache_column(migration):
    module, _, bind = migration()

    module.downgrade()

    events_sql, rates_sql = bind.statements
    for column in ("cache_read_tokens", "cache_creation_tokens", "cache_read_per_1k", "cache_creation_per_1k"):
        assert column in events_sql
    assert "cache_read_per_1k" in rates_sql and "cache_creation_per_1k" in rates_sql


def test_a_clean_ledger_drops_all_six_columns(migration):
    module, fake_op, _ = migration()

    module.downgrade()

    assert fake_op.dropped == [
        (RATES, "cache_creation_per_1k"),
        (RATES, "cache_read_per_1k"),
        (EVENTS, "cache_creation_per_1k"),
        (EVENTS, "cache_read_per_1k"),
        (EVENTS, "cache_creation_tokens"),
        (EVENTS, "cache_read_tokens"),
    ]


def test_upgrade_stays_purely_additive_and_reads_no_rows(migration):
    module, fake_op, bind = migration(events=9)

    module.upgrade()

    assert fake_op.added == [
        (EVENTS, "cache_read_tokens"),
        (EVENTS, "cache_creation_tokens"),
        (EVENTS, "cache_read_per_1k"),
        (EVENTS, "cache_creation_per_1k"),
        (RATES, "cache_read_per_1k"),
        (RATES, "cache_creation_per_1k"),
    ]
    assert bind.statements == [] and fake_op.dropped == []
