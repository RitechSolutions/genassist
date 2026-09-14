"""Unit tests for read-replica routing: settings, engine fallback, the read session provider and routed repositories"""

import typing

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.tenant_scope import background_task_context, clear_tenant_context, set_tenant_context
from app.db import multi_tenant_session as mts
from app.db.session_types import ReadOnlySession

TENANT = "replica-routing-test"
LOOK_ALIKE_TENANT = f"{TENANT}_read"
MANAGER_CACHES = ("_engines", "_session_factories", "_read_engines", "_read_session_factories")
SETTINGS_UNDER_TEST = (
    "DB_HOST",
    "DB_USER",
    "DB_PASS",
    "DB_NAME",
    "DB_READ_HOST",
    "DB_READ_POOL_SIZE",
    "DB_READ_MAX_OVERFLOW",
)


class FakeEngine:
    def __init__(self, url, kwargs):
        self.url = url
        self.kwargs = kwargs
        self.disposed = False

    async def dispose(self):
        self.disposed = True


@pytest.fixture(autouse=True)
def restore_settings():
    snapshot = {name: getattr(settings, name) for name in SETTINGS_UNDER_TEST}
    settings.DB_HOST = "writer.internal"
    settings.DB_USER = "user"
    settings.DB_PASS = "secret"
    settings.DB_NAME = "core_db"
    settings.DB_READ_HOST = None
    settings.DB_READ_POOL_SIZE = None
    settings.DB_READ_MAX_OVERFLOW = None
    try:
        yield
    finally:
        for name, value in snapshot.items():
            setattr(settings, name, value)


@pytest.fixture(autouse=True)
def restore_manager_caches():
    manager = mts.multi_tenant_manager
    snapshot = {name: dict(getattr(manager, name)) for name in MANAGER_CACHES}
    try:
        yield manager
    finally:
        for name, cached in snapshot.items():
            getattr(manager, name).clear()
            getattr(manager, name).update(cached)


@pytest.fixture
def created_engines(monkeypatch):
    created = []

    def fake_create_async_engine(url, **kwargs):
        engine = FakeEngine(url, kwargs)
        created.append(engine)
        return engine

    monkeypatch.setattr(mts, "create_async_engine", fake_create_async_engine)
    return created


# ───────────── settings ─────────────


def test_replica_disabled_when_host_missing_or_blank():
    settings.DB_READ_HOST = None
    assert settings.read_replica_enabled is False
    settings.DB_READ_HOST = "   "
    assert settings.read_replica_enabled is False
    settings.DB_READ_HOST = "reader.internal"
    assert settings.read_replica_enabled is True


def test_read_url_equals_writer_url_when_replica_disabled():
    settings.DB_READ_HOST = None
    assert settings.get_tenant_read_database_url("acme-co") == settings.get_tenant_database_url("acme-co")


def test_read_url_swaps_only_the_host():
    settings.DB_READ_HOST = " reader.internal "
    read_url = make_url(settings.get_tenant_read_database_url("acme-co"))
    write_url = make_url(settings.get_tenant_database_url("acme-co"))
    assert read_url.host == "reader.internal"
    assert write_url.host == "writer.internal"
    assert read_url.database == write_url.database == settings.get_tenant_database_name("acme-co")
    assert read_url.username == write_url.username
    assert read_url.drivername == write_url.drivername


def test_read_pool_settings_inherit_writer_values_unless_set():
    assert settings.read_pool_size == settings.DB_POOL_SIZE
    assert settings.read_max_overflow == settings.DB_MAX_OVERFLOW
    settings.DB_READ_POOL_SIZE = 7
    settings.DB_READ_MAX_OVERFLOW = 3
    assert settings.read_pool_size == 7
    assert settings.read_max_overflow == 3


# ───────────── engines and session factories ─────────────


def test_read_engine_is_the_writer_engine_when_replica_disabled(created_engines, restore_manager_caches):
    manager = restore_manager_caches
    assert manager.get_tenant_read_engine(TENANT) is manager.get_tenant_engine(TENANT)
    assert TENANT not in manager._read_engines
    assert len(created_engines) == 1


def test_read_engine_is_a_separate_read_only_engine_when_replica_enabled(created_engines, restore_manager_caches):
    manager = restore_manager_caches
    settings.DB_READ_HOST = "reader.internal"
    settings.DB_READ_POOL_SIZE = 5
    settings.DB_READ_MAX_OVERFLOW = 2

    read_engine = manager.get_tenant_read_engine(TENANT)
    write_engine = manager.get_tenant_engine(TENANT)

    assert read_engine is not write_engine
    assert manager._read_engines[TENANT] is read_engine
    assert manager._engines[TENANT] is write_engine
    assert manager.get_tenant_read_engine(TENANT) is read_engine

    assert make_url(read_engine.url).host == "reader.internal"
    assert make_url(write_engine.url).host == "writer.internal"
    assert read_engine.kwargs["pool_size"] == 5
    assert read_engine.kwargs["max_overflow"] == 2
    assert read_engine.kwargs["pool_pre_ping"] is True

    server_settings = read_engine.kwargs["connect_args"]["server_settings"]
    assert server_settings["default_transaction_read_only"] == "on"
    assert server_settings["application_name"] == "genassist-read"
    assert server_settings["statement_timeout"] == str(settings.DB_STATEMENT_TIMEOUT * 1000)

    writer_server_settings = write_engine.kwargs["connect_args"]["server_settings"]
    assert "default_transaction_read_only" not in writer_server_settings


