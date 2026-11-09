import asyncio
import logging
import time
from typing import Any, AsyncIterator, Awaitable, Callable

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.core.exceptions.exception_handler import stream_error_body
from app.core.turn_stream import KEEPALIVE_SECONDS
from app.core.utils.background_tasks import spawn
from app.core.utils.db_connection_utils import create_tenant_request_scope
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware

logger = logging.getLogger(__name__)


KEEPALIVE_HEADER = "x-keepalive"


async def keepalive_json(request: Request, work: Callable[[], Awaitable[Any]], *, name: str) -> Any:
    if request.headers.get(KEEPALIVE_HEADER) != "1":
        return await work()

    async def run() -> bytes:
        started = time.perf_counter()
        outcome = "cancelled"
        try:
            async with create_tenant_request_scope():
                result = await work()
            await ReadAfterWriteMiddleware.remember_write(request)
            body = JSONResponse(jsonable_encoder(result)).body
            outcome = "done"
            return body
        except Exception as e:
            error = stream_error_body(request, e)
            outcome = f"{error['error_code']} {error.get('error_key') or ''}".rstrip()
            return JSONResponse(error).body
        finally:
            logger.info("Kept-alive %s %s in %.0fms", name, outcome, (time.perf_counter() - started) * 1000)

    task = spawn(run(), name=name)

    async def body() -> AsyncIterator[bytes]:
        while not task.done():
            await asyncio.wait([task], timeout=KEEPALIVE_SECONDS)
            if not task.done():
                yield b" "
        yield task.result()

    return StreamingResponse(
        body(),
        media_type="application/json",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        # Holds the request open until the work ends, even after a disconnect, so a graceful shutdown waits for it.
        background=BackgroundTask(asyncio.wait, [task]),
    )
