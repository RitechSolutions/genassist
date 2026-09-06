"""
Celery tasks for test suite run execution.
"""

import logging
from typing import Any, Dict
from uuid import UUID

from celery import shared_task

from app.core.tenant_scope import (
    set_tenant_context,
    clear_tenant_context,
    background_task_context,
)
from app.tasks.base import (
    TERMINAL_RUN_STATUSES,
    create_task_wrapper,
    run_async_in_celery,
    should_execute_run,
)
from app.core.tenant_scope import get_tenant_context
from app.dependencies.injector import injector
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.services.realtime_notifications import emit_notification, notification_payload

logger = logging.getLogger(__name__)

async def _persist_failure(service, run, exc: Exception) -> None:
    """Commit the failed status on its own; the task wrapper rolls back on raise."""
    session = service.run_repo.db
    # The service may already have failed the run in memory and notified the user
    already_notified = run.status in TERMINAL_RUN_STATUSES
    error = (run.summary_metrics or {}).get("error") or f"Run failed unexpectedly: {exc}"
    try:
        await session.rollback()
        await session.refresh(run)
        if run.status in TERMINAL_RUN_STATUSES:
            return
        if already_notified:
            run.status = "failed"
            run.summary_metrics = {"error": error}
            await service.run_repo.update(run)
        else:
            await service._fail_run(run, error)
        await session.commit()
    except Exception:
        logger.error("Could not persist the failed status of TestRun %s", run.id, exc_info=True)


async def _execute_test_suite_run_async(
    run_id: UUID,
    input_metadata: Dict[str, Any] | None,
    technique_configs: Dict[str, Dict[str, Any]] | None,
) -> None:
    """
    Load the TestRun and drive execution via the injected TestSuiteService.
    Must be called within a request scope (via create_task_wrapper) so that
    the DI container resolves the tenant-scoped AsyncSession correctly.
    """
    from app.dependencies.injector import injector
    from app.services.test_suite import TestSuiteService

    service = injector.get(TestSuiteService)

    run = await service.run_repo.get_by_id(run_id)
    if not run:
        logger.warning("TestRun %s not found — skipping", run_id)
        return
    if not should_execute_run("TestRun", run_id, run.status):
        return

    suite = await service.suite_repo.get_by_id(run.suite_id)
    if not suite:
        logger.error("Suite %s not found for run %s", run.suite_id, run_id)
        run.status = "failed"
        run.summary_metrics = {"error": "Suite not found"}
        await service.run_repo.update(run)
        emit_notification(
            socket_connection_manager=injector.get(SocketConnectionManager),
            tenant_id=get_tenant_context(),
            payload=notification_payload(
                notification_id=f"workflow_failed:test:{run_id}",
                title="Workflow Run Failed",
                description=f"Test run {str(run_id)[:8]}... failed.",
                level="error",
                action_url="/tests/evaluations",
                entity_kind="test_run",
                entity_id=run_id,
                event_key=f"workflow_failed:test:{run_id}",
            ),
        )
        return

    try:
        workflow = await service.workflow_service.get_by_id(UUID(str(run.workflow_id)))
        await service._execute_run(
            suite,
            workflow,
            run,
            run_input_metadata=input_metadata,
            technique_configs=technique_configs,
        )
    except Exception as exc:
        logger.error("Test run %s failed: %s", run_id, exc, exc_info=True)
        await _persist_failure(service, run, exc)
        raise


@shared_task(name="execute_test_suite_run")
def execute_test_suite_run_task(
    run_id: str,
    tenant_id: str,
    input_metadata: Dict[str, Any] | None = None,
    technique_configs: Dict[str, Dict[str, Any]] | None = None,
) -> None:
    """
    Celery task that executes all test cases in a suite run asynchronously.

    Args:
        run_id: UUID string of the TestRun to execute.
        tenant_id: Schema name of the tenant that owns this run.
        input_metadata: Optional per-run input metadata override.
        technique_configs: Optional per-technique evaluator configuration.
    """
    logger.info("Starting test suite run execution: %s (tenant: %s)", run_id, tenant_id)
    set_tenant_context(tenant_id)
    # Forces get_tenant_engine() onto the NullPool ("_background") engine instead of
    # the pooled one, so this task never reuses a connection whose event loop
    # run_async_in_celery already closed (a stale pooled connection hangs silently
    # rather than erroring — see the ml-worker asyncio-loop crash history).
    # Context-local (propagates into the run_async_in_celery event loop) so it can't
    # race with other tasks in the same worker.
    with background_task_context():
        try:
            async def _run():
                async def task(**kwargs):
                    await _execute_test_suite_run_async(
                        UUID(kwargs["run_id"]),
                        kwargs.get("input_metadata"),
                        kwargs.get("technique_configs"),
                    )

                wrapper = create_task_wrapper(task)
                await wrapper(
                    run_id=run_id,
                    input_metadata=input_metadata,
                    technique_configs=technique_configs,
                )

            run_async_in_celery(
                _run(),
                timeout=2 * 60 * 60,
                task_name=f"execute_test_suite_run_task[{run_id}]",
            )
        except Exception as exc:
            logger.error("Error in test suite run task %s: %s", run_id, exc, exc_info=True)
            raise
        finally:
            clear_tenant_context()