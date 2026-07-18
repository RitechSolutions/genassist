import logging
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.core.tenant_scope import get_tenant_context
from app.dependencies.dependency_injection import RedisString
from app.dependencies.injector import injector
from app.schemas.test_suite import (
    PaginatedEvaluations,
    StartedEvaluationRun,
    TestEvaluation,
    TestEvaluationCreate,
    TestEvaluationUpdate,
    WorkflowEvaluationSummary,
)
from app.services.test_suite import TestSuiteService
from app.tasks.test_suite_tasks import execute_test_suite_run_task


logger = logging.getLogger(__name__)

router = APIRouter()

# Safety-net TTL for the Run-all lock; released explicitly on completion.
RUN_ALL_LOCK_TTL_SECONDS = 120

# Release only if we still own the lock (token match), so an expired-and-reacquired
# lock held by another request is never deleted by ours.
_RELEASE_LOCK_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) else return 0 end"
)


@router.get(
    "/evaluations",
    response_model=List[TestEvaluation],
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_evaluations(
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_evaluations()


@router.post(
    "/evaluations",
    response_model=TestEvaluation,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def create_evaluation(
    data: TestEvaluationCreate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.create_evaluation(data)


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=TestEvaluation,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def get_evaluation(
    evaluation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.get_evaluation(evaluation_id)


@router.patch(
    "/evaluations/{evaluation_id}",
    response_model=TestEvaluation,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def update_evaluation(
    evaluation_id: UUID,
    data: TestEvaluationUpdate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.update_evaluation(evaluation_id, data)


@router.post(
    "/evaluations/{evaluation_id}/runs/{run_id}",
    response_model=TestEvaluation,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def append_run_to_evaluation(
    evaluation_id: UUID,
    run_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.append_run_to_evaluation(evaluation_id, str(run_id))


@router.delete(
    "/evaluations/{evaluation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def delete_evaluation(
    evaluation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    await service.delete_evaluation(evaluation_id)


@router.post(
    "/workflows/{workflow_id}/evaluations/run",
    response_model=List[StartedEvaluationRun],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.RUN))],
)
async def run_workflow_evaluations(
    workflow_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """
    Queue a run for every evaluation that targets this workflow. Returns the
    per-evaluation outcome immediately; execution is handled by background
    workers. Evaluations that could not be queued are reported individually.

    A Redis ``SET NX`` lock makes the "no active run?" check and the batch start
    one atomic operation, so two concurrent requests cannot both start a batch.
    Refuses with 409 while a batch is starting or the workflow already has
    queued/running evaluations.
    """
    conflict = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="This workflow already has running evaluations.",
    )
    redis = injector.get(RedisString)
    lock_key = f"tenant:{get_tenant_context()}:eval-run-all:{workflow_id}"
    lock_token = uuid4().hex
    acquired = await redis.set(
        lock_key, lock_token, nx=True, ex=RUN_ALL_LOCK_TTL_SECONDS
    )
    if not acquired:
        raise conflict

    try:
        if await service.workflow_has_active_run(workflow_id):
            raise conflict

        tenant = get_tenant_context()

        def dispatch(run, input_metadata, technique_configs):
            execute_test_suite_run_task.delay(
                str(run.id),
                tenant,
                input_metadata,
                technique_configs,
            )

        return await service.start_workflow_evaluations(workflow_id, dispatch)
    finally:
        # Compare-and-delete so we only release our own lock; never let a release
        # error mask the actual response.
        try:
            await redis.eval(_RELEASE_LOCK_LUA, 1, lock_key, lock_token)
        except Exception:
            logger.warning("Failed to release Run-all lock %s", lock_key, exc_info=True)


@router.get(
    "/workflows/evaluation-summaries",
    response_model=List[WorkflowEvaluationSummary],
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_workflow_evaluation_summaries(
    service: TestSuiteService = Injected(TestSuiteService),
):
    """One row per workflow (and the unassigned bucket): count, health, running."""
    return await service.get_workflow_evaluation_summaries()


@router.get(
    "/workflows/{workflow_id}/evaluations",
    response_model=PaginatedEvaluations,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_workflow_evaluations(
    workflow_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    service: TestSuiteService = Injected(TestSuiteService),
):
    """A page of one workflow's evaluations. Use ``unassigned`` for evals with no workflow."""
    if workflow_id == "unassigned":
        resolved: Optional[UUID] = None
    else:
        try:
            resolved = UUID(workflow_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid workflow_id")
    return await service.list_workflow_evaluations(resolved, page, page_size, search)