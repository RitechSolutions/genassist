"""
Celery tasks for test suite run execution.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID

from celery import shared_task

from app.core.config.settings import settings
from app.core.tenant_scope import (
    set_tenant_context,
    clear_tenant_context,
    background_task_context,
)
from app.tasks.base import create_task_wrapper, run_async_in_celery
from app.core.tenant_scope import get_tenant_context
from app.db.multi_tenant_session import multi_tenant_manager
from app.dependencies.injector import injector
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.repositories.test_suite import TestRunRepository
from app.services.realtime_notifications import emit_notification, notification_payload

logger = logging.getLogger(__name__)

_STUCK_TEST_RUN_ERROR = (
    "Run stopped unexpectedly (its worker crashed or was restarted) and was "
    "marked failed by the reconciliation job."
)


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
        if run.status not in ("completed", "failed"):
            await service._fail_run(run, f"Run failed unexpectedly: {exc}")
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


async def reconcile_stuck_test_runs_async() -> None:
    """Fail evaluation runs left stuck by a crashed worker for the current tenant."""
    tenant_id = get_tenant_context()
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)

    async with session_factory() as session:
        try:
            run_repository = TestRunRepository(session)
            now = datetime.now(timezone.utc)
            queued_before = now - timedelta(
                seconds=settings.TEST_RUN_QUEUED_MAX_AGE_SECONDS
            )
            running_before = now - timedelta(
                seconds=settings.TEST_RUN_RUNNING_MAX_AGE_SECONDS
            )
            failed = await run_repository.mark_stuck_as_failed(
                queued_before=queued_before,
                running_before=running_before,
                error_message=_STUCK_TEST_RUN_ERROR,
            )
            # Repos only flush now; this out-of-band session owns its commit.
            await session.commit()
            if failed:
                logger.warning(
                    "Reconciled %s stuck evaluation run(s) as failed for tenant %s",
                    failed,
                    tenant_id,
                )
        except Exception as exc:
            await session.rollback()
            logger.error("Error reconciling stuck evaluation runs: %s", exc, exc_info=True)
        finally:
            await session.close()


async def reconcile_stuck_test_runs_async_with_scope():
    """Run the stuck-run reconciliation for all tenants."""
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        reconcile_stuck_test_runs_async,
        "reconcile stuck evaluation runs",
    )


@shared_task
def reconcile_stuck_test_runs():
    """Celery beat task to fail evaluation runs orphaned by a worker/pod crash."""
    try:
        run_async_in_celery(
            reconcile_stuck_test_runs_async_with_scope(),
            timeout=50,
            task_name="reconcile_stuck_test_runs",
        )
    except Exception as exc:
        logger.error("Error in stuck evaluation-run reconciliation task: %s", exc, exc_info=True)
        raise