"""Admission control for agent turns: a per-process cap with a bounded wait for a free place."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable, Optional
from weakref import WeakKeyDictionary

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

logger = logging.getLogger(__name__)

SLOW_WAIT_LOG_THRESHOLD_SECONDS = 1.0

BeforeWait = Callable[[], Awaitable[None]]


class ChatTurnGate:
    """Caps concurrent agent turns in this process; a turn that waits past the timeout gets a 503."""

    def __init__(self, max_inflight: int, queue_timeout_seconds: float):
        self.max_inflight = max_inflight
        self.queue_timeout_seconds = queue_timeout_seconds
        # One semaphore per running loop: a semaphore binds to the loop it first waits on.
        self._semaphores: WeakKeyDictionary = WeakKeyDictionary()

    @asynccontextmanager
    async def slot(self, context: str, before_wait: Optional[BeforeWait] = None) -> AsyncIterator[None]:
        """Hold one place for the block. ``before_wait`` runs only if the turn has to queue."""
        if self.max_inflight <= 0:
            yield
            return

        semaphore = self._semaphore_for_running_loop()
        if semaphore.locked() and before_wait is not None:
            await before_wait()
        await self._acquire(semaphore, context)
        try:
            yield
        finally:
            semaphore.release()

    def _semaphore_for_running_loop(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        semaphore = self._semaphores.get(loop)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self.max_inflight)
            self._semaphores[loop] = semaphore
        return semaphore

    async def _acquire(self, semaphore: asyncio.Semaphore, context: str) -> None:
        started = time.monotonic()
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=self.queue_timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "Agent turn rejected after waiting %.1fs, all %s places taken (%s)",
                self.queue_timeout_seconds,
                self.max_inflight,
                context,
            )
            raise AppException(
                error_key=ErrorKey.CHAT_TURN_CAPACITY_EXCEEDED, status_code=503
            )

        waited = time.monotonic() - started
        if waited >= SLOW_WAIT_LOG_THRESHOLD_SECONDS:
            logger.info(
                "Agent turn waited %.1fs for one of %s places (%s)",
                waited,
                self.max_inflight,
                context,
            )


chat_turn_gate = ChatTurnGate(
    max_inflight=settings.CHAT_TURN_MAX_INFLIGHT,
    queue_timeout_seconds=settings.CHAT_TURN_QUEUE_TIMEOUT_SECONDS,
)
