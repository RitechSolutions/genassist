from fastapi.testclient import TestClient
from loguru import logger
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette_context.middleware import RawContextMiddleware

from app.auth.utils import API_KEY_HEADER_NAME, generate_api_key
from app.middlewares._middleware import RequestContextMiddleware


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
    finally:
        logger.remove(handler_id)

    masked, plain = "/agents/a1/query/[TOKEN]", "/agents/a1/query/thread-1"
    assert [p.strip() for p in paths] == [masked] * 2 + [plain] * 2 + [masked] * 2 + [plain] * 2
