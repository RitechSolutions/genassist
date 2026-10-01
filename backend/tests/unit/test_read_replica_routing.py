"""Unit tests for read-replica routing: settings, engine fallback, the read session provider and routed repositories"""

import typing
from contextlib import contextmanager

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.tenant_scope import background_task_context, clear_tenant_context, set_tenant_context
from app.db import multi_tenant_session as mts
from app.db.read_routing import allow_replica_reads, reset_replica_reads
from app.db.replica_health import ReplicaSession, replica_health
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
    "DB_READ_POOL_TIMEOUT",
    "DB_READ_STATEMENT_TIMEOUT",
    "DB_STATEMENT_TIMEOUT",
)


class FakeEngine:
    def __init__(self, url, kwargs):
        self.url = url
        self.kwargs = kwargs
        self.disposed = False

    async def dispose(self):
        self.disposed = True


@contextmanager
def http_request_scope():
    """Mirror ReplicaScopeMiddleware, which marks only HTTP scopes eligible for the replica."""
    token = allow_replica_reads()
    try:
        yield
    finally:
        reset_replica_reads(token)


@pytest.fixture(autouse=True)
def restore_settings():
    snapshot = {name: getattr(settings, name) for name in SETTINGS_UNDER_TEST}
    settings.DB_HOST = "writer.internal"
    settings.DB_USER = "user"
    settings.DB_PASS = "secret"
    settings.DB_NAME = "core_db"
    settings.DB_READ_HOST = None
    settings.DB_READ_POOL_SIZE = 20
    settings.DB_READ_MAX_OVERFLOW = 20
    settings.DB_READ_POOL_TIMEOUT = 5
    settings.DB_READ_STATEMENT_TIMEOUT = 120
    settings.DB_STATEMENT_TIMEOUT = 1800
    try:
        yield
    finally:
        for name, value in snapshot.items():
            setattr(settings, name, value)


@pytest.fixture(autouse=True)
def healthy_replica():
    replica_health.reset()
    try:
        yield replica_health
    finally:
        replica_health.reset()


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


def test_read_pool_is_smaller_and_more_impatient_than_the_writer_pool():
    fields = getattr(type(settings), "model_fields", None) or type(settings).__fields__
    assert fields["DB_READ_POOL_SIZE"].default < fields["DB_POOL_SIZE"].default
    assert fields["DB_READ_MAX_OVERFLOW"].default < fields["DB_MAX_OVERFLOW"].default
    assert fields["DB_READ_POOL_TIMEOUT"].default < fields["DB_POOL_TIMEOUT"].default


def test_read_statement_timeout_inherits_the_writer_ceiling_unless_set(monkeypatch):
    """Unset follows a per-environment writer override, so reads are never looser than writes."""
    monkeypatch.setattr(settings, "DB_STATEMENT_TIMEOUT", 60)

    monkeypatch.setattr(settings, "DB_READ_STATEMENT_TIMEOUT", None)
    assert settings.read_statement_timeout == 60

    monkeypatch.setattr(settings, "DB_READ_STATEMENT_TIMEOUT", 30)
    assert settings.read_statement_timeout == 30

    monkeypatch.setattr(settings, "DB_READ_STATEMENT_TIMEOUT", 0)
    assert settings.read_statement_timeout == 0


@pytest.mark.parametrize("writer_timeout", [1800, 0], ids=["writer-default", "writer-unbounded"])
def test_unset_read_statement_timeout_never_exceeds_the_read_pool_cap(monkeypatch, writer_timeout):
    """A generous or disabled writer ceiling must not let slow reads occupy the small read pool."""
    monkeypatch.setattr(settings, "DB_STATEMENT_TIMEOUT", writer_timeout)
    monkeypatch.setattr(settings, "DB_READ_STATEMENT_TIMEOUT", None)
    assert settings.read_statement_timeout == 600


@pytest.mark.parametrize("raw", ["", "  ", "none", "NULL"])
def test_unset_looking_read_statement_timeout_values_mean_inherit(raw):
    assert type(settings)._blank_read_timeout_means_inherit(raw) is None


@pytest.mark.parametrize("raw", ["60", 60, "0", 0])
def test_real_read_statement_timeout_values_pass_through(raw):
    assert type(settings)._blank_read_timeout_means_inherit(raw) == raw


