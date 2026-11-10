"""Celery task running a workflow test run that trains a model (see app.modules.workflow.training_jobs)."""

import asyncio
import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict

import redis
from celery import shared_task
from redis.asyncio import Redis

from app.core.config.settings import settings
from app.core.exceptions.error_policy import sanitize_error_detail
from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import get_tenant_context
from app.core.utils.uuid_utils import coerce_uuid
from app.modules.workflow import training_jobs
from app.modules.workflow.usage_context import WorkflowUsageContext
from app.tasks.base import run_async_in_celery, run_task_for_tenant

logger = logging.getLogger(__name__)

def _error_message(error: BaseException) -> str:
    if isinstance(error, AppException):
        return sanitize_error_detail(error.error_detail or error.error_key.value)
    if isinstance(error, asyncio.TimeoutError):
        return f"Training did not finish within {training_jobs.JOB_TIMEOUT_SECONDS // 60} minutes."
    return sanitize_error_detail(str(error)) or "Training failed."


def _redis_options() -> Dict[str, Any]:
    return {
        "decode_responses": True,
        "socket_timeout": settings.REDIS_SOCKET_TIMEOUT,
        "socket_connect_timeout": settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        "retry_on_timeout": True,
    }


def _open_job_redis() -> Redis:
    """A Redis client for one job, opened and closed in the task's own event loop.

    run_async_in_celery gives every task a new event loop, and the shared
    injector client's pool lock stays bound to the loop that first waited on
    it, so a later job fails when it saves its result.
    """
    return Redis.from_url(settings.REDIS_URL, **_redis_options())


def _open_heartbeat_redis() -> redis.Redis:
    """A blocking client for the heartbeat thread, which has no event loop."""
    return redis.Redis.from_url(settings.REDIS_URL, **_redis_options())


def _start_heartbeat(tenant_id: str, job_id: str, progress_snapshot, on_cancel: Callable[[], None]) -> threading.Event:
    """Publish the job's progress every HEARTBEAT_SECONDS until the returned event is set.

    A thread rather than an asyncio task: loading or preparing a large file
    runs on the event loop and would hold an asyncio heartbeat back long
    enough for a job that is still running to look like its worker died.
    Each beat also checks whether the user cancelled the job, and calls
    on_cancel once if they did.
    """
    stop = threading.Event()
    client = _open_heartbeat_redis()

    def cancelled() -> bool:
        raw = client.get(training_jobs.job_key(tenant_id, job_id))
        return bool(raw) and json.loads(raw).get("status") == training_jobs.STATUS_CANCELLED

    def beat() -> None:
        try:
            while not stop.wait(training_jobs.HEARTBEAT_SECONDS):
                try:
                    client.set(
                        training_jobs.heartbeat_key(tenant_id, job_id),
                        training_jobs.heartbeat_value(progress_snapshot()),
                        ex=settings.ML_TRAINING_JOB_TTL_SECONDS,
                    )
                    if cancelled():
                        on_cancel()
                        return
                except Exception as e:
                    logger.warning(f"Could not update training job {job_id}: {e}")
        finally:
            client.close()

    threading.Thread(target=beat, name=f"training-job-heartbeat-{job_id}", daemon=True).start()
    return stop


def _stop_worker() -> None:
    """End the worker process, as tasks.solo_watchdog does for a wedged task.

    The orchestrator restarts the worker; the job is already marked
    finished, so its redelivered message skips itself.
    """
    logging.shutdown()
    os._exit(1)


def _free_worker_if_still_fitting(job_id: str) -> None:
    """Stop the worker when a job timed out while a model fit still runs in a thread.

    A thread can't be stopped: cancelling the job's coroutine leaves the fit
    running, holding the "ml" worker (and asyncio.run would wait for it on exit).
    Only the timeout does this. A user's cancel lets the fit end on its own
    (it is bounded by ML_HPO_MAX_FITS and this timeout), so cancelling can't
    be used to keep restarting the worker every tenant shares.
    """
    from app.modules.workflow.engine.nodes.ml import training_progress

    if training_progress.fits_running() == 0:
        return
    logger.critical(f"Training job {job_id} timed out while a model fit was still running; stopping the worker to end it")
    _stop_worker()


async def run_training_job_async(job_id: str, payload: Dict[str, Any]) -> None:
    """Execute the job's workflow and record its progress and result."""
    redis = _open_job_redis()
    try:
        await _run_job(training_jobs.TrainingJobStore(redis), job_id, payload)
    finally:
        await redis.aclose()


