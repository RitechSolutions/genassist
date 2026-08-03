"""Registry for post-response background work owned by the application"""

import asyncio
import logging
from typing import Any, Coroutine

logger = logging.getLogger(__name__)

_TASKS: set[asyncio.Task[Any]] = set()


def _on_done(task: asyncio.Task[Any]) -> None:
    _TASKS.discard(task)
    if task.cancelled():
        logger.warning("Background task %s was cancelled", task.get_name())
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("Background task %s failed", task.get_name(), exc_info=exc)


def spawn(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
    """Schedule ``coro`` as a tracked task. Raises when it cannot be scheduled"""
    try:
        task = asyncio.create_task(coro, name=name)
    except BaseException:
        coro.close()
        raise
    _TASKS.add(task)
    task.add_done_callback(_on_done)
    return task


async def drain(timeout: float = 10.0) -> None:
    """Wait out the tracked tasks. Every one of them is done when this returns"""
    pending = set(_TASKS)
    if not pending:
        return

    logger.info("Draining %d background task(s)", len(pending))
    _, overdue = await asyncio.wait(pending, timeout=timeout)
    if overdue:
        logger.warning(
            "Cancelling %d background task(s) past the drain timeout: %s",
            len(overdue),
            ", ".join(sorted(task.get_name() for task in overdue)),
        )
        for task in overdue:
            task.cancel()
        await asyncio.gather(*overdue, return_exceptions=True)
