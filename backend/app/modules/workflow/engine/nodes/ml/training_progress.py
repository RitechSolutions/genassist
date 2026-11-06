"""
Progress reporting for Train Model runs, and tracking of the fits in progress.

A background training job installs a reporter with ``reporting_to``; the
Train Model node calls ``report`` at each stage. Outside a job (pipelines,
the synchronous execute API) no reporter is installed and ``report`` does
nothing. The reporter is a context variable, so it follows the node into
``asyncio.to_thread`` and must be safe to call from another thread.

``fitting`` counts the model fits running in worker threads. A thread can't
be stopped, so a job that is cancelled or times out while a fit still runs
has to end its worker process to free it (see ml_training_job_tasks).
"""

import logging
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

ProgressReporter = Callable[[Dict[str, Any]], None]

_reporter: ContextVar[Optional[ProgressReporter]] = ContextVar("training_progress_reporter", default=None)

_fits_lock = threading.Lock()
_fits_running = 0


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


def in_training_job() -> bool:
    """True inside a background training job.

    Only a job installs a reporter, and a job has its worker process to
    itself (the "ml" worker runs one task at a time), so process-wide
    settings such as the BLAS thread limit are safe to change there.
    """
    return _reporter.get() is not None


@contextmanager
def fitting() -> Iterator[None]:
    """Mark a model fit as running for the duration of the block."""
    global _fits_running
    with _fits_lock:
        _fits_running += 1
    try:
        yield
    finally:
        with _fits_lock:
            _fits_running -= 1


def fits_running() -> int:
    """How many model fits are running in this process right now."""
    with _fits_lock:
        return _fits_running
