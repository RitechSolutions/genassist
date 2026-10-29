from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.issue_status import IssueStatusCreate, IssueStatusEdit, IssueStatusOrder, IssueStatusRead
from app.services.issue_status import IssueStatusService

router = APIRouter()


@router.get(
    "",
    response_model=list[IssueStatusRead],
    dependencies=[Depends(auth), Depends(permissions(P.Conversation.READ))],
)
async def list_issue_statuses(svc: IssueStatusService = Injected(IssueStatusService)):
    return await svc.list_statuses()


@router.post(
    "",
    response_model=IssueStatusRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.CREATE))],
)
async def create_issue_status(dto: IssueStatusCreate, svc: IssueStatusService = Injected(IssueStatusService)):
    return await svc.create(dto)


@router.put(
    "/order",
    response_model=list[IssueStatusRead],
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.UPDATE))],
)
async def reorder_issue_statuses(dto: IssueStatusOrder, svc: IssueStatusService = Injected(IssueStatusService)):
    return await svc.reorder(dto)


@router.patch(
    "/{status_id}",
    response_model=IssueStatusRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.UPDATE))],
)
async def update_issue_status(
    status_id: UUID, dto: IssueStatusEdit, svc: IssueStatusService = Injected(IssueStatusService)
):
    return await svc.update(status_id, dto)
