"""Unit tests for the lock-aware retry around `alembic upgrade head`"""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

import migrations
from alembic import command
from app.core.config.settings import settings

QUERY_CANCELED = "57014"


def _database_error(pgcode: str) -> OperationalError:
    return OperationalError("UPDATE conversations", {}, SimpleNamespace(pgcode=pgcode))


def _upgrade_failing(errors):
    """Fake upgrade that raises the queued errors in order, then succeeds"""
    calls = []

    def upgrade(alembic_cfg, revision):
        calls.append(revision)
        if errors:
            raise errors.pop(0)

    return upgrade, calls


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(migrations.time, "sleep", recorded.append)
    return recorded


def test_lock_timeouts_are_retried_with_growing_pauses(monkeypatch, sleeps):
    monkeypatch.setattr(settings, "MIGRATION_LOCK_RETRIES", 5)
    lock_errors = [_database_error(migrations.LOCK_NOT_AVAILABLE)] * 2
    upgrade, calls = _upgrade_failing(lock_errors)
    monkeypatch.setattr(command, "upgrade", upgrade)

    migrations.upgrade_head_with_lock_retry(alembic_cfg=None, database_name="main")

    assert calls == ["head"] * 3
    assert sleeps == [2, 4]


def test_gives_up_after_the_configured_retries(monkeypatch, sleeps):
    monkeypatch.setattr(settings, "MIGRATION_LOCK_RETRIES", 2)
    lock_errors = [_database_error(migrations.LOCK_NOT_AVAILABLE)] * 3
    upgrade, calls = _upgrade_failing(lock_errors)
    monkeypatch.setattr(command, "upgrade", upgrade)

    with pytest.raises(migrations.MigrationLockRetriesExhausted):
        migrations.upgrade_head_with_lock_retry(alembic_cfg=None, database_name="main")

    assert calls == ["head"] * 3
    assert sleeps == [2, 4]


def test_backoff_stops_growing_at_the_ceiling(monkeypatch, sleeps):
    monkeypatch.setattr(settings, "MIGRATION_LOCK_RETRIES", 7)
    lock_errors = [_database_error(migrations.LOCK_NOT_AVAILABLE)] * 7
    upgrade, calls = _upgrade_failing(lock_errors)
    monkeypatch.setattr(command, "upgrade", upgrade)

    migrations.upgrade_head_with_lock_retry(alembic_cfg=None, database_name="main")

    assert calls == ["head"] * 8
    assert sleeps == [2, 4, 8, 16, 32, 32, 32]


def test_other_database_errors_are_not_retried(monkeypatch, sleeps):
    monkeypatch.setattr(settings, "MIGRATION_LOCK_RETRIES", 5)
    upgrade, calls = _upgrade_failing([_database_error(QUERY_CANCELED)])
    monkeypatch.setattr(command, "upgrade", upgrade)

    with pytest.raises(OperationalError):
        migrations.upgrade_head_with_lock_retry(alembic_cfg=None, database_name="main")

    assert calls == ["head"]
    assert sleeps == []
