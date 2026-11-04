"""Webhook endpoint URLs carry the address callers outside the load balancer use.

TLS ends at the load balancer, so the backend sees plain http requests on the
public host.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from starlette.requests import Request

# Importing app.services.webhook first hits a pre-existing circular import
# (via chat_as_client_use_case); going through the route module avoids it.
from app.api.v1.routes import webhook as webhook_routes
from app.api.v1.routes import webhook_execute
from app.core.config.settings import ProjectSettings, settings
from app.core.utils.webhook_urls import build_public_url
from app.schemas.webhook import WebhookCreate, WebhookResponse
from app.schemas.workflow_trigger import WorkflowTriggerProvision
from app.services.workflow_trigger import WorkflowTriggerService

PUBLIC = "https://api.genassist.ai/api"
BEHIND_TLS = {"x-forwarded-proto": "https"}
NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def tenant_and_no_public_url(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", None)
    with patch("app.core.utils.webhook_urls.get_tenant_context", return_value="acme"):
        yield


def _request(headers=None, host="api.genassist.ai"):
    """What uvicorn hands the app for a call to https://api.genassist.ai."""
    app = FastAPI()
    app.include_router(webhook_execute.router, prefix="/api/webhook/execute")
    raw_headers = [(b"host", host.encode())]
    raw_headers += [(k.encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "server": ("api.genassist.ai", 80),
        "path": "/api/genagent/workflow-triggers/provision",
        "root_path": "",
        "query_string": b"",
        "headers": raw_headers,
        "app": app,
    })


def _stored_row(webhook_id, url):
    return SimpleNamespace(
        id=webhook_id, name="hook", url=url, method="POST", headers={}, secret=None,
        description=None, is_active=1, is_deleted=0, webhook_type="workflow_trigger",
        agent_id=uuid4(), app_settings_id=None, node_id="wt", auth_mode="bearer",
        rate_limit_per_minute=60, created_at=NOW, updated_at=NOW,
    )


def _with_timestamps(model):
    model.created_at = model.updated_at = NOW
    return model


def _trigger_service(row=None):
    webhooks = MagicMock()
    webhooks.get_trigger_by_agent_node = AsyncMock(return_value=None)
    webhooks.create_model = AsyncMock(side_effect=_with_timestamps)
    webhooks.get_by_id = AsyncMock(return_value=row)
    return WorkflowTriggerService(
        webhook_repository=webhooks,
        run_repository=SimpleNamespace(get_last_run=AsyncMock(return_value=None)),
        agent_repository=SimpleNamespace(get_by_id=AsyncMock(return_value=SimpleNamespace(id=uuid4()))),
    )


def test_request_url_takes_the_scheme_the_load_balancer_reports():
    wid = uuid4()
    assert build_public_url(None, _request(BEHIND_TLS), wid) == (
        f"https://api.genassist.ai/api/webhook/execute/{wid}?x-tenant-id=acme"
    )
    assert build_public_url(None, _request(), wid) == (
        f"http://api.genassist.ai/api/webhook/execute/{wid}?x-tenant-id=acme"
    )
    assert build_public_url(None, _request(BEHIND_TLS, host="api.genassist.ai:80"), wid) == (
        f"https://api.genassist.ai/api/webhook/execute/{wid}?x-tenant-id=acme"
    )


def test_configured_public_url_wins_over_caller_base_and_request(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", PUBLIC)
    wid = uuid4()
    expected = f"{PUBLIC}/webhook/execute/{wid}?x-tenant-id=acme"
    assert build_public_url("http://elsewhere/api/", _request(), wid) == expected
    assert build_public_url(None, _request(), wid) == expected
    assert build_public_url(None, None, wid) == expected


def test_caller_base_is_used_without_a_configured_url():
    wid = uuid4()
    for base in ("https://host/api", "https://host/api/"):
        assert build_public_url(base, None, wid) == f"https://host/api/webhook/execute/{wid}?x-tenant-id=acme"


def test_no_address_to_build_from_is_an_error():
    with pytest.raises(ValueError):
        build_public_url(None, None, uuid4())


def test_public_api_url_setting_is_normalized():
    assert ProjectSettings(PUBLIC_API_URL=" https://api.example.com/api/ ").PUBLIC_API_URL == "https://api.example.com/api"
    for unset in ("", "none", "null"):
        assert ProjectSettings(PUBLIC_API_URL=unset).PUBLIC_API_URL is None


def test_a_wrong_public_api_url_is_ignored_with_an_error(caplog):
    wrong_values = (
        "https://api.example.com",
        "api.example.com/api",
        "ftp://api.example.com/api",
        "https://user:S3cret@api.example.com/api",
        "https://api.example.com/api;v=1",
        "https://api.example.com/api?token=S3cret",
        "https://api.example.com/api#x",
        "https://api.example.com:abc/api",
        "https://api.example .com/api",
    )
    for wrong in wrong_values:
        assert ProjectSettings(PUBLIC_API_URL=wrong).PUBLIC_API_URL is None
    assert caplog.text.count("Ignoring PUBLIC_API_URL") == len(wrong_values)
    assert "S3cret" not in caplog.text


@pytest.mark.asyncio
async def test_new_trigger_endpoint_is_https_without_a_base_url():
    created = await _trigger_service().provision(
        WorkflowTriggerProvision(agent_id=uuid4(), node_id="wt"), _request(BEHIND_TLS)
    )
    assert created.created
    assert created.url == f"https://api.genassist.ai/api/webhook/execute/{created.id}?x-tenant-id=acme"


@pytest.mark.asyncio
async def test_new_generic_webhook_is_https_without_a_base_url():
    service = SimpleNamespace(create_webhook=AsyncMock(side_effect=lambda data, url, webhook_id: url))
    url = await webhook_routes.create_webhook(WebhookCreate(name="hook"), _request(BEHIND_TLS), service=service)
    assert url.startswith("https://api.genassist.ai/api/webhook/execute/")


@pytest.mark.asyncio
async def test_existing_http_endpoints_on_the_public_host_become_https(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", PUBLIC)
    wid = uuid4()
    row = _stored_row(wid, f"http://api.genassist.ai/api/webhook/execute/{wid}?x-tenant-id=acme")
    expected = f"https://api.genassist.ai/api/webhook/execute/{wid}?x-tenant-id=acme"

    assert (await _trigger_service(row).get(wid)).url == expected
    assert WebhookResponse.model_validate(row).url == expected


def test_rows_on_other_hosts_or_malformed_keep_their_url(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", PUBLIC)
    wid = uuid4()
    for url in (
        f"http://localhost:8000/api/webhook/execute/{wid}?x-tenant-id=acme",
        f"https://acme.genassist.ai/api/webhook/execute/{wid}?x-tenant-id=acme",
        f"http://[api.genassist.ai/api/webhook/execute/{wid}",
    ):
        assert WebhookResponse.model_validate(_stored_row(wid, url)).url == url


def test_an_http_public_url_never_downgrades_https_rows(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "http://api.genassist.ai/api")
    wid = uuid4()
    url = f"https://api.genassist.ai/api/webhook/execute/{wid}?x-tenant-id=acme"
    assert WebhookResponse.model_validate(_stored_row(wid, url)).url == url


def test_existing_endpoints_keep_their_url_without_a_configured_address():
    wid = uuid4()
    row = _stored_row(wid, f"http://api.genassist.ai/api/webhook/execute/{wid}?x-tenant-id=acme")
    assert WebhookResponse.model_validate(row).url == row.url
