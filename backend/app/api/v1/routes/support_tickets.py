from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services.support_ticket import SupportTicketService
from app.schemas.support_ticket import (
    SupportTicketCommentCreate,
    SupportTicketCommentRead,
    SupportTicketCreate,
    SupportTicketDuplicateCandidate,
    SupportTicketLinkDuplicate,
    SupportTicketListResponse,
    SupportTicketRead,
    SupportTicketSearchDuplicatesQuery,
)

router = APIRouter(tags=["Help Center"], dependencies=[Depends(auth)])


def _permissions_from_request(request: Request) -> list[str]:
    if hasattr(request.state, "api_key") and request.state.api_key:
        return list(getattr(request.state.api_key, "permissions", []) or [])
    user = getattr(request.state, "user", None)
    if user:
        return list(getattr(user, "permissions", []) or [])
    raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)


@router.get(
    "/duplicates",
    response_model=list[SupportTicketDuplicateCandidate],
    dependencies=[Depends(permissions("read:support_ticket"))],
)
async def search_duplicate_candidates(
    request: Request,
    title: str = Query(..., min_length=3),
    ticket_type: str = Query("bug"),
    service: SupportTicketService = Injected(SupportTicketService),
):
    query = SupportTicketSearchDuplicatesQuery(title=title, ticket_type=ticket_type)
    return await service.search_duplicates(query, _permissions_from_request(request))


@router.get(
    "",
    response_model=SupportTicketListResponse,
    dependencies=[Depends(permissions("read:support_ticket"))],
)
async def list_support_tickets(
    request: Request,
    status: str | None = None,
    ticket_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    mine_only: bool = False,
    service: SupportTicketService = Injected(SupportTicketService),
):
    return await service.list_tickets(
        _permissions_from_request(request),
        status=status,
        ticket_type=ticket_type,
        skip=skip,
        limit=limit,
        mine_only=mine_only,
    )


@router.get(
    "/triage",
    response_model=SupportTicketListResponse,
    dependencies=[Depends(permissions("manage:support_ticket"))],
)
async def triage_queue(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: SupportTicketService = Injected(SupportTicketService),
):
    return await service.list_triage(
        _permissions_from_request(request), skip=skip, limit=limit
    )


@router.post(
    "",
    response_model=SupportTicketRead,
    dependencies=[Depends(permissions("create:support_ticket"))],
)
async def create_support_ticket(
    request: Request,
    data: SupportTicketCreate,
    service: SupportTicketService = Injected(SupportTicketService),
):
    return await service.create_ticket(data, _permissions_from_request(request))


@router.get(
    "/{ticket_id}",
    response_model=SupportTicketRead,
    dependencies=[Depends(permissions("read:support_ticket"))],
)
async def get_support_ticket(
    request: Request,
    ticket_id: UUID,
    service: SupportTicketService = Injected(SupportTicketService),
):
    return await service.get_ticket(ticket_id, _permissions_from_request(request))


@router.post(
    "/{ticket_id}/link-duplicate",
    response_model=SupportTicketRead,
    dependencies=[Depends(permissions("manage:support_ticket"))],
)
async def link_support_ticket_duplicate(
    request: Request,
    ticket_id: UUID,
    body: SupportTicketLinkDuplicate,
    service: SupportTicketService = Injected(SupportTicketService),
):
    return await service.link_duplicate(
        ticket_id, body, _permissions_from_request(request)
    )


@router.get(
    "/{ticket_id}/comments",
    response_model=list[SupportTicketCommentRead],
    dependencies=[Depends(permissions("read:support_ticket"))],
)
async def list_ticket_comments(
    request: Request,
    ticket_id: UUID,
    service: SupportTicketService = Injected(SupportTicketService),
):
    return await service.list_comments(ticket_id, _permissions_from_request(request))


@router.post(
    "/{ticket_id}/comments",
    response_model=SupportTicketCommentRead,
    dependencies=[Depends(permissions("create:support_ticket"))],
)
async def add_ticket_comment(
    request: Request,
    ticket_id: UUID,
    data: SupportTicketCommentCreate,
    service: SupportTicketService = Injected(SupportTicketService),
):
    return await service.add_comment(
        ticket_id, data, _permissions_from_request(request)
    )
