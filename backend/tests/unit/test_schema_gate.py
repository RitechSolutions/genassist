"""Unit tests for the startup wait that keeps Celery workers and beat off an old schema"""

from types import SimpleNamespace

import pytest

import migrations
from app.core.config.settings import settings

UPLOAD_PURPOSE_REVISION = "c3a9d27e5b41"  # 00126, files_upload_sessions.upload_purpose
BEFORE_UPLOAD_PURPOSE = "a601f9fbdddb"  # 00125


@pytest.fixture(scope="module")
def code_heads():
    return migrations._code_head_revisions()


@pytest.fixture
def clock(monkeypatch):
    """Fake monotonic clock that only moves when the gate sleeps"""
    now = [0.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    # Replace the module's clock, not the shared `time` module: threads left over
    # from other tests also sleep, and must not move this clock
    monkeypatch.setattr(migrations, "time", SimpleNamespace(monotonic=lambda: now[0], sleep=sleep))
    return sleeps


@pytest.fixture(autouse=True)
def tenant_marker(monkeypatch):
    """In-memory stand-in for the Redis marker of a tenant wait that was given up"""
    saved = set()
    monkeypatch.setattr(migrations, "_tenant_wait_given_up", lambda head: head in saved)
    monkeypatch.setattr(migrations, "_remember_tenant_wait_given_up", saved.add)
    return saved


def _behind_sequence(monkeypatch, results):
    calls = []

    def databases_behind(heads, script):
        calls.append(heads)
        return results.pop(0) if len(results) > 1 else results[0]

    monkeypatch.setattr(migrations, "_databases_behind", databases_behind)
    return calls


def test_code_heads_include_the_upload_purpose_migration(code_heads):
    heads, script = code_heads
    assert heads
    for head in heads:
        ancestors = {rev.revision for rev in script.iterate_revisions(head, "base")}
        assert UPLOAD_PURPOSE_REVISION in ancestors


def test_database_at_head_is_ready(code_heads):
    heads, script = code_heads
    assert migrations._is_schema_ready(set(heads), heads, script)


def test_database_before_the_upload_purpose_migration_is_not_ready(code_heads):
    heads, script = code_heads
    assert not migrations._is_schema_ready({BEFORE_UPLOAD_PURPOSE}, heads, script)


def test_database_without_a_revision_is_not_ready(code_heads):
    heads, script = code_heads
    assert not migrations._is_schema_ready(set(), heads, script)


def test_database_ahead_of_this_code_is_ready(code_heads):
    """A rollback runs older workers on a newer schema; they must still start"""
    heads, script = code_heads
    assert migrations._is_schema_ready({"ffffffffffff"}, heads, script)


def test_starts_at_once_when_the_schema_is_at_head(monkeypatch, clock):
    calls = _behind_sequence(monkeypatch, [[]])

    migrations.wait_for_schema_at_head(timeout_seconds=60, interval_seconds=5)

    assert len(calls) == 1
    assert clock == []


def test_waits_until_the_migration_has_run(monkeypatch, clock):
    calls = _behind_sequence(monkeypatch, [["main"], ["main", "tenant:(acme)"], []])

    migrations.wait_for_schema_at_head(timeout_seconds=60, interval_seconds=5)

    assert len(calls) == 3
    assert clock == [5, 5]


def test_gives_up_when_the_main_database_stays_behind(monkeypatch, clock):
    _behind_sequence(monkeypatch, [["main", "tenant:(acme)"]])

    with pytest.raises(migrations.SchemaNotReadyError, match=r"main, tenant:\(acme\)"):
        migrations.wait_for_schema_at_head(timeout_seconds=12, interval_seconds=5)

    assert clock == [5, 5, 5]


def test_starts_anyway_when_only_a_tenant_stays_behind(monkeypatch, clock, caplog):
    """One broken tenant must not stop background jobs for every tenant"""
    _behind_sequence(monkeypatch, [["tenant:(acme)"]])

    with caplog.at_level("ERROR", logger=migrations.logger.name):
        migrations.wait_for_schema_at_head(timeout_seconds=12, interval_seconds=5)

    assert clock == [5, 5, 5]
    assert "tenant:(acme)" in caplog.text


def test_waits_for_tenants_before_giving_up_on_them(monkeypatch, clock):
    calls = _behind_sequence(monkeypatch, [["tenant:(acme)"], []])

    migrations.wait_for_schema_at_head(timeout_seconds=60, interval_seconds=5)

    assert len(calls) == 2
    assert clock == [5]


@pytest.fixture
def databases(monkeypatch):
    """Fake main + tenant databases: url -> revisions, or an exception to raise"""
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)
    state = {"main-url": None, "tenants": [("tenant:(acme)", "acme-url")], "acme-url": None}

    def database_revisions(url):
        value = state["main-url" if url == settings.DATABASE_URL_SYNC else url]
        if isinstance(value, Exception):
            raise value
        return value

    def active_tenant_urls():
        if isinstance(state["tenants"], Exception):
            raise state["tenants"]
        return state["tenants"]

    monkeypatch.setattr(migrations, "_database_revisions", database_revisions)
    monkeypatch.setattr(migrations, "_active_tenant_urls", active_tenant_urls)
    return state


