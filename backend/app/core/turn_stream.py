"""
Server-sent events for one streamed chat turn. The stream is held in a ContextVar so node hooks, agent-invoked tools and the MCP
executor reach it without a parameter; ``emit_activity`` is a no-op outside a streamed turn.
"""

import asyncio
import json
import logging
import time
from contextvars import ContextVar
from functools import partial
from typing import Any, AsyncIterator, Awaitable, Callable, Literal, Optional
from uuid import UUID

from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.core.exceptions.exception_handler import stream_error_body
from app.core.utils.background_tasks import spawn
from app.core.utils.db_connection_utils import create_tenant_request_scope
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware

logger = logging.getLogger(__name__)

# Below the 60 s default idle timeout of the load balancer in front of the API.
KEEPALIVE_SECONDS = 15

ActivityKind = Literal["knowledge", "tool"]
ActivityPhase = Literal["start", "end"]
# Called with (call_id, text) as one model call writes its reply.
TokenSink = Callable[[str, str], None]

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
        self._calls: dict[str, Optional[str]] = {}
        self._shown_call: Optional[str] = None
        self._reply_final = False
        self._replying_node: Optional[str] = None
        self._text_withheld = False

    def withhold_text(self) -> None:
        self._text_withheld = True

    def text_sink(self, node_id: str) -> Optional[TokenSink]:
        return None if self._text_withheld else partial(self.delta, node_id)

    def delta(self, node_id: str, call_id: str, text: str) -> None:
        """Stream reply text from one model call"""
        if call_id not in self._calls:
            head = text.lstrip()
            if not head:
                return
            muted = head[0] in "{`" or self._replying_node not in (None, node_id)
            self._calls[call_id] = None if muted else ""
            if not muted:
                self._replying_node = node_id
        if self._calls[call_id] is not None:
            self._calls[call_id] += text
            self._shown_call = call_id
            self._reply_final = False
            self.emit("delta", call_id=call_id, text=text)

    def activity(self, kind: ActivityKind, phase: ActivityPhase) -> None:
        if phase == "start":
            if self._reply_final:
                return
            self._shown_call = None
        self.emit("activity", kind=kind, phase=phase)

    def end_reply(self, node_id: str) -> None:
        if node_id == self._replying_node:
            self._replying_node = None
            self._reply_final = self._shown_call is not None

    def shown_text(self) -> Optional[str]:
        return self._calls[self._shown_call] if self._shown_call else None

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
        stream.activity(kind, phase)


def end_reply(node_id: str) -> None:
    stream = current_stream.get()
    if stream is not None:
        stream.end_reply(node_id)


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
