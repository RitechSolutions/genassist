import logging

from fastapi.testclient import TestClient
from loguru import logger
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette_context.middleware import RawContextMiddleware

from app.auth.utils import API_KEY_HEADER_NAME, generate_api_key
from app.core.config.settings import settings
from app.middlewares._middleware import RequestContextMiddleware
from app.middlewares.tenant_middleware import TenantMiddleware


def test_api_key_path_segment_is_masked_in_both_request_log_lines():
    async def endpoint(_request):
        return JSONResponse({})

    app = Starlette(routes=[Route("/agents/a1/query/{thread_id}", endpoint, methods=["POST"])])
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RawContextMiddleware)
    client = TestClient(app)
    key = generate_api_key()

    paths = []
    handler_id = logger.add(
        paths.append, format="{extra[path]}", filter=lambda r: r["name"] == "app.middlewares._middleware"
    )
    try:
        client.post(f"/agents/a1/query/{key}", headers={API_KEY_HEADER_NAME: key})
        client.post("/agents/a1/query/thread-1", headers={API_KEY_HEADER_NAME: key})
        client.post(f"/agents/a1/query/{key}")
        client.post("/agents/a1/query/thread-1", headers={API_KEY_HEADER_NAME: ""})
        client.post("/agents/a1/query/agent123", headers={API_KEY_HEADER_NAME: "agent123"})
    finally:
        logger.remove(handler_id)

    masked, plain = "/agents/a1/query/[TOKEN]", "/agents/a1/query/thread-1"
    assert [p.strip() for p in paths] == [masked] * 2 + [plain] * 2 + [masked] * 2 + [plain] * 2 + [masked] * 2


def test_at_info_a_request_logs_one_line_and_start_stays_at_debug():
    """The start line repeated the handled line's fields; it is kept for local DEBUG runs only."""

    async def endpoint(_request):
        return JSONResponse({})

    app = Starlette(routes=[Route("/health", endpoint)])
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RawContextMiddleware)
    client = TestClient(app)

    def capture(level):
        lines = []
        handler_id = logger.add(
            lambda m: lines.append(m.record["message"]),
            level=level,
            filter=lambda r: r["name"] == "app.middlewares._middleware",
        )
        try:
            client.get("/health")
        finally:
            logger.remove(handler_id)
        return lines

    assert [m.strip() for m in capture("INFO")] == ["✅ Request handled 200"]
    assert [m.split()[-1] for m in capture("DEBUG")] == ["start", "200"]


def test_multi_tenant_request_logs_tenant_line_at_debug_only(monkeypatch, caplog):
    """On multi-tenant installs the tenant line would add a second INFO line per request."""
    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)

    async def endpoint(_request):
        return JSONResponse({})

    app = Starlette(routes=[Route("/health", endpoint)])
    app.add_middleware(TenantMiddleware)
    app.add_middleware(RawContextMiddleware)
    client = TestClient(app)
    name = "app.middlewares.tenant_middleware"

    def tenant_lines(level):
        caplog.clear()
        with caplog.at_level(level, logger=name):
            client.get("/health", headers={settings.TENANT_HEADER_NAME: "acme"})
        return [r.getMessage() for r in caplog.records if r.name == name]

    assert tenant_lines(logging.INFO) == []
    assert tenant_lines(logging.DEBUG) == ["Request processed with tenant_slug: acme, tenant_id: acme"]
