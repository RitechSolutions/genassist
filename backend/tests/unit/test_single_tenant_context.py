"""Unit tests for tenant context in single-tenant mode: every request must resolve to master"""

import contextvars

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config.settings import settings
from app.core.tenant_scope import require_tenant_context
from app.middlewares.tenant_middleware import TenantMiddleware
from app.middlewares.tenant_scope_middleware import TenantScopeMiddleware


@pytest.fixture
def single_tenant(monkeypatch):
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", False)


def _installed_middleware_classes():
    from app.middlewares._middleware import build_middlewares

    return [middleware.cls for middleware in build_middlewares()]


def test_single_tenant_mode_still_installs_the_scope_middleware(single_tenant):
    """The session provider fails closed, so the scope middleware must run with no resolved tenant."""
    installed = _installed_middleware_classes()
    assert TenantScopeMiddleware in installed
    assert TenantMiddleware not in installed


def test_multi_tenant_mode_resolves_the_tenant_before_scoping_it(monkeypatch):
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)
    installed = _installed_middleware_classes()
    assert installed.index(TenantMiddleware) < installed.index(TenantScopeMiddleware)


def _probe_app(stack):
    app = FastAPI(middleware=stack)

    @app.get("/probe")
    async def probe():
        return {"tenant": require_tenant_context()}

    return app


def _get_probe_in_a_clean_context(app):
    """Earlier tests leave master in the pytest thread's context, which TestClient copies."""
    return contextvars.Context().run(lambda: TestClient(app, raise_server_exceptions=False).get("/probe"))


def _real_stack_without_the_database():
    from app.middlewares._middleware import build_middlewares
    from app.middlewares.session_cleanup_middleware import TransactionMiddleware

    return [middleware for middleware in build_middlewares() if middleware.cls is not TransactionMiddleware]


def test_single_tenant_request_sees_the_master_context_through_the_real_stack(single_tenant):
    response = _get_probe_in_a_clean_context(_probe_app(_real_stack_without_the_database()))
    assert response.status_code == 200
    assert response.json() == {"tenant": "master"}


def test_without_the_scope_middleware_a_single_tenant_request_fails(single_tenant):
    """Negative control: proves the probe above depends on the middleware, not on leftover context."""
    stack = [
        middleware for middleware in _real_stack_without_the_database() if middleware.cls is not TenantScopeMiddleware
    ]
    response = _get_probe_in_a_clean_context(_probe_app(stack))
    assert response.status_code == 500
