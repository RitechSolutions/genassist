"""
Beat tasks that fail runs orphaned by a lost worker.

Kept free of ML imports so they run on the default worker, outside the ml queue
they watch. A waiting run counts as orphaned only when its job is no longer in
the broker; a running run when it exceeds the maximum run age.
"""

import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional, Set

from celery import current_app, shared_task

from app.core.config.settings import settings
from app.core.tenant_scope import get_tenant_context
from app.db.multi_tenant_session import multi_tenant_manager
from app.repositories.test_suite import TestRunRepository
from app.repositories.workflow_schedule_run import WorkflowScheduleRunRepository
from app.tasks.base import run_async_in_celery, run_task_with_tenant_support

logger = logging.getLogger(__name__)

RUN_QUEUE = "ml"
EVALUATION_RUN_TASK = "execute_test_suite_run"
WORKFLOW_RUN_TASK = "execute_workflow_run"
RECONCILER_TIMEOUT_SECONDS = 240

STUCK_TEST_RUN_ERROR = (
    "Run stopped unexpectedly (its worker crashed or was restarted) and was "
    "marked failed by the reconciliation job."
)
STUCK_WORKFLOW_RUN_ERROR = (
    "Run did not complete — the worker/pod was lost or restarted "
    "mid-execution and the task was not resumed."
)


class BrokerScanError(RuntimeError):
    """The queue holds messages the scan could not read; nothing may be reaped from it."""


@dataclass(frozen=True)
class RunReconciliation:
    kind: str
    repository: Callable
    task_name: str
    waiting_max_age_seconds: int
    running_max_age_seconds: int
    error_message: str


def run_id_from_message(raw, task_name: str) -> Optional[str]:
    """Run id carried by a broker message of ``task_name``, else None."""
    try:
        message = json.loads(raw)
        # Reserved (unacked) entries are stored as [message, exchange, routing_key]
        if isinstance(message, list):
            message = message[0]
        if message["headers"].get("task") != task_name:
            return None
        args = json.loads(base64.b64decode(message["body"]))[0]
        return str(args[0])
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def _read_broker_messages(queue: str) -> list:
    """Raw messages waiting in ``queue`` plus those reserved by a worker."""
    with current_app.connection_for_read() as connection:
        channel = connection.default_channel
        prefix = channel.global_keyprefix or ""
        client = channel.client
        waiting = client.lrange(f"{prefix}{queue}", 0, -1)
        reserved = client.hvals(f"{prefix}{channel.unacked_key}")
        # kombu prefixes LLEN itself, so a mismatch means the raw keys above are wrong
        if not waiting and not reserved and client.llen(queue) > 0:
            raise BrokerScanError(f"queue '{queue}' holds messages the scan cannot read")
        return waiting + reserved


async def run_ids_in_broker(task_name: str, queue: str = RUN_QUEUE) -> Set[str]:
    """Ids of runs whose job still exists in the broker, waiting or executing."""
    # Read inline: the Celery current app is thread-local, and the lists are small
    raw_messages = _read_broker_messages(queue)
    ids = {run_id_from_message(raw, task_name) for raw in raw_messages}
    ids.discard(None)
    return ids


async def orphaned_waiting_runs(candidates: List[str], task_name: str) -> List[str]:
    """Waiting runs whose job is gone; none when the broker cannot be read safely."""
    if not candidates:
        return []
    try:
        present = await run_ids_in_broker(task_name)
    except BrokerScanError as exc:
        logger.warning("%s; leaving waiting runs untouched this round", exc)
        return []
    return [run_id for run_id in candidates if run_id not in present]


async def _reconcile_runs(spec: RunReconciliation) -> None:
    """Fail the current tenant's orphaned runs of one kind."""
    tenant_id = get_tenant_context()
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)
    now = datetime.now(timezone.utc)
    waiting_before = now - timedelta(seconds=spec.waiting_max_age_seconds)
    running_before = now - timedelta(seconds=spec.running_max_age_seconds)

    async with session_factory() as session:
        try:
            repository = spec.repository(session)
            candidates = await repository.get_waiting_ids_older_than(waiting_before)
            failed = await repository.mark_orphaned_as_failed(
                waiting_ids=await orphaned_waiting_runs(candidates, spec.task_name),
                running_before=running_before,
                error_message=spec.error_message,
            )
            # Repos only flush; this out-of-band session owns its commit
            await session.commit()
            if failed:
                logger.warning(
                    "Reconciled %s stuck %s(s) as failed for tenant %s",
                    failed,
                    spec.kind,
                    tenant_id,
                )
        except Exception as exc:
            await session.rollback()
            logger.error("Error reconciling stuck %ss: %s", spec.kind, exc, exc_info=True)
        finally:
            await session.close()


async def reconcile_stuck_test_runs_async() -> None:
    await _reconcile_runs(
        RunReconciliation(
            kind="evaluation run",
            repository=TestRunRepository,
            task_name=EVALUATION_RUN_TASK,
            waiting_max_age_seconds=settings.TEST_RUN_QUEUED_MAX_AGE_SECONDS,
            running_max_age_seconds=settings.TEST_RUN_RUNNING_MAX_AGE_SECONDS,
            error_message=STUCK_TEST_RUN_ERROR,
        )
    )


async def reconcile_stuck_workflow_runs_async() -> None:
    await _reconcile_runs(
        RunReconciliation(
            kind="workflow schedule run",
            repository=WorkflowScheduleRunRepository,
            task_name=WORKFLOW_RUN_TASK,
            waiting_max_age_seconds=settings.WORKFLOW_SCHEDULE_PENDING_MAX_AGE_SECONDS,
            running_max_age_seconds=settings.WORKFLOW_SCHEDULE_RUNNING_MAX_AGE_SECONDS,
            error_message=STUCK_WORKFLOW_RUN_ERROR,
        )
    )


@shared_task
def reconcile_stuck_test_runs():
    """Celery beat task to fail evaluation runs orphaned by a worker/pod loss."""
    run_async_in_celery(
        run_task_with_tenant_support(
            reconcile_stuck_test_runs_async, "reconcile stuck evaluation runs"
        ),
        timeout=RECONCILER_TIMEOUT_SECONDS,
        task_name="reconcile_stuck_test_runs",
    )


@shared_task
def reconcile_stuck_workflow_runs():
    """Celery beat task to fail scheduled workflow runs orphaned by a worker/pod loss."""
    run_async_in_celery(
        run_task_with_tenant_support(
            reconcile_stuck_workflow_runs_async, "reconcile stuck workflow runs"
        ),
        timeout=RECONCILER_TIMEOUT_SECONDS,
        task_name="reconcile_stuck_workflow_runs",
    )
