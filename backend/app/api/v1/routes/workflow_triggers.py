"""Management API for Webhook Trigger node endpoints.

The public delivery endpoint itself is ``/webhook/execute/{id}`` (see
``webhook_execute.py``); everything here is authenticated builder tooling.
"""

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
from app.schemas.workflow_trigger import (
    WorkflowTriggerDeliveryResponse,
    WorkflowTriggerProvision,
    WorkflowTriggerProvisionResponse,
    WorkflowTriggerRead,
    WorkflowTriggerRunRead,
    WorkflowTriggerRunSummary,
    WorkflowTriggerSecret,
    WorkflowTriggerTestRequest,
    WorkflowTriggerUpdate,
)
from app.services.workflow_trigger import WorkflowTriggerService

logger = logging.getLogger(__name__)

router = APIRouter()


def _http(e: AppException) -> HTTPException:
    if e.error_key == ErrorKey.NOT_FOUND:
        return HTTPException(status_code=404, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


@router.post(
    "/provision",
    response_model=WorkflowTriggerProvisionResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def provision_workflow_trigger(
    data: WorkflowTriggerProvision,
    request: Request,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    """Create the endpoint for a trigger node, or return the existing one."""
    try:
        return await service.provision(data, request)
    except AppException as e:
        raise _http(e)


@router.get(
    "/by-agent/{agent_id}",
    response_model=List[WorkflowTriggerRead],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_workflow_triggers_by_agent(
    agent_id: UUID,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    return await service.list_by_agent(agent_id)


@router.get(
    "/{trigger_id}",
    response_model=WorkflowTriggerRead,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_workflow_trigger(
    trigger_id: UUID,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    try:
        return await service.get(trigger_id)
    except AppException as e:
        raise _http(e)


@router.put(
    "/{trigger_id}",
    response_model=WorkflowTriggerRead,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def update_workflow_trigger(
    trigger_id: UUID,
    data: WorkflowTriggerUpdate,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    try:
        return await service.update(trigger_id, data)
    except AppException as e:
        raise _http(e)


@router.delete(
    "/{trigger_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.DELETE))],
)
async def delete_workflow_trigger(
    trigger_id: UUID,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    try:
        await service.delete(trigger_id)
        return None
    except AppException as e:
        raise _http(e)


@router.post(
    "/{trigger_id}/rotate-secret",
    response_model=WorkflowTriggerSecret,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def rotate_workflow_trigger_secret(
    trigger_id: UUID,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    try:
        return await service.rotate_secret(trigger_id)
    except AppException as e:
        raise _http(e)


@router.get(
    "/{trigger_id}/reveal-secret",
    response_model=WorkflowTriggerSecret,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def reveal_workflow_trigger_secret(
    trigger_id: UUID,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    try:
        return await service.reveal_secret(trigger_id)
    except AppException as e:
        raise _http(e)


@router.get(
    "/{trigger_id}/runs",
    response_model=List[WorkflowTriggerRunSummary],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_workflow_trigger_runs(
    trigger_id: UUID,
    run_status: Optional[WorkflowScheduleRunStatus] = Query(None, description="Filter by run status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    try:
        return await service.list_runs(trigger_id, status=run_status, limit=limit, offset=offset)
    except AppException as e:
        raise _http(e)


@router.get(
    "/{trigger_id}/runs/{run_id}",
    response_model=WorkflowTriggerRunRead,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_workflow_trigger_run(
    trigger_id: UUID,
    run_id: UUID,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    try:
        return await service.get_run(trigger_id, run_id)
    except AppException as e:
        raise _http(e)


@router.post(
    "/{trigger_id}/test",
    response_model=WorkflowTriggerDeliveryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.EXECUTE))],
)
async def test_workflow_trigger(
    trigger_id: UUID,
    data: WorkflowTriggerTestRequest,
    request: Request,
    service: WorkflowTriggerService = Injected(WorkflowTriggerService),
):
    """Queue a run with a sample delivery, skipping auth and rate limiting."""
    try:
        return await service.test(trigger_id, data, request)
    except AppException as e:
        raise _http(e)
