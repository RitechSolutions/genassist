import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
from app.schemas.workflow_schedule import (
    WorkflowScheduleCreate,
    WorkflowScheduleRead,
    WorkflowScheduleRunRead,
    WorkflowScheduleUpdate,
)
from app.services.workflow_schedule import WorkflowScheduleService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=List[WorkflowScheduleRead],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_workflow_schedules(
    is_active: Optional[bool] = Query(None, description="Filter by active state"),
    service: WorkflowScheduleService = Injected(WorkflowScheduleService),
):
    """List all workflow schedules."""
    return await service.list(is_active=is_active)


@router.post(
    "",
    response_model=WorkflowScheduleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.CREATE))],
)
async def create_workflow_schedule(
    data: WorkflowScheduleCreate,
    service: WorkflowScheduleService = Injected(WorkflowScheduleService),
):
    """Create a new workflow schedule."""
    try:
        return await service.create(data)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        if e.error_key == ErrorKey.INTERNAL_ERROR and "cron" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{schedule_id}",
    response_model=WorkflowScheduleRead,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_workflow_schedule(
    schedule_id: UUID,
    service: WorkflowScheduleService = Injected(WorkflowScheduleService),
):
    """Get a single workflow schedule."""
    try:
        return await service.get_by_id(schedule_id)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{schedule_id}",
    response_model=WorkflowScheduleRead,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def update_workflow_schedule(
    schedule_id: UUID,
    data: WorkflowScheduleUpdate,
    service: WorkflowScheduleService = Injected(WorkflowScheduleService),
):
    """Update a workflow schedule."""
    try:
        return await service.update(schedule_id, data)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        if e.error_key == ErrorKey.INTERNAL_ERROR and "cron" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.DELETE))],
)
async def delete_workflow_schedule(
    schedule_id: UUID,
    service: WorkflowScheduleService = Injected(WorkflowScheduleService),
):
    """Delete (soft) a workflow schedule."""
    try:
        await service.delete(schedule_id)
        return None
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{schedule_id}/runs",
    response_model=List[WorkflowScheduleRunRead],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_workflow_schedule_runs(
    schedule_id: UUID,
    run_status: Optional[WorkflowScheduleRunStatus] = Query(
        None, description="Filter by run status"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: WorkflowScheduleService = Injected(WorkflowScheduleService),
):
    """List run history for a workflow schedule."""
    try:
        return await service.get_runs(
            schedule_id, status=run_status, limit=limit, offset=offset
        )
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{schedule_id}/run-now",
    response_model=WorkflowScheduleRunRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.EXECUTE))],
)
async def run_workflow_schedule_now(
    schedule_id: UUID,
    request: Request,
    service: WorkflowScheduleService = Injected(WorkflowScheduleService),
):
    """Trigger an immediate run of a workflow schedule."""
    try:
        run = await service.create_manual_run(schedule_id)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # Dispatch the execution task (mirrors ML pipeline run-now behaviour).
    try:
        celery_app = request.app.celery_app
        result = celery_app.send_task("execute_workflow_run", args=[str(run.id)])
        logger.info(f"Queued workflow schedule run: {run.id}, task_id: {result.id}")
    except Exception as task_error:
        logger.error(
            f"Error queueing workflow schedule run task: {str(task_error)}",
            exc_info=True,
        )
        try:
            from app.tasks.workflow_schedule_tasks import execute_workflow_run_task

            execute_workflow_run_task.delay(str(run.id))
            logger.info(f"Queued workflow schedule run (fallback): {run.id}")
        except Exception as fallback_error:
            logger.error(
                f"Error in fallback task queueing: {str(fallback_error)}",
                exc_info=True,
            )

    return run