def test_background_tasks_keep_reading_from_the_writer(created_engines, restore_manager_caches):
    manager = restore_manager_caches
    settings.DB_READ_HOST = "reader.internal"
    with background_task_context():
        assert manager.get_tenant_read_engine(TENANT) is manager.get_tenant_engine(TENANT)
    assert TENANT not in manager._read_engines


def test_read_caches_cannot_be_poisoned_by_a_look_alike_tenant_string(created_engines, restore_manager_caches):
    """A request carrying x-tenant-id '<tenant>_read' must never alias the real tenant's read engine"""
    manager = restore_manager_caches
    settings.DB_READ_HOST = "reader.internal"

    look_alike_write_engine = manager.get_tenant_engine(LOOK_ALIKE_TENANT)
    read_engine = manager.get_tenant_read_engine(TENANT)

    assert read_engine is not look_alike_write_engine
    assert make_url(read_engine.url).host == "reader.internal"
    assert make_url(look_alike_write_engine.url).host == "writer.internal"
    assert manager.get_tenant_read_session_factory(TENANT) is not manager.get_tenant_session_factory(LOOK_ALIKE_TENANT)


@pytest.mark.asyncio
async def test_close_all_disposes_read_engines_too(created_engines, restore_manager_caches):
    manager = restore_manager_caches
    settings.DB_READ_HOST = "reader.internal"
    manager.get_tenant_engine(TENANT)
    manager.get_tenant_read_engine(TENANT)

    await manager.close_all()

    assert len(created_engines) == 2
    assert all(engine.disposed for engine in created_engines)


def test_read_session_factory_falls_back_to_the_writer_factory(created_engines, restore_manager_caches):
    manager = restore_manager_caches
    assert manager.get_tenant_read_session_factory(TENANT) is manager.get_tenant_session_factory(TENANT)
    assert TENANT not in manager._read_session_factories


def test_read_session_factory_binds_to_the_read_engine(created_engines, restore_manager_caches):
    manager = restore_manager_caches
    settings.DB_READ_HOST = "reader.internal"
    read_factory = manager.get_tenant_read_session_factory(TENANT)
    assert read_factory is not manager.get_tenant_session_factory(TENANT)
    assert read_factory.kw["bind"] is manager.get_tenant_read_engine(TENANT)
    assert read_factory.kw["expire_on_commit"] is False


# ───────────── dependency injection ─────────────


def test_provider_returns_the_request_write_session_when_replica_disabled():
    from app.dependencies.dependency_injection import Dependencies

    write_session = object()
    assert Dependencies().provide_read_session(write_session) is write_session


def test_provider_returns_a_read_session_from_the_tenant_read_factory(monkeypatch):
    from app.dependencies.dependency_injection import Dependencies

    settings.DB_READ_HOST = "reader.internal"
    read_session = object()
    seen_tenants = []

    def fake_read_factory(tenant):
        seen_tenants.append(tenant)
        return lambda: read_session

    monkeypatch.setattr(mts.multi_tenant_manager, "get_tenant_read_session_factory", fake_read_factory)
    set_tenant_context("acme-co")
    try:
        assert Dependencies().provide_read_session(object()) is read_session
    finally:
        clear_tenant_context()
    assert seen_tenants == ["acme-co"]


def test_provider_keeps_background_tasks_on_the_write_session():
    from app.dependencies.dependency_injection import Dependencies

    settings.DB_READ_HOST = "reader.internal"
    write_session = object()
    with background_task_context():
        assert Dependencies().provide_read_session(write_session) is write_session


def test_read_only_session_is_bound_to_the_provider_without_touching_the_write_binding():
    from fastapi_injector.request_scope import RequestScope
    from injector import CallableProvider, Injector

    from app.dependencies.dependency_injection import Dependencies

    inj = Injector([Dependencies()])
    read_binding, _ = inj.binder.get_binding(ReadOnlySession)
    write_binding, _ = inj.binder.get_binding(AsyncSession)

    assert isinstance(read_binding.provider, CallableProvider)
    assert read_binding.provider._callable.__func__ is Dependencies.provide_read_session
    assert read_binding.scope is RequestScope
    assert write_binding.provider._callable.__func__ is Dependencies.provide_session


