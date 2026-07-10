"""
Celery tasks for scheduled workflow run execution.

Mirrors the ML model pipeline scheduling pattern: a beat task fires every
minute, finds schedules whose cron is due (and not already run this minute),
creates a PENDING run row and dispatches an execution task. The execution
task resolves the agent's *current* workflow version and runs it.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from celery import shared_task

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import get_tenant_context
from app.core.utils.enums.workflow_schedule_enum import (
    WorkflowScheduleRunStatus,
    ThreadIdMode,
)
from app.db.multi_tenant_session import multi_tenant_manager
from app.dependencies.injector import injector
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.repositories.agent import AgentRepository
from app.repositories.workflow_schedule import WorkflowScheduleRepository
from app.repositories.workflow_schedule_run import WorkflowScheduleRunRepository
from app.services.realtime_notifications import emit_notification, notification_payload
from app.tasks.base import run_async_in_celery

logger = logging.getLogger(__name__)

# Lazily-built PII redactor. Constructed with no entity restriction so it
# redacts the anonymizer's full default set (email, phone, credit card, IP,
# IBAN, SSN, ITIN, passport, driver license, NHS, medical license) — not just
# cardholder data. Built on first use so importing this module (e.g. in celery
# beat) stays cheap.
_pii_redactor = None


def _get_pii_redactor():
    global _pii_redactor
    if _pii_redactor is None:
        from app.modules.workflow.engine.pii_anonymizer import PIIAnonymizer

        _pii_redactor = PIIAnonymizer()
    return _pii_redactor


def _redact_structure(value):
    """Recursively redact PII from every string in a JSON-like structure
    (dict/list/str). Used to sanitize execution_output before it is persisted to
    the run history. Best-effort: a failure on one string leaves that string
    unchanged rather than dropping the whole record."""
    if isinstance(value, str):
        try:
            return _get_pii_redactor().redact(value)
        except Exception:
            return value
    if isinstance(value, dict):
        return {k: _redact_structure(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_structure(v) for v in value]
    return value


# ==================== Execution ====================

async def execute_workflow_run_async(run_id: UUID):
    """Execute a single workflow schedule run for the current tenant."""
    tenant_id = get_tenant_context()
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)

    async with session_factory() as session:
        try:
            run_repository = WorkflowScheduleRunRepository(session)
            schedule_repository = WorkflowScheduleRepository(session)
            agent_repository = AgentRepository(session)

            try:
                # If the run doesn't exist in this tenant's DB, this isn't our
                # tenant (run_task_for_all_tenants iterates every tenant).
                try:
                    run = await run_repository.get_by_id(run_id)
                except AppException as e:
                    if e.error_key == ErrorKey.NOT_FOUND:
                        logger.debug(
                            f"Workflow schedule run {run_id} not found in tenant "
                            f"{tenant_id}, skipping execution"
                        )
                        return None
                    raise

                await run_repository.update_status(
                    run_id, WorkflowScheduleRunStatus.RUNNING
                )

                schedule = await schedule_repository.get_by_id(run.schedule_id)

                # Resolve the agent's CURRENT workflow version so the latest
                # published workflow is always executed.
                agent = await agent_repository.get_by_id_full(schedule.agent_id)
                if not agent or not agent.workflow:
                    raise Exception(
                        f"Agent {schedule.agent_id} has no associated workflow"
                    )
                workflow = agent.workflow

                # Determine the thread id for this run.
                if schedule.thread_id_mode == ThreadIdMode.FIXED.value:
                    thread_id = schedule.fixed_thread_id
                    if not thread_id:
                        # First fixed run with no thread id yet: mint and persist one.
                        thread_id = str(uuid.uuid4())
                        await schedule_repository.set_fixed_thread_id(
                            schedule.id, thread_id
                        )
                else:
                    thread_id = str(uuid.uuid4())

                # Build the input payload (ensure a message key exists).
                input_data = dict(schedule.input_data or {})
                input_data.setdefault("message", "")
                input_data["thread_id"] = thread_id

                workflow_config = {
                    "id": str(workflow.id),
                    "nodes": workflow.nodes or [],
                    "edges": workflow.edges or [],
                }
                workflow_engine = WorkflowEngine(workflow_config)

                state = await workflow_engine.execute_from_node(
                    input_data=input_data, thread_id=thread_id
                )
                # Redact cardholder data from the output before persisting it to
                # the run history (it is stored raw/JSONB otherwise).
                execution_output = _redact_structure(
                    state.format_state_as_response()
                )

                await run_repository.update_status(
                    run_id,
                    WorkflowScheduleRunStatus.COMPLETED,
                    execution_output=execution_output,
                    execution_id=(
                        UUID(state.execution_id) if state.execution_id else None
                    ),
                    workflow_id=workflow.id,
                    thread_id=thread_id,
                )
                logger.info(f"Workflow schedule run {run_id} completed successfully")

            except Exception as e:
                logger.error(
                    f"Error executing workflow schedule run {run_id}: {str(e)}",
                    exc_info=True,
                )
                try:
                    await run_repository.update_status(
                        run_id,
                        WorkflowScheduleRunStatus.FAILED,
                        error_message=str(e),
                    )
                    socket_connection_manager = injector.get(SocketConnectionManager)
                    emit_notification(
                        socket_connection_manager=socket_connection_manager,
                        tenant_id=tenant_id,
                        payload=notification_payload(
                            notification_id=f"workflow_failed:schedule:{run_id}",
                            title="Scheduled Workflow Run Failed",
                            description=f"Scheduled run {str(run_id)[:8]}... failed.",
                            level="error",
                            action_url="/ai-agents",
                            entity_kind="workflow_schedule_run",
                            entity_id=run_id,
                            event_key=f"workflow_failed:schedule:{run_id}",
                        ),
                    )
                except AppException as update_error:
                    if update_error.error_key == ErrorKey.NOT_FOUND:
                        logger.debug(
                            f"Workflow schedule run {run_id} not found in tenant "
                            f"{tenant_id} when updating status, skipping"
                        )
                    else:
                        logger.error(f"Error updating run status: {str(update_error)}")
                except Exception as update_error:
                    logger.error(f"Error updating run status: {str(update_error)}")
        finally:
            await session.close()


async def execute_workflow_run_async_with_scope(run_id: UUID):
    """Run the execution across all tenants (only the owning tenant acts)."""
    from app.tasks.base import create_task_wrapper, run_task_for_all_tenants

    async def task_with_uuid_conversion(**kwargs):
        task_run_id = kwargs.get("run_id", run_id)
        if isinstance(task_run_id, str):
            task_run_id = UUID(task_run_id)
        return await execute_workflow_run_async(task_run_id)

    try:
        logger.info(f"Starting workflow schedule run execution for all tenants: {run_id}")
        wrapper = create_task_wrapper(task_with_uuid_conversion)
        results = await run_task_for_all_tenants(wrapper, run_id=str(run_id))
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error(f"Error in workflow schedule run execution task: {str(e)}")
        return {"status": "failed", "error": str(e)}
    finally:
        logger.debug("Workflow schedule run execution task completed.")


@shared_task(name="execute_workflow_run")
def execute_workflow_run_task(run_id: str):
    """Celery task to execute a scheduled workflow run asynchronously."""
    logger.info(f"Starting workflow schedule run execution: {run_id}")
    try:
        run_async_in_celery(
            execute_workflow_run_async_with_scope(UUID(run_id)),
            timeout=2 * 60 * 60,
            task_name=f"execute_workflow_run_task[{run_id}]",
        )
    except Exception as e:
        logger.error(
            f"Error in workflow schedule run task {run_id}: {str(e)}", exc_info=True
        )
        raise


# ==================== Scheduler (beat) ====================

async def check_and_execute_scheduled_workflows_async():
    """Find schedules whose cron is due in the last minute and dispatch runs."""
    from croniter import croniter

    tenant_id = get_tenant_context()
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)

    async with session_factory() as session:
        try:
            schedule_repository = WorkflowScheduleRepository(session)
            run_repository = WorkflowScheduleRunRepository(session)

            schedules = await schedule_repository.get_active_with_cron()
            current_time = datetime.now(timezone.utc)
            executed_count = 0

            for schedule in schedules:
                if not schedule.cron_schedule:
                    continue
                try:
                    cron_iter = croniter(schedule.cron_schedule, current_time)
                    prev_run_time = cron_iter.get_prev(datetime)
                    time_diff = (current_time - prev_run_time).total_seconds()

                    if not (0 <= time_diff < 60):
                        continue

                    # Dedup: skip if we already created a run within the last minute.
                    last_run = await run_repository.get_last_run(schedule.id)
                    if last_run and last_run.created_at:
                        if (current_time - last_run.created_at).total_seconds() < 60:
                            continue

                    run = await run_repository.create(
                        schedule_id=schedule.id,
                        agent_id=schedule.agent_id,
                    )

                    # Dispatch first so a metadata-write hiccup can never block
                    # the actual execution.
                    execute_workflow_run_task.delay(str(run.id))
                    executed_count += 1
                    logger.info(
                        f"Scheduled workflow run created: {run.id} for schedule {schedule.id}"
                    )

                    # Best-effort: record last run time for display/dedup.
                    try:
                        await schedule_repository.set_last_run_at(
                            schedule.id, current_time
                        )
                    except Exception as e:
                        logger.exception(
                            f"Failed to set last_run_at for schedule {schedule.id}: {str(e)}"
                        )
                except Exception as e:
                    logger.exception(
                        f"Error checking cron schedule for schedule {schedule.id}: {str(e)}"
                    )

            if executed_count > 0:
                logger.info(f"Dispatched {executed_count} scheduled workflow runs")

        except Exception as e:
            logger.exception(
                f"Error checking scheduled workflows: {str(e)}", exc_info=True
            )
        finally:
            await session.close()


async def check_and_execute_scheduled_workflows_async_with_scope():
    """Run the scheduled-workflow check for all tenants."""
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        check_and_execute_scheduled_workflows_async,
        "scheduled workflow check",
    )


@shared_task
def check_scheduled_workflow_runs():
    """Celery beat task to check for due scheduled workflow runs (every minute)."""
    try:
        run_async_in_celery(
            check_and_execute_scheduled_workflows_async_with_scope(),
            timeout=50,
            task_name="check_scheduled_workflow_runs",
        )
    except Exception as e:
        logger.error(
            f"Error in scheduled workflow check task: {str(e)}", exc_info=True
        )
        raise


# ==================== Reconciliation (crash recovery) ====================
#
# Runs are dispatched with Celery's default early-ack, so a run whose worker/pod
# dies mid-execution is never redelivered and would otherwise sit in
# PENDING/RUNNING forever. This sweep marks such runs FAILED once they exceed
# safe age thresholds so the run history stays truthful. It deliberately does
# NOT re-dispatch them, to avoid duplicating side effects (a partially-run
# workflow may already have created tickets, sent messages, etc.). Re-run via
# "Run now" if needed.

_STUCK_RUN_ERROR = (
    "Run did not complete — the worker/pod was lost or restarted "
    "mid-execution and the task was not resumed."
)


async def reconcile_stuck_workflow_runs_async():
    """Fail runs left stuck by a crashed worker for the current tenant."""
    tenant_id = get_tenant_context()
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)

    async with session_factory() as session:
        try:
            run_repository = WorkflowScheduleRunRepository(session)
            now = datetime.now(timezone.utc)
            pending_before = now - timedelta(
                seconds=settings.WORKFLOW_SCHEDULE_PENDING_MAX_AGE_SECONDS
            )
            running_before = now - timedelta(
                seconds=settings.WORKFLOW_SCHEDULE_RUNNING_MAX_AGE_SECONDS
            )
            failed = await run_repository.mark_stuck_as_failed(
                pending_before=pending_before,
                running_before=running_before,
                error_message=_STUCK_RUN_ERROR,
            )
            if failed:
                logger.warning(
                    f"Reconciled {failed} stuck workflow schedule run(s) as FAILED "
                    f"for tenant {tenant_id}"
                )
        except Exception as e:
            logger.error(
                f"Error reconciling stuck workflow runs: {str(e)}", exc_info=True
            )
        finally:
            await session.close()


async def reconcile_stuck_workflow_runs_async_with_scope():
    """Run the stuck-run reconciliation for all tenants."""
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        reconcile_stuck_workflow_runs_async,
        "reconcile stuck workflow runs",
    )


@shared_task
def reconcile_stuck_workflow_runs():
    """Celery beat task to fail runs orphaned by a worker/pod crash."""
    try:
        run_async_in_celery(
            reconcile_stuck_workflow_runs_async_with_scope(),
            timeout=50,
            task_name="reconcile_stuck_workflow_runs",
        )
    except Exception as e:
        logger.error(
            f"Error in stuck-run reconciliation task: {str(e)}", exc_info=True
        )
        raise