def test_unreadable_main_database_counts_as_behind(databases, code_heads):
    heads, script = code_heads
    databases["main-url"] = ConnectionError("database is starting")
    databases["acme-url"] = set(heads)

    assert migrations._databases_behind(heads, script) == ["main"]


def test_unreadable_tenant_list_does_not_hide_the_main_database(databases, code_heads):
    heads, script = code_heads
    databases["main-url"] = {BEFORE_UPLOAD_PURPOSE}
    databases["tenants"] = RuntimeError("tenants table missing")

    assert migrations._databases_behind(heads, script) == ["main", "tenants"]


def test_names_the_tenant_that_is_behind(databases, code_heads):
    heads, script = code_heads
    databases["main-url"] = set(heads)
    databases["acme-url"] = {BEFORE_UPLOAD_PURPOSE}

    assert migrations._databases_behind(heads, script) == ["tenant:(acme)"]


def test_short_revision_prefix_is_not_mistaken_for_a_known_revision(code_heads):
    """Alembic resolves prefixes; a stored revision must match a known id exactly"""
    heads, script = code_heads
    assert migrations._is_schema_ready({BEFORE_UPLOAD_PURPOSE[:2]}, heads, script)
    assert not migrations._is_schema_ready({BEFORE_UPLOAD_PURPOSE}, heads, script)


def test_giving_up_on_a_tenant_is_remembered_for_this_head(monkeypatch, clock, tenant_marker):
    heads, _ = migrations._code_head_revisions()
    _behind_sequence(monkeypatch, [["tenant:(acme)"]])

    migrations.wait_for_schema_at_head(timeout_seconds=12, interval_seconds=5)

    assert tenant_marker == {", ".join(sorted(heads))}


def test_later_worker_starts_at_once_when_a_tenant_wait_was_given_up(monkeypatch, clock, tenant_marker):
    """A crash restart or scale-out must not pause every tenant's jobs again"""
    heads, _ = migrations._code_head_revisions()
    tenant_marker.add(", ".join(sorted(heads)))
    _behind_sequence(monkeypatch, [["tenant:(acme)"]])

    migrations.wait_for_schema_at_head(timeout_seconds=900, interval_seconds=5)

    assert clock == []


def test_given_up_tenant_wait_never_skips_a_stale_main_database(monkeypatch, clock, tenant_marker):
    heads, _ = migrations._code_head_revisions()
    tenant_marker.add(", ".join(sorted(heads)))
    _behind_sequence(monkeypatch, [["main", "tenant:(acme)"]])

    with pytest.raises(migrations.SchemaNotReadyError):
        migrations.wait_for_schema_at_head(timeout_seconds=12, interval_seconds=5)

    assert clock == [5, 5, 5]


def test_marker_from_another_release_is_ignored(monkeypatch, clock, tenant_marker):
    tenant_marker.add("older-head")
    calls = _behind_sequence(monkeypatch, [["tenant:(acme)"], []])

    migrations.wait_for_schema_at_head(timeout_seconds=60, interval_seconds=5)

    assert len(calls) == 2
    assert clock == [5]


def test_unreachable_redis_falls_back_to_waiting(monkeypatch):
    monkeypatch.undo()

    def broken_client():
        raise ConnectionError("redis down")

    monkeypatch.setattr(migrations, "_redis_client", broken_client)

    assert migrations._tenant_wait_given_up("any-head") is False
    migrations._remember_tenant_wait_given_up("any-head")  # logs, does not raise