@pytest.mark.parametrize("raw", ["-5", -5])
def test_a_negative_read_statement_timeout_is_rejected(raw):
    with pytest.raises(ValidationError):
        type(settings)(DB_READ_STATEMENT_TIMEOUT=raw)


def test_a_blank_read_statement_timeout_builds_settings_that_inherit():
    built = type(settings)(DB_READ_STATEMENT_TIMEOUT="")
    assert built.DB_READ_STATEMENT_TIMEOUT is None
    assert built.read_statement_timeout == min(built.DB_STATEMENT_TIMEOUT, 600)


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

    writer_server_settings = write_engine.kwargs["connect_args"]["server_settings"]
    assert "default_transaction_read_only" not in writer_server_settings


def test_read_connections_use_their_own_timeouts(created_engines, restore_manager_caches):
    """Each engine gets its own statement timeout; the fixture keeps the values apart so a shared one cannot pass."""
    manager = restore_manager_caches
    settings.DB_READ_HOST = "reader.internal"

    read_engine = manager.get_tenant_read_engine(TENANT)
    write_engine = manager.get_tenant_engine(TENANT)

    assert read_engine.kwargs["pool_timeout"] == settings.DB_READ_POOL_TIMEOUT
    assert write_engine.kwargs["pool_timeout"] == settings.DB_POOL_TIMEOUT

    read_timeout = read_engine.kwargs["connect_args"]["server_settings"]["statement_timeout"]
    write_timeout = write_engine.kwargs["connect_args"]["server_settings"]["statement_timeout"]
    assert read_timeout == str(settings.read_statement_timeout * 1000)
    assert write_timeout == str(settings.DB_STATEMENT_TIMEOUT * 1000)
    assert read_timeout != write_timeout


def test_read_engine_inherits_the_writer_timeout_when_unset(created_engines, restore_manager_caches):
    """Guards the engine wiring: reading the raw field here would be a TypeError on the default."""
    manager = restore_manager_caches
    settings.DB_READ_HOST = "reader.internal"
    settings.DB_READ_STATEMENT_TIMEOUT = None

    read_engine = manager.get_tenant_read_engine(TENANT)

    read_timeout = read_engine.kwargs["connect_args"]["server_settings"]["statement_timeout"]
    assert read_timeout == str(settings.read_statement_timeout * 1000)
    assert read_timeout == "600000"


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
    assert read_factory.class_ is ReplicaSession


# ───────────── middleware wiring ─────────────


def test_replica_middlewares_are_installed_in_the_app():
    """Without these registrations the whole feature silently reverts to the writer."""
    from app.middlewares._middleware import build_middlewares
    from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware
    from app.middlewares.replica_scope_middleware import ReplicaScopeMiddleware
    from app.middlewares.session_cleanup_middleware import TransactionMiddleware

    installed = [middleware.cls for middleware in build_middlewares()]

    assert ReplicaScopeMiddleware in installed
    assert ReadAfterWriteMiddleware in installed
    # Outermost first: the scope marker and the guard must both wrap the endpoint.
    assert installed.index(ReplicaScopeMiddleware) < installed.index(ReadAfterWriteMiddleware)
    assert installed.index(ReadAfterWriteMiddleware) < installed.index(TransactionMiddleware)


def test_replica_scope_middleware_marks_only_http_scopes():
    """Without this guard a dashboard websocket would hold a replica connection for
    the whole connection, which is what the small read pool cannot absorb."""
    from fastapi.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route, WebSocketRoute

    from app.db.read_routing import replica_reads_allowed
    from app.middlewares.replica_scope_middleware import ReplicaScopeMiddleware

    async def http_endpoint(_request):
        return JSONResponse({"eligible": replica_reads_allowed()})

    async def websocket_endpoint(websocket):
        await websocket.accept()
        await websocket.send_json({"eligible": replica_reads_allowed()})
        await websocket.close()

    app = Starlette(routes=[Route("/read", http_endpoint), WebSocketRoute("/ws", websocket_endpoint)])
    app.add_middleware(ReplicaScopeMiddleware)
    client = TestClient(app)

    assert client.get("/read").json() == {"eligible": True}
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json() == {"eligible": False}


