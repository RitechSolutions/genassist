import asyncio
import logging
import time
from typing import Awaitable, Callable
from uuid import UUID

from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.core.exceptions.exception_handler import stream_error_body
from app.core.turn_stream import TurnStream, current_stream
from app.core.utils.background_tasks import spawn
from app.core.utils.db_connection_utils import create_tenant_request_scope
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware

logger = logging.getLogger(__name__)


def stream_turn(request: Request, run_turn: Callable[[], Awaitable[dict]], conversation_id: UUID) -> StreamingResponse:
    """Stream a chat turn that runs in a tracked task with its own DB scope."""
    stream = TurnStream(str(conversation_id))

    async def run() -> None:
        current_stream.set(stream)
        started = time.perf_counter()
        outcome = "cancelled"
        try:
            async with create_tenant_request_scope():
                payload = await run_turn()
            await ReadAfterWriteMiddleware.remember_write(request)
            outcome = "done"
            stream.emit("done", conversation=payload)
        except Exception as e:
            body = stream_error_body(request, e)
            outcome = f"{body['error_code']} {body.get('error_key') or ''}".rstrip()
            stream.emit("error", **body)
        finally:
            stream.close()
            logger.info(
                "Streamed chat turn %s in %.0fms (conversation %s)",
                outcome,
                (time.perf_counter() - started) * 1000,
                conversation_id,
            )

    task = spawn(run(), name=f"chat-turn:{conversation_id}")
    return StreamingResponse(
        stream.frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        # Holds the request open until the turn ends, even after a disconnect, so a graceful shutdown waits for it.
        background=BackgroundTask(asyncio.wait, [task]),
    )
