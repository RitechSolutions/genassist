"""
Server-sent events for one streamed chat turn. The stream is held in a ContextVar so node hooks, agent-invoked tools and the MCP
executor reach it without a parameter; ``emit_activity`` is a no-op outside a streamed turn.
"""

import asyncio
import json
import logging
import time
from contextvars import ContextVar
from typing import Any, AsyncIterator, Awaitable, Callable, Literal, Optional
from uuid import UUID

from fastapi import Request
from fastapi.responses import StreamingResponse

from app.core.exceptions.exception_handler import stream_error_body
from app.core.utils.background_tasks import spawn
from app.core.utils.db_connection_utils import create_tenant_request_scope
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware

logger = logging.getLogger(__name__)

# Below the 60 s default idle timeout of the load balancer in front of the API.
KEEPALIVE_SECONDS = 15

ActivityKind = Literal["knowledge", "tool"]
ActivityPhase = Literal["start", "end"]

# Node types whose work the chat widget may label. Only the coarse kind leaves the backend;
# node names, ids and types never do, and unlisted types send nothing.
_NODE_ACTIVITY_KINDS: dict[str, ActivityKind] = {
    "knowledgeBaseNode": "knowledge",
    "apiToolNode": "tool",
    "openApiNode": "tool",
    "pythonCodeNode": "tool",
    "sqlNode": "tool",
    "webSearchNode": "tool",
    "webScraperNode": "tool",
    "slackMessageNode": "tool",
    "gmailNode": "tool",
    "readMailsNode": "tool",
    "calendarEventNode": "tool",
    "whatsappToolNode": "tool",
    "zendeskTicketNode": "tool",
    "salesforceCaseNode": "tool",
    "jiraNode": "tool",
    "createWorkflowScheduleNode": "tool",
    "mlModelInferenceNode": "tool",
}

current_stream: ContextVar[Optional["TurnStream"]] = ContextVar("turn_stream", default=None)


class TurnStream:
    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self.started = time.monotonic()
        self.first_seen: set[str] = set()

    def emit(self, event: str, **data: Any) -> None:
        if event in ("activity", "delta") and event not in self.first_seen:
            self.first_seen.add(event)
            logger.info(
                "First %s after %.2fs (conversation %s)",
                event,
                time.monotonic() - self.started,
                self.conversation_id,
            )
        self.queue.put_nowait(f"event: {event}\ndata: {json.dumps(data)}\n\n")

    def close(self) -> None:
        self.queue.put_nowait(None)

    async def frames(self) -> AsyncIterator[str]:
        while True:
            try:
                frame = await asyncio.wait_for(self.queue.get(), KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            if frame is None:
                return
            yield frame


def emit_activity(kind: ActivityKind, phase: ActivityPhase) -> None:
    stream = current_stream.get()
    if stream is not None:
        stream.emit("activity", kind=kind, phase=phase)


def emit_node_activity(node_type: str, phase: ActivityPhase) -> None:
    kind = _NODE_ACTIVITY_KINDS.get(node_type)
    if kind:
        emit_activity(kind, phase)


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
            outcome = body.get("error_key") or f"http_{body['error_code']}"
            stream.emit("error", **body)
        finally:
            stream.close()
            logger.info(
                "Streamed chat turn %s in %.0fms (conversation %s)",
                outcome,
                (time.perf_counter() - started) * 1000,
                conversation_id,
            )

    spawn(run(), name=f"chat-turn:{conversation_id}")
    return StreamingResponse(
        stream.frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
