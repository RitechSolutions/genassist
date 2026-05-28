from __future__ import annotations

import asyncio
import logging
from typing import Optional
from uuid import UUID

from injector import inject
from starlette_context import context

from app.auth.utils import current_user_is_admin, has_permission
from app.core.config.azure_devops_defaults import OPEN_LOCAL_STATUSES
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.support_ticket import SupportTicketModel
from app.repositories.support_ticket import SupportTicketRepository
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
from app.services.support_ticket_dedup import compute_fingerprint
from app.services.support_ticket_sync import SupportTicketSyncService

logger = logging.getLogger(__name__)

MAX_TICKETS_PER_USER_PER_DAY = 10


@inject
class SupportTicketService:
    def __init__(
        self,
        repo: SupportTicketRepository,
        sync_service: SupportTicketSyncService,
    ):
        self.repo = repo
        self.sync_service = sync_service

    def _current_user_id(self) -> UUID:
        user_id = context.get("user_id")
        if not user_id:
            raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
        return UUID(str(user_id))

    def _can_manage_all(self, permissions: list[str]) -> bool:
        return (
            current_user_is_admin()
            or has_permission(permissions, "manage:support_ticket")
            or has_permission(permissions, "*")
        )

    def _ensure_ticket_access(
        self, ticket: SupportTicketModel, user_id: UUID, permissions: list[str]
    ) -> None:
        if self._can_manage_all(permissions):
            return
        if ticket.reporter_user_id != user_id:
            raise AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE)

    async def search_duplicates(
        self, query: SupportTicketSearchDuplicatesQuery, permissions: list[str]
    ) -> list[SupportTicketDuplicateCandidate]:
        _ = permissions
        similar = await self.repo.search_similar_titles(query.title, limit=query.limit)
        fingerprint = compute_fingerprint(query.title, query.ticket_type, query.tags)
        by_fp = await self.repo.find_by_fingerprint_open(fingerprint)
        seen: set[UUID] = set()
        results: list[SupportTicketDuplicateCandidate] = []

        for ticket in ([by_fp] if by_fp else []) + similar:
            if not ticket or ticket.id in seen:
                continue
            seen.add(ticket.id)
            results.append(
                SupportTicketDuplicateCandidate(
                    id=ticket.id,
                    title=ticket.title,
                    status=ticket.status,
                    vote_count=ticket.vote_count,
                    azure_work_item_id=ticket.azure_work_item_id,
                    azure_url=ticket.azure_url,
                    similarity="fingerprint" if ticket.fingerprint == fingerprint else "title",
                )
            )
        return results[: query.limit]

    async def create_ticket(
        self, data: SupportTicketCreate, permissions: list[str]
    ) -> SupportTicketRead:
        user_id = self._current_user_id()
        fingerprint = compute_fingerprint(data.title, data.ticket_type, data.tags)

        if not data.force_create and not data.duplicate_of_id:
            recent = await self.repo.find_recent_duplicate_by_user(user_id, fingerprint)
            if recent:
                await self.repo.add_comment(
                    recent.id,
                    user_id,
                    "User attempted to submit the same issue again.",
                )
                return SupportTicketRead.model_validate(recent, from_attributes=True)

        canonical: Optional[SupportTicketModel] = None
        if data.duplicate_of_id:
            canonical = await self.repo.get_by_id(data.duplicate_of_id)
            if not canonical:
                raise AppException(status_code=404, error_key=ErrorKey.MISSING_PARAMETER)
            root = canonical
            while root.duplicate_of_id:
                parent = await self.repo.get_by_id(root.duplicate_of_id)
                if not parent:
                    break
                root = parent
            canonical = root
            ticket = SupportTicketModel(
                reporter_user_id=user_id,
                title=data.title,
                description=data.description,
                ticket_type=data.ticket_type,
                status=canonical.status,
                priority=data.priority or canonical.priority,
                tags=data.tags or canonical.tags,
                environment=data.environment,
                duplicate_of_id=canonical.id,
                fingerprint=fingerprint,
                vote_count=0,
                azure_work_item_id=canonical.azure_work_item_id,
                azure_project=canonical.azure_project,
                azure_url=canonical.azure_url,
            )
            ticket = await self.repo.create(ticket)
            await self.repo.increment_vote(canonical.id)
            await self.repo.add_event(
                canonical.id,
                "duplicate_linked",
                payload={"duplicate_ticket_id": str(ticket.id)},
                actor_user_id=user_id,
            )
            return SupportTicketRead.model_validate(ticket, from_attributes=True)

        if not data.force_create:
            existing_fp = await self.repo.find_by_fingerprint_open(fingerprint)
            if existing_fp:
                await self.repo.increment_vote(existing_fp.id)
                await self.repo.add_comment(
                    existing_fp.id,
                    user_id,
                    f"Additional report (same fingerprint): {data.title}",
                )
                return SupportTicketRead.model_validate(existing_fp, from_attributes=True)

        ticket = SupportTicketModel(
            reporter_user_id=user_id,
            title=data.title.strip(),
            description=data.description,
            ticket_type=data.ticket_type,
            status="sync_pending",
            priority=data.priority,
            tags=data.tags or [],
            environment=data.environment,
            fingerprint=fingerprint,
            vote_count=1,
        )
        ticket = await self.repo.create(ticket)
        await self.repo.add_event(ticket.id, "created", actor_user_id=user_id)

        await self.repo.enqueue_outbox(
            ticket.id,
            "create_work_item",
            payload={},
        )
        asyncio.create_task(self._process_outbox_async(ticket.id))

        return SupportTicketRead.model_validate(ticket, from_attributes=True)

    async def _process_outbox_async(self, ticket_id: UUID) -> None:
        try:
            entries = await self.repo.get_pending_outbox(limit=5)
            for entry in entries:
                if entry.ticket_id == ticket_id:
                    await self.sync_service.process_outbox_entry(entry)
        except Exception:
            logger.exception("Background support ticket sync failed for %s", ticket_id)

    async def list_tickets(
        self,
        permissions: list[str],
        *,
        status: Optional[str] = None,
        ticket_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        mine_only: bool = False,
    ) -> SupportTicketListResponse:
        user_id = self._current_user_id()
        include_all = self._can_manage_all(permissions) and not mine_only
        items, total = await self.repo.list_tickets(
            reporter_user_id=user_id,
            include_all=include_all,
            status=status,
            ticket_type=ticket_type,
            skip=skip,
            limit=limit,
        )
        return SupportTicketListResponse(
            items=[SupportTicketRead.model_validate(t, from_attributes=True) for t in items],
            total=total,
        )

    async def get_ticket(
        self, ticket_id: UUID, permissions: list[str]
    ) -> SupportTicketRead:
        ticket = await self.repo.get_by_id(ticket_id)
        if not ticket:
            raise AppException(status_code=404, error_key=ErrorKey.MISSING_PARAMETER)
        self._ensure_ticket_access(ticket, self._current_user_id(), permissions)
        return SupportTicketRead.model_validate(ticket, from_attributes=True)

    async def link_duplicate(
        self,
        ticket_id: UUID,
        body: SupportTicketLinkDuplicate,
        permissions: list[str],
    ) -> SupportTicketRead:
        if not self._can_manage_all(permissions):
            raise AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE)

        ticket = await self.repo.get_by_id(ticket_id)
        if not ticket:
            raise AppException(status_code=404, error_key=ErrorKey.MISSING_PARAMETER)

        canonical = await self.repo.get_by_id(body.duplicate_of_id)
        if not canonical:
            raise AppException(status_code=404, error_key=ErrorKey.MISSING_PARAMETER)

        ticket.duplicate_of_id = canonical.id
        ticket.azure_work_item_id = canonical.azure_work_item_id
        ticket.azure_url = canonical.azure_url
        ticket.azure_project = canonical.azure_project
        ticket.status = canonical.status
        await self.repo.increment_vote(canonical.id)
        await self.repo.add_event(
            ticket.id,
            "admin_linked_duplicate",
            payload={"canonical_id": str(canonical.id)},
            actor_user_id=self._current_user_id(),
        )
        return SupportTicketRead.model_validate(
            await self.repo.save(ticket), from_attributes=True
        )

    async def add_comment(
        self,
        ticket_id: UUID,
        data: SupportTicketCommentCreate,
        permissions: list[str],
    ) -> SupportTicketCommentRead:
        ticket = await self.repo.get_by_id(ticket_id)
        if not ticket:
            raise AppException(status_code=404, error_key=ErrorKey.MISSING_PARAMETER)
        user_id = self._current_user_id()
        self._ensure_ticket_access(ticket, user_id, permissions)

        root = ticket
        if ticket.duplicate_of_id:
            parent = await self.repo.get_by_id(ticket.duplicate_of_id)
            if parent:
                root = parent

        comment = await self.repo.add_comment(ticket_id, user_id, data.body)
        if root.azure_work_item_id:
            await self.repo.enqueue_outbox(
                root.id,
                "add_comment",
                payload={"text": data.body},
            )
            asyncio.create_task(self._process_outbox_async(root.id))
        return SupportTicketCommentRead.model_validate(comment, from_attributes=True)

    async def list_comments(
        self, ticket_id: UUID, permissions: list[str]
    ) -> list[SupportTicketCommentRead]:
        ticket = await self.repo.get_by_id(ticket_id)
        if not ticket:
            raise AppException(status_code=404, error_key=ErrorKey.MISSING_PARAMETER)
        self._ensure_ticket_access(ticket, self._current_user_id(), permissions)
        comments = await self.repo.list_comments(ticket_id)
        return [
            SupportTicketCommentRead.model_validate(c, from_attributes=True) for c in comments
        ]

    async def list_triage(
        self, permissions: list[str], *, skip: int = 0, limit: int = 50
    ) -> SupportTicketListResponse:
        if not self._can_manage_all(permissions):
            raise AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE)
        items, total = await self.repo.list_tickets(
            include_all=True,
            skip=skip,
            limit=limit,
        )
        open_items = [
            t
            for t in items
            if t.status in OPEN_LOCAL_STATUSES and t.duplicate_of_id is None
        ]
        return SupportTicketListResponse(
            items=[SupportTicketRead.model_validate(t, from_attributes=True) for t in open_items],
            total=total,
        )
