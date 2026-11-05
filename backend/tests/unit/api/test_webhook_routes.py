"""Unit tests for the webhook routes: WebhookService comes from the app's injector, so a lost @inject fails here"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_injector import RequestScopeFactory
from starlette.middleware import Middleware

from app import add_di_middleware
from app.api.v1.routes._routes import register_routers
from app.auth.dependencies import auth
from app.core.tenant_scope import set_tenant_context
from app.db.multi_tenant_session import multi_tenant_manager
from app.dependencies.injector import injector
from app.middlewares.tenant_scope_middleware import TenantScopeMiddleware
from app.repositories.webhook_repository import WebhookRepository
from app.services.webhook import WebhookService
from app.services.workflow_trigger import WorkflowTriggerService


@pytest.fixture
def no_webhooks(monkeypatch):
    """Fake sessions and an empty webhooks table."""
    monkeypatch.setattr(multi_tenant_manager, "get_tenant_session_factory", lambda tenant: MagicMock)
    monkeypatch.setattr(WebhookRepository, "get_all", AsyncMock(return_value=[]))
    monkeypatch.setattr(WebhookRepository, "get_by_id", AsyncMock(return_value=None))
    monkeypatch.setattr(WebhookRepository, "get_by_id_full", AsyncMock(return_value=None))


@pytest.fixture(scope="module")
def webhook_app():
    """The real routers and injector, signed in."""
    app = FastAPI(middleware=[Middleware(TenantScopeMiddleware)])
    add_di_middleware(app)
    register_routers(app)
    app.dependency_overrides[auth] = lambda: None
    return app


@pytest.fixture
def api(webhook_app, no_webhooks):
    return TestClient(webhook_app, raise_server_exceptions=False)


@pytest.mark.asyncio
async def test_the_injector_builds_the_webhook_service(no_webhooks):
    set_tenant_context("master")
    async with injector.get(RequestScopeFactory).create_scope():
        service = injector.get(WebhookService)

    assert isinstance(service.repo, WebhookRepository)
    assert isinstance(service.trigger_service, WorkflowTriggerService)


def test_the_webhook_list_loads(api):
    response = api.get("/api/webhooks")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/api/webhook/execute/{id}", None),
        ("GET", "/api/webhook/execute/{id}", None),
        ("GET", "/api/webhooks/{id}", None),
        ("PUT", "/api/webhooks/{id}", {"name": "renamed"}),
        ("DELETE", "/api/webhooks/{id}", None),
    ],
)
def test_an_unknown_webhook_id_is_404(api, method, path, body):
    response = api.request(method, path.format(id=uuid4()), json=body)

    # The service's 404, not FastAPI's for a missing route
    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not found"}
