"""
Progress reporting for Train Model runs.

A background training job installs a reporter with ``reporting_to``; the
Train Model node calls ``report`` at each stage. Outside a job (pipelines,
the synchronous execute API) no reporter is installed and ``report`` does
nothing. The reporter is a context variable, so it follows the node into
``asyncio.to_thread`` and must be safe to call from another thread.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

ProgressReporter = Callable[[Dict[str, Any]], None]

_reporter: ContextVar[Optional[ProgressReporter]] = ContextVar("training_progress_reporter", default=None)


def report(stage: str, message: str, percent: int) -> None:
    """Send a progress update to the current job, if there is one."""
    reporter = _reporter.get()
    if reporter is None:
        return
    try:
        reporter({"stage": stage, "message": message, "percent": max(0, min(100, int(percent)))})
    except Exception as e:  # progress must never fail a training run
        logger.debug(f"Could not report training progress: {e}")


@contextmanager
def reporting_to(reporter: ProgressReporter) -> Iterator[None]:
    """Send every ``report`` made inside this block to ``reporter``."""
    token = _reporter.set(reporter)
    try:
        yield
    finally:
        _reporter.reset(token)
