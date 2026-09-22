"""
Hard stop for tasks on the solo pool.

The solo pool runs each task in the worker's main thread and cannot enforce Celery's
time limits. A task wedged in blocking code then outlives every timeout, and the broker
redelivers its message while the original still runs. This watchdog ends the worker
process once a task passes its hard limit; the orchestrator restarts the worker, and the
redelivered message fails the run instead of running it again.
"""

import logging
import os
import threading
from typing import Callable, Dict, Optional

from celery.signals import celeryd_after_setup, task_postrun, task_prerun

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# Fires this long after the hard limit, so a pool that can enforce limits acts first
GRACE_SECONDS = 60


def _exit_process() -> None:
    logging.shutdown()
    os._exit(1)


def hard_limit_for(task, conf) -> Optional[int]:
    """The task's own hard limit, else the global one."""
    return getattr(task, "time_limit", None) or conf.task_time_limit


def is_solo_pool(pool_cls) -> bool:
    name = pool_cls if isinstance(pool_cls, str) else getattr(pool_cls, "__module__", "")
    return name == "solo" or name.endswith(".solo")


class TaskWatchdog:
    """One timer per running task; an expired timer ends the worker process."""

    def __init__(
        self,
        terminate: Callable[[], None] = _exit_process,
        timer_factory: Callable = threading.Timer,
    ):
        self._terminate = terminate
        self._timer_factory = timer_factory
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def arm(self, task_id: str, task_name: str, hard_limit_seconds: int) -> None:
        delay = hard_limit_seconds + GRACE_SECONDS
        timer = self._timer_factory(delay, self._expire, args=(task_id, task_name, hard_limit_seconds))
        timer.daemon = True
        with self._lock:
            self._timers[task_id] = timer
        timer.start()

    def disarm(self, task_id: str) -> None:
        with self._lock:
            timer = self._timers.pop(task_id, None)
        if timer is not None:
            timer.cancel()

    def _expire(self, task_id: str, task_name: str, hard_limit_seconds: int) -> None:
        logger.critical(
            "%s[%s] is still running %ss past its %ss hard limit on the solo pool; "
            "stopping the worker",
            task_name,
            task_id,
            GRACE_SECONDS,
            hard_limit_seconds,
        )
        self._terminate()


_watchdog: Optional[TaskWatchdog] = None


def install(watchdog: Optional[TaskWatchdog] = None) -> TaskWatchdog:
    global _watchdog
    _watchdog = watchdog or TaskWatchdog()
    task_prerun.connect(on_task_start, weak=False)
    task_postrun.connect(on_task_end, weak=False)
    return _watchdog


def on_task_start(task_id=None, task=None, **kwargs) -> None:
    if _watchdog is None:
        return
    hard_limit = hard_limit_for(task, task.app.conf)
    if hard_limit:
        _watchdog.arm(task_id, task.name, hard_limit)


def on_task_end(task_id=None, **kwargs) -> None:
    if _watchdog is not None:
        _watchdog.disarm(task_id)


@celeryd_after_setup.connect
def on_worker_setup(sender=None, instance=None, **kwargs) -> None:
    if not settings.CELERY_SOLO_WATCHDOG_ENABLED:
        return
    pool_cls = getattr(instance, "pool_cls", None) or settings.CELERY_WORKER_POOL
    if not is_solo_pool(pool_cls):
        return
    install()
    logger.info("Solo pool watchdog installed; a task is stopped %ss past its hard limit", GRACE_SECONDS)