# ───────────── dependency injection ─────────────


def test_provider_returns_the_request_write_session_when_replica_disabled():
    from app.dependencies.dependency_injection import Dependencies

    write_session = object()
    with http_request_scope():
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
        with http_request_scope():
            assert Dependencies().provide_read_session(object()) is read_session
    finally:
        clear_tenant_context()
    assert seen_tenants == ["acme-co"]


def test_provider_keeps_non_http_scopes_on_the_write_session():
    """A websocket scope lives for the whole connection, so it must never hold a replica connection."""
    from app.dependencies.dependency_injection import Dependencies

    settings.DB_READ_HOST = "reader.internal"
    write_session = object()
    assert Dependencies().provide_read_session(write_session) is write_session


def test_provider_keeps_background_tasks_on_the_write_session():
    from app.dependencies.dependency_injection import Dependencies

    settings.DB_READ_HOST = "reader.internal"
    write_session = object()
    with http_request_scope(), background_task_context():
        assert Dependencies().provide_read_session(write_session) is write_session


def test_provider_falls_back_to_the_writer_while_the_replica_is_unhealthy(healthy_replica):
    from app.dependencies.dependency_injection import Dependencies

    settings.DB_READ_HOST = "reader.internal"
    write_session = object()
    healthy_replica.mark_failure(RuntimeError("replica down"))
    set_tenant_context("acme-co")
    try:
        with http_request_scope():
            assert Dependencies().provide_read_session(write_session) is write_session
    finally:
        clear_tenant_context()


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
        with http_request_scope():
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
        with http_request_scope():
            async with inj.get(RequestScopeFactory).create_scope():
                assert inj.get(AsyncSession) is write_session
                assert inj.get(ReadOnlySession) is read_session
    finally:
        clear_tenant_context()


def _routed_repositories():
    from app.repositories.analytics_read import AnalyticsReadRepository
    from app.repositories.dashboard import DashboardRepository
    from app.repositories.llm_usage_read import LlmUsageReadRepository

    return (AnalyticsReadRepository, DashboardRepository, LlmUsageReadRepository)


async def _resolve_repositories_in_a_request(monkeypatch, write_sessions, read_sessions):
    """Build every repository through the real injector, as a request would, and return their sessions.

    The factories mint a new object per call, so a dropped request scope shows up as
    a different session per repository instead of passing unnoticed.
    """
    from fastapi_injector import RequestScopeFactory
    from injector import Injector

    from app.dependencies.dependency_injection import Dependencies
    from app.repositories.conversations import ConversationRepository

    monkeypatch.setattr(
        mts.multi_tenant_manager, "get_tenant_session_factory", lambda tenant="master": lambda: write_sessions()
    )
    monkeypatch.setattr(
        mts.multi_tenant_manager, "get_tenant_read_session_factory", lambda tenant="master": lambda: read_sessions()
    )
    inj = Injector([Dependencies()])
    set_tenant_context("acme-co")
    try:
        with http_request_scope():
            async with inj.get(RequestScopeFactory).create_scope():
                routed = {cls.__name__: inj.get(cls).db for cls in _routed_repositories()}
                write_side = inj.get(ConversationRepository).db
    finally:
        clear_tenant_context()
    return routed, write_side


def _session_minter(label):
    """Returns a fresh, identifiable session object on every call."""
    counter = iter(range(1, 1000))
    return lambda: f"{label}-{next(counter)}"


@pytest.mark.asyncio
async def test_routed_repositories_share_one_read_session_when_enabled(monkeypatch):
    """A session per repository would open one replica connection per repository per request."""
    settings.DB_READ_HOST = "reader.internal"

    routed, write_side = await _resolve_repositories_in_a_request(
        monkeypatch, _session_minter("write"), _session_minter("read")
    )

    assert set(routed.values()) == {"read-1"}, routed
    assert write_side == "write-1"


@pytest.mark.asyncio
async def test_routed_repositories_share_the_write_session_when_disabled(monkeypatch):
    routed, write_side = await _resolve_repositories_in_a_request(
        monkeypatch, _session_minter("write"), _session_minter("read")
    )

    assert set(routed.values()) == {"write-1"}, routed
    assert write_side == "write-1"


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
