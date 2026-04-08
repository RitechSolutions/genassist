"""
Celery tasks for test suite run execution.
"""

import asyncio
import logging
from typing import Any, Dict
from uuid import UUID

from celery import shared_task

from app.core.tenant_scope import set_tenant_context, clear_tenant_context
from app.tasks.base import create_task_wrapper

logger = logging.getLogger(__name__)


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
        return

    workflow = await service.workflow_service.get_by_id(UUID(str(run.workflow_id)))

    await service._execute_run(
        suite,
        workflow,
        run,
        run_input_metadata=input_metadata,
        technique_configs=technique_configs,
    )


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
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

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

        loop.run_until_complete(_run())
    except Exception as exc:
        logger.error("Error in test suite run task %s: %s", run_id, exc, exc_info=True)
        raise
    finally:
        clear_tenant_context()