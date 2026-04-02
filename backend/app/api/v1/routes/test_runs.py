from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.core.tenant_scope import get_tenant_context
from app.schemas.test_suite import (
    TestResult,
    TestRun,
    TestRunCreate,
)
from app.services.test_suite import TestSuiteService
from app.tasks.test_suite_tasks import execute_test_suite_run_task


router = APIRouter()


@router.post(
    "/suites/{suite_id}/runs",
    response_model=TestRun,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.RUN))],
)
async def run_test_suite(
    suite_id: UUID,
    data: TestRunCreate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """
    Queue a test suite run. Returns immediately with status ``queued``.
    The actual execution is handled by a Celery background worker.
    """
    run = await service.create_run(suite_id, data)
    execute_test_suite_run_task.delay(
        str(run.id),
        get_tenant_context(),
        data.input_metadata,
        data.technique_configs,
    )
    return run


@router.get(
    "/suites/{suite_id}/runs",
    response_model=List[TestRun],
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_runs_for_suite(
    suite_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_runs_for_suite(suite_id)


@router.get(
    "/runs/{run_id}",
    response_model=TestRun,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def get_run(
    run_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.get_run(run_id)


@router.get(
    "/runs/{run_id}/results",
    response_model=List[TestResult],
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_results_for_run(
    run_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_results_for_run(run_id)