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
from app.schemas.eval_bundle import (
    EvaluationBundle,
    EvaluationBundleSet,
    EvaluationImportPreview,
    EvaluationImportPreviewRequest,
    EvaluationImportRequest,
    EvaluationImportResult,
    EvaluationSetImportPreview,
    EvaluationSetImportPreviewRequest,
    EvaluationSetImportRequest,
    EvaluationSetImportResult,
)
from app.schemas.test_suite import (
    EvaluationRunRequest,
    EvaluationToolCatalog,
    PaginatedEvaluations,
    RunWorkflowEvaluationsRequest,
    StartedEvaluationRun,
    TestEvaluation,
    TestEvaluationCreate,
    TestEvaluationUpdate,
    TestRun,
    WorkflowEvaluationSummary,
)
from app.services.eval_bundle import EvalBundleService
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
    "/workflows/{workflow_id}/evaluation-tool-catalog",
    response_model=EvaluationToolCatalog,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def get_evaluation_tool_catalog(
    workflow_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """Agents and their tools for a workflow, so the rule builder never needs free text."""
    return await service.get_evaluation_tool_catalog(workflow_id)


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


@router.post(
    "/evaluations/import/preview",
    response_model=EvaluationImportPreview,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def preview_evaluation_import(
    data: EvaluationImportPreviewRequest,
    service: EvalBundleService = Injected(EvalBundleService),
):
    """Resolve a bundle's references against a target workflow without importing."""
    return await service.preview_import(data)


@router.post(
    "/evaluations/import",
    response_model=EvaluationImportResult,
    status_code=status.HTTP_201_CREATED,
    # Evaluation.UPDATE, matching every other evaluation and dataset route.
    # Note: test_cases.py gates case reads/writes behind Workflow.* instead, so
    # a supervisor can own datasets but not their cases — an inconsistency in
    # that router, not something to resolve by locking supervisors out here.
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def import_evaluation(
    data: EvaluationImportRequest,
    service: EvalBundleService = Injected(EvalBundleService),
):
    """Create the bundle's dataset, cases and evaluation against a target workflow."""
    return await service.import_bundle(data)


@router.post(
    "/evaluations/import-set/preview",
    response_model=EvaluationSetImportPreview,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def preview_evaluation_set_import(
    data: EvaluationSetImportPreviewRequest,
    service: EvalBundleService = Injected(EvalBundleService),
):
    """Resolve a bundle set's references against a target workflow without importing."""
    return await service.preview_set_import(data)


@router.post(
    "/evaluations/import-set",
    response_model=EvaluationSetImportResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def import_evaluation_set(
    data: EvaluationSetImportRequest,
    service: EvalBundleService = Injected(EvalBundleService),
):
    """Import the selected evaluations of a bundle set; one result per item."""
    return await service.import_bundle_set(data)


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


@router.get(
    "/evaluations/{evaluation_id}/export",
    response_model=EvaluationBundle,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def export_evaluation(
    evaluation_id: UUID,
    service: EvalBundleService = Injected(EvalBundleService),
):
    """The evaluation, its dataset and reference labels as a portable bundle."""
    return await service.export_evaluation(evaluation_id)


@router.get(
    "/workflows/{workflow_id}/evaluations/export",
    response_model=EvaluationBundleSet,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def export_workflow_evaluations(
    workflow_id: UUID,
    service: EvalBundleService = Injected(EvalBundleService),
):
    """Every evaluation of this workflow as one portable bundle set."""
    return await service.export_workflow_evaluations(workflow_id)


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
    """Refuses with 409 while the evaluation is queued/running — its config must
    not change underneath an executing run."""
    if await service.evaluation_has_active_run(evaluation_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This evaluation is running. Wait for it to finish before editing.",
        )
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


@router.post(
    "/evaluations/{evaluation_id}/run",
    response_model=TestRun,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.RUN))],
)
async def run_evaluation(
    evaluation_id: UUID,
    data: Optional[EvaluationRunRequest] = None,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """Queue one evaluation's run, optionally against another version of its
    workflow. Refuses with 409 while the evaluation is queued/running."""
    if await service.evaluation_has_active_run(evaluation_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This evaluation is already running.",
        )

    tenant = get_tenant_context()

    def dispatch(run, input_metadata, technique_configs):
        execute_test_suite_run_task.delay(
            str(run.id),
            tenant,
            input_metadata,
            technique_configs,
        )

    return await service.start_evaluation_run(
        evaluation_id,
        dispatch,
        data.target_workflow_id if data else None,
    )


@router.delete(
    "/evaluations/{evaluation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def delete_evaluation(
    evaluation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """Refuses with 409 while the evaluation is queued/running — deleting would
    soft-delete a run the worker is still writing to."""
    if await service.evaluation_has_active_run(evaluation_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This evaluation is running. Wait for it to finish before deleting.",
        )
    await service.delete_evaluation(evaluation_id)


@router.post(
    "/workflows/{workflow_id}/evaluations/run",
    response_model=List[StartedEvaluationRun],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.RUN))],
)
async def run_workflow_evaluations(
    workflow_id: UUID,
    data: Optional[RunWorkflowEvaluationsRequest] = None,
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
    # The batch spans every version of the workflow, so the lock must key on the
    # workflow rather than whichever version the URL names — two callers holding
    # different version ids would otherwise both start runs for the same set.
    # A failed lookup falls back to the requested id: a narrower lock is worse
    # than none at all, and must not turn a valid request into a 500.
    try:
        canonical_id = (
            await service.workflow_service.get_active_version_id(workflow_id)
        ) or workflow_id
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Could not resolve the live version of workflow %s for the Run-all "
            "lock; locking on the requested version.",
            workflow_id,
        )
        canonical_id = workflow_id
    lock_key = f"tenant:{get_tenant_context()}:eval-run-all:{canonical_id}"
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

        return await service.start_workflow_evaluations(
            workflow_id,
            dispatch,
            data.target_workflow_id if data else None,
        )
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