@pytest.mark.asyncio
async def test_injector_resolves_the_write_session_for_read_only_dependencies_when_disabled(monkeypatch):
    from fastapi_injector import RequestScopeFactory
    from injector import Injector

    from app.dependencies.dependency_injection import Dependencies

    write_session = object()
    monkeypatch.setattr(mts.multi_tenant_manager, "get_tenant_session_factory", lambda tenant="master": lambda: write_session)
    inj = Injector([Dependencies()])
    set_tenant_context("acme-co")
    try:
        async with inj.get(RequestScopeFactory).create_scope():
            assert inj.get(AsyncSession) is write_session
            assert inj.get(ReadOnlySession) is write_session
    finally:
        clear_tenant_context()


@pytest.mark.asyncio
async def test_injector_resolves_a_separate_read_session_when_enabled(monkeypatch):
    from fastapi_injector import RequestScopeFactory
    from injector import Injector

    from app.dependencies.dependency_injection import Dependencies

    settings.DB_READ_HOST = "reader.internal"
    write_session, read_session = object(), object()
    monkeypatch.setattr(mts.multi_tenant_manager, "get_tenant_session_factory", lambda tenant="master": lambda: write_session)
    monkeypatch.setattr(mts.multi_tenant_manager, "get_tenant_read_session_factory", lambda tenant="master": lambda: read_session)
    inj = Injector([Dependencies()])
    set_tenant_context("acme-co")
    try:
        async with inj.get(RequestScopeFactory).create_scope():
            assert inj.get(AsyncSession) is write_session
            assert inj.get(ReadOnlySession) is read_session
            assert inj.get(ReadOnlySession) is read_session
    finally:
        clear_tenant_context()


def _routed_repositories():
    from app.repositories.analytics_read import AnalyticsReadRepository
    from app.repositories.dashboard import DashboardRepository
    from app.repositories.llm_usage_read import LlmUsageReadRepository

    return (AnalyticsReadRepository, DashboardRepository, LlmUsageReadRepository)


async def _resolve_repositories_in_a_request(monkeypatch, write_session, read_session):
    """Build every repository through the real injector, as a request would, and return their sessions"""
    from fastapi_injector import RequestScopeFactory
    from injector import Injector

    from app.dependencies.dependency_injection import Dependencies
    from app.repositories.conversations import ConversationRepository

    monkeypatch.setattr(mts.multi_tenant_manager, "get_tenant_session_factory", lambda tenant="master": lambda: write_session)
    monkeypatch.setattr(mts.multi_tenant_manager, "get_tenant_read_session_factory", lambda tenant="master": lambda: read_session)
    inj = Injector([Dependencies()])
    set_tenant_context("acme-co")
    try:
        async with inj.get(RequestScopeFactory).create_scope():
            routed = {cls.__name__: inj.get(cls).db for cls in _routed_repositories()}
            write_side = inj.get(ConversationRepository).db
    finally:
        clear_tenant_context()
    return routed, write_side


@pytest.mark.asyncio
async def test_routed_repositories_are_constructed_with_the_read_session_when_enabled(monkeypatch):
    settings.DB_READ_HOST = "reader.internal"
    write_session, read_session = object(), object()

    routed, write_side = await _resolve_repositories_in_a_request(monkeypatch, write_session, read_session)

    for name, session in routed.items():
        assert session is read_session, name
    assert write_side is write_session


@pytest.mark.asyncio
async def test_routed_repositories_are_constructed_with_the_write_session_when_disabled(monkeypatch):
    write_session, read_session = object(), object()

    routed, write_side = await _resolve_repositories_in_a_request(monkeypatch, write_session, read_session)

    for name, session in routed.items():
        assert session is write_session, name
    assert write_side is write_session


# ───────────── which repositories are routed ─────────────


def _session_type_of(repository_class):
    return typing.get_type_hints(repository_class.__init__, include_extras=True)["db"]


def test_read_only_repositories_ask_for_the_read_session():
    from app.repositories.analytics_read import AnalyticsReadRepository
    from app.repositories.dashboard import DashboardRepository
    from app.repositories.llm_usage_read import LlmUsageReadRepository

    for repository_class in (AnalyticsReadRepository, DashboardRepository, LlmUsageReadRepository):
        assert _session_type_of(repository_class) == ReadOnlySession, repository_class.__name__


def test_chat_path_repositories_stay_on_the_write_session():
    from app.repositories.conversations import ConversationRepository
    from app.repositories.transcript_message import TranscriptMessageRepository

    for repository_class in (ConversationRepository, TranscriptMessageRepository):
        assert _session_type_of(repository_class) == AsyncSession, repository_class.__name__
        assert _session_type_of(repository_class) != ReadOnlySession, repository_class.__name__
