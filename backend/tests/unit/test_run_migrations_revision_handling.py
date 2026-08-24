"""run_migrations' revision handling: a fresh database stamps head (create_all builds the
schema at startup), while AUTO_MIGRATE=false must leave alembic_version to the external
migration job in every case, fresh databases included, stamping there would make the
job's next upgrade an empty walk"""

import pytest
from alembic import command

import migrations


@pytest.fixture
def alembic_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(command, "ensure_version", lambda cfg: calls.append("ensure_version"))
    monkeypatch.setattr(command, "stamp", lambda cfg, revision: calls.append(f"stamp:{revision}"))
    monkeypatch.setattr(command, "upgrade", lambda cfg, revision: calls.append(f"upgrade:{revision}"))
    return calls


def _tables(monkeypatch, names):
    monkeypatch.setattr(migrations, "get_table_names", lambda url: names)


def test_a_fresh_database_stamps_head(monkeypatch, alembic_calls):
    _tables(monkeypatch, ["alembic_version"])
    monkeypatch.delenv("AUTO_MIGRATE", raising=False)

    assert migrations.run_migrations("postgresql://x/y") is True
    assert alembic_calls == ["ensure_version", "stamp:head"]


def test_auto_migrate_off_touches_no_revision_on_a_fresh_database(monkeypatch, alembic_calls):
    _tables(monkeypatch, [])
    monkeypatch.setenv("AUTO_MIGRATE", "false")

    assert migrations.run_migrations("postgresql://x/y") is True
    assert alembic_calls == []


def test_auto_migrate_off_touches_no_revision_on_an_existing_database(monkeypatch, alembic_calls):
    _tables(monkeypatch, ["users", "tenants"])
    monkeypatch.setenv("AUTO_MIGRATE", "false")

    assert migrations.run_migrations("postgresql://x/y") is True
    assert alembic_calls == []


def test_auto_migrate_off_never_even_inspects_the_database(monkeypatch, alembic_calls):
    def _boom(url):
        raise AssertionError("must not connect")

    monkeypatch.setattr(migrations, "get_table_names", _boom)
    monkeypatch.setenv("AUTO_MIGRATE", "false")

    assert migrations.run_migrations("postgresql://x/y") is True
    assert alembic_calls == []


def test_an_existing_database_upgrades_to_head(monkeypatch, alembic_calls):
    _tables(monkeypatch, ["users", "tenants"])
    monkeypatch.delenv("AUTO_MIGRATE", raising=False)

    assert migrations.run_migrations("postgresql://x/y") is True
    assert alembic_calls == ["upgrade:head"]
