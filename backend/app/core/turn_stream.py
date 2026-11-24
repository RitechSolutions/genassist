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
from typing import Any, AsyncIterator, Callable, Literal, Optional

logger = logging.getLogger(__name__)

# Below the 60 s default idle timeout of the load balancer in front of the API.
KEEPALIVE_SECONDS = 15

ActivityKind = Literal["knowledge", "tool"]
ActivityPhase = Literal["start", "end"]
# Called with (call_id, text) as one model call writes its reply.
TokenSink = Callable[[str, str], None]

current_stream: ContextVar[Optional["TurnStream"]] = ContextVar("turn_stream", default=None)
# Ids of the nodes whose execution encloses the running code, outermost first.
node_path: ContextVar[tuple[str, ...]] = ContextVar("turn_stream_node_path", default=())


class TurnStream:

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self.started = time.monotonic()
        self.first_seen: set[str] = set()
        self._open_calls: set[str] = set()
        self._muted_calls: set[str] = set()
        self._screen: Literal["empty", "live", "final"] = "empty"
        self._replying_node: Optional[str] = None
        self._text_withheld = False

    def withhold_text(self) -> None:
        self._text_withheld = True

    def text_sink(self, node_id: str) -> Optional[TokenSink]:
        return None if self._text_withheld else partial(self.delta, node_id)

    def delta(self, node_id: str, call_id: str, text: str) -> None:
        """Stream reply text from one model call"""
        if call_id not in self._open_calls and call_id not in self._muted_calls:
            head = text.lstrip()
            if not head:
                return
            if head[0] in "{`" or self._replying_node not in (None, node_id):
                self._muted_calls.add(call_id)
            else:
                self._open_calls.add(call_id)
                self._replying_node = node_id
        if call_id in self._open_calls:
            self._screen = "live"
            self.emit("delta", call_id=call_id, text=text)

    def activity(self, kind: ActivityKind, phase: ActivityPhase) -> None:
        if phase == "start":
            if self._screen == "final":
                return
            if self._screen == "live" and self._replying_node not in node_path.get():
                return
            self._screen = "empty"
        self.emit("activity", kind=kind, phase=phase)

    def end_reply(self, node_id: str) -> None:
        if node_id == self._replying_node:
            self._replying_node = None
            if self._screen == "live":
                self._screen = "final"

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


def emit_step(step_id: str, kind: str, text: str, phase: ActivityPhase = "start", detail: str = "") -> None:
    """
    Narrate one step of an agent's work in plain words ("Adding 3 steps"), so a
    chat can show what is happening instead of a bare "Thinking". ``kind`` groups
    steps for an icon (read, lookup, search, edit, test, finalize, question);
    ``detail`` on the end frame is the outcome ("7 of 7 applied"). A no-op
    outside a streamed turn.
    """
    stream = current_stream.get()
    if stream is not None:
        stream.emit("step", id=step_id, kind=kind, text=text, phase=phase, detail=detail)


def end_reply(node_id: str) -> None:
    stream = current_stream.get()
    if stream is not None:
        stream.end_reply(node_id)