async def _execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the test exactly as the test endpoint would have, and return its response."""
    from app.modules.workflow.engine.workflow_engine import WorkflowEngine
    from app.modules.workflow.test_runs import run_workflow_test

    workflow_config = payload["workflow_config"]
    engine = WorkflowEngine(workflow_config)
    input_data = payload.get("input_data") or {}
    usage_context = WorkflowUsageContext(
        source=payload.get("usage_source", "workflow_test"),
        workflow_id=coerce_uuid(payload.get("workflow_id") or engine.workflow_id),
        # Recorded inline: asyncio.run cancels deferred capture tasks when the task ends.
        defer_capture=False,
    )
    if payload.get("kind") == "workflow":
        # Sub-agent routing and registry-managed threads, as in POST /workflows/test.
        return await run_workflow_test(
            engine,
            workflow_config["id"],
            input_data,
            payload["thread_id"],
            payload.get("start_node_id"),
            usage_context,
        )
    state = await engine.execute_from_node(
        start_node_id=payload.get("start_node_id"),
        input_data=input_data,
        thread_id=payload.get("thread_id"),
        usage_context=usage_context,
    )
    return state.format_state_as_response()


async def _run_job(store: training_jobs.TrainingJobStore, job_id: str, payload: Dict[str, Any]) -> None:
    # Imported here so the worker master stays free of ML libraries.
    from app.modules.workflow.engine.nodes.ml import training_progress

    tenant_id = get_tenant_context()
    job = await store.get(tenant_id, job_id)
    status = training_jobs.public_view(job)["status"] if job else "not found"
    if status != training_jobs.STATUS_QUEUED:
        # Expired, cancelled before it started, a redelivered message for a job
        # that already ran, or a job that waited so long the client was already
        # told it failed.
        logger.info(f"Skipping training job {job_id}: {status}")
        return

    started = time.monotonic()
    progress: Dict[str, Any] = {"stage": "starting", "message": "Starting", "percent": 1}

    def reporter(update: Dict[str, Any]) -> None:
        # Called from the training thread; the heartbeat thread writes it out.
        progress.update(update)

    def progress_snapshot() -> Dict[str, Any]:
        return {**progress, "elapsed_seconds": int(time.monotonic() - started)}

    if not await store.update(
        tenant_id,
        job_id,
        expect=(training_jobs.STATUS_QUEUED,),
        status=training_jobs.STATUS_RUNNING,
        progress=progress_snapshot(),
    ):
        logger.info(f"Skipping training job {job_id}: it was cancelled before it started")
        return
    loop = asyncio.get_running_loop()
    with training_progress.reporting_to(reporter):
        # A task (created inside the block, so it carries the reporter) that
        # the heartbeat thread can cancel when the user cancels the job.
        run = asyncio.create_task(_execute(payload))
    cancel_requested = threading.Event()

    def on_cancel() -> None:
        cancel_requested.set()
        loop.call_soon_threadsafe(run.cancel)

    stop_heartbeat = _start_heartbeat(tenant_id, job_id, progress_snapshot, on_cancel)
    try:
        result = await run
        stop_heartbeat.set()
        # Only over "running": a cancel that came in meanwhile stands.
        await store.update(
            tenant_id,
            job_id,
            expect=(training_jobs.STATUS_RUNNING,),
            status=training_jobs.STATUS_SUCCEEDED,
            result=result,
            progress={**progress_snapshot(), "stage": "done", "message": "Finished", "percent": 100},
        )
    except asyncio.CancelledError:
        stop_heartbeat.set()
        if cancel_requested.is_set() and not _being_cancelled():
            # The user cancelled: the job already says so. A fit still running
            # in its thread ends on its own; the worker is not restarted.
            logger.info(f"Training job {job_id} was cancelled")
            return
        # run_async_in_celery's timeout cancelled this coroutine.
        run.cancel()
        logger.error(f"Training job {job_id} timed out")
        await store.update(
            tenant_id,
            job_id,
            expect=(training_jobs.STATUS_RUNNING,),
            status=training_jobs.STATUS_FAILED,
            error=_error_message(asyncio.TimeoutError()),
            progress=progress_snapshot(),
        )
        _free_worker_if_still_fitting(job_id)
        raise
    except Exception as e:
        stop_heartbeat.set()
        logger.error(f"Training job {job_id} failed: {e}", exc_info=not isinstance(e, AppException))
        await store.update(
            tenant_id,
            job_id,
            expect=(training_jobs.STATUS_RUNNING,),
            status=training_jobs.STATUS_FAILED,
            error=_error_message(e),
            progress=progress_snapshot(),
        )


def _being_cancelled() -> bool:
    """Whether this coroutine itself was cancelled (the timeout), not only the run it awaited."""
    task = asyncio.current_task()
    return bool(task and task.cancelling())


async def run_training_job_for_tenant(job_id: str, tenant_id: str, payload: Dict[str, Any]):
    async def _run(**kwargs):
        return await run_training_job_async(kwargs["job_id"], kwargs["payload"])

    return await run_task_for_tenant(_run, "ML training job", tenant_id, job_id=job_id, payload=payload)


@shared_task(name="run_ml_training_job")
def run_training_job_task(job_id: str, tenant_id: str | None, payload: Dict[str, Any]):
    """Celery task: run one workflow test run that trains a model, in its tenant."""
    logger.info("Starting ML training job %s for tenant %s", job_id, tenant_id)
    run_async_in_celery(
        run_training_job_for_tenant(job_id, tenant_id or "master", payload),
        timeout=2 * 60 * 60,
        task_name=f"run_ml_training_job[{job_id}]",
    )
