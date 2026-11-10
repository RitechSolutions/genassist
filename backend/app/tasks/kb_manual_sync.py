"""Runs a knowledge base's manual sync in the background of the API process."""

import asyncio
import contextlib
import logging
import threading
import time
from typing import Any, Callable, Dict

import redis

from app.core.config.settings import settings
from app.core.utils.background_tasks import spawn
from app.modules.data import manual_sync_runs
from app.modules.data.manual_sync_runs import ManualSyncRunStore
from app.tasks.base import run_task_for_tenant
from app.tasks.kb_batch_tasks import batch_process_files_kb_async

logger = logging.getLogger(__name__)

SYNC_NOT_STARTED_MESSAGE = "Could not start the synchronization. Try again."
# The reason stays in the server log; the page only learns that the sync failed.
SYNC_FAILED_ERROR = "Synchronization failed."


def _open_heartbeat_redis() -> redis.Redis:
    """A blocking client, so the heartbeat thread works while the sync blocks the event loop."""
    return redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        retry_on_timeout=True,
    )


def _keep_running_mark(client: redis.Redis, tenant_id: str, kb_id: str, run_id: str) -> bool:
    """Renew the run's mark. False once a newer run holds the KB or this run has ended."""
    kept = client.eval(
        manual_sync_runs.RENEW_OR_RETAKE,
        2,
        manual_sync_runs.active_key(tenant_id, kb_id),
        manual_sync_runs.result_key(tenant_id, kb_id),
        run_id,
        manual_sync_runs.RUNNING_TTL_SECONDS,
    )
    return bool(kept)


def _start_heartbeat(
    tenant_id: str, kb_id: str, run_id: str, on_superseded: Callable[[], None]
) -> threading.Event:
    """Keep the run's mark alive until the returned event is set or the hold limit is reached."""
    stop_event = threading.Event()
    client = _open_heartbeat_redis()
    started_at = time.monotonic()

    def beat() -> None:
        try:
            while not stop_event.wait(manual_sync_runs.HEARTBEAT_SECONDS):
                held_too_long = time.monotonic() - started_at >= manual_sync_runs.MARK_HOLD_LIMIT_SECONDS
                if held_too_long:
                    logger.warning(f"Manual sync {run_id} of KB {kb_id} is still running; it no longer blocks a new sync")
                    return
                try:
                    still_holds = _keep_running_mark(client, tenant_id, kb_id, run_id)
                except Exception as e:
                    logger.warning(f"Could not renew manual sync {run_id} of KB {kb_id}: {e}")
                    continue
                lost_mark_while_running = not still_holds and not stop_event.is_set()
                if lost_mark_while_running:
                    on_superseded()
                    return
        finally:
            client.close()

    threading.Thread(target=beat, name=f"kb-manual-sync-heartbeat-{run_id}", daemon=True).start()
    return stop_event


async def _save_outcome(store: ManualSyncRunStore, tenant_id: str, kb_id: str, run_id: str, **outcome: Any) -> None:
    """Keep the run's outcome. Saving is safe to repeat, so one Redis error is retried."""
    try:
        saved = await store.finish(tenant_id, kb_id, run_id, **outcome)
    except Exception as e:
        logger.warning(f"Retrying to save the outcome of manual sync {run_id} of KB {kb_id}: {e}")
        saved = await store.finish(tenant_id, kb_id, run_id, **outcome)
    if not saved:
        logger.warning(f"Manual sync {run_id} of KB {kb_id} ended after a newer run took the KB; outcome not kept")


def _sync_succeeded(outcome: Dict[str, Any]) -> bool:
    batch_result = outcome.get("result") or {}
    every_kb_synced = not batch_result.get("kbs_not_synced")
    return outcome.get("status") == "success" and every_kb_synced


async def _record_outcome(
    store: ManualSyncRunStore, tenant_id: str, kb_id: str, run_id: str, outcome: Dict[str, Any]
) -> None:
    """Keep what run_task_for_tenant returned as the run's result or failure."""
    if _sync_succeeded(outcome):
        result = manual_sync_runs.result_for_page(outcome.get("result"))
        await _save_outcome(store, tenant_id, kb_id, run_id, status=manual_sync_runs.STATUS_SUCCEEDED, result=result)
        return
    logger.error(f"Manual sync {run_id} of KB {kb_id} failed: {outcome.get('error') or outcome.get('result')}")
    await _save_outcome(store, tenant_id, kb_id, run_id, status=manual_sync_runs.STATUS_FAILED, error=SYNC_FAILED_ERROR)


def _being_cancelled() -> bool:
    """Whether this coroutine itself was cancelled (server shutdown), not only the sync it awaited."""
    task = asyncio.current_task()
    return bool(task and task.cancelling())


async def _run_manual_sync(store: ManualSyncRunStore, tenant_id: str, kb_id: str, run_id: str) -> None:
    loop = asyncio.get_running_loop()
    sync = asyncio.create_task(
        run_task_for_tenant(batch_process_files_kb_async, "Manual KB sync", tenant_id, kb_id=kb_id)
    )
    superseded = threading.Event()

    def on_superseded() -> None:
        superseded.set()
        with contextlib.suppress(RuntimeError):  # the loop already closed
            loop.call_soon_threadsafe(sync.cancel)

    stop_heartbeat = _start_heartbeat(tenant_id, kb_id, run_id, on_superseded)
    try:
        outcome = await sync
    except asyncio.CancelledError:
        stopped_for_newer_run = superseded.is_set() and not _being_cancelled()
        if stopped_for_newer_run:
            logger.warning(f"Manual sync {run_id} of KB {kb_id} stopped: a newer run holds the KB")
            return
        # Server shutdown: the mark expires and the page reports the sync as stopped.
        sync.cancel()
        raise
    finally:
        stop_heartbeat.set()
    await _record_outcome(store, tenant_id, kb_id, run_id, outcome)


async def start_manual_sync(store: ManualSyncRunStore, tenant_id: str, kb_id: str) -> Dict[str, Any]:
    """Start the sync in the background, unless one is already in progress for the knowledge base."""
    run_id, active_run_id = await store.claim_or_find_active(tenant_id, kb_id)
    if active_run_id:
        return {"status": "already_running", "run_id": active_run_id}
    if not run_id:
        return {"status": "error", "message": SYNC_NOT_STARTED_MESSAGE}
    # Tracked by the app, so a shutdown waits for it briefly and then stops it.
    spawn(_run_manual_sync(store, tenant_id, kb_id, run_id), name=f"kb-manual-sync-{run_id}")
    return {"status": "started", "run_id": run_id}
