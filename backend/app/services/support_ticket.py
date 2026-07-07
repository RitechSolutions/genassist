from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from injector import inject
from starlette_context import context

from app.auth.utils import current_user_is_admin, has_permission
from app.core.tenant_scope import get_tenant_context
from app.core.config.help_center_ado import get_help_center_public_base_url, get_help_center_ado_connector
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.support_ticket import SupportTicketModel
from app.repositories.support_ticket import SupportTicketRepository
from app.schemas.support_ticket import (
    SupportTicketCommentCreate,
    SupportTicketCommentRead,
    SupportTicketCreate,
    SupportTicketDuplicateCandidate,
    SupportTicketListResponse,
    SupportTicketRead,
    SupportTicketSearchDuplicatesQuery,
)
from app.services.html_sanitizer import sanitize_html
from app.services.support_ticket_dedup import compute_fingerprint
from app.services.support_ticket_sync import SupportTicketSyncService

logger = logging.getLogger(__name__)

MAX_TICKETS_PER_USER_PER_DAY = 10


def _merge_help_center_tags(tags: list[str] | None, ticket_type: str) -> list[str]:
    merged = list(tags or [])
    for tag in ("genassist", f"help-center-{ticket_type}"):
        if tag not in merged:
            merged.append(tag)
    return merged


@inject
class SupportTicketService:
    def __init__(
        self,
        repo: SupportTicketRepository,
        sync_service: SupportTicketSyncService,
    ):
        self.repo = repo
        self.sync_service = sync_service

    async def _build_environment(
        self, user_id: UUID, base: Optional[dict] = None
    ) -> Optional[dict]:
        """Merge reporter identity (email, tenant) into the environment payload."""
        environment = dict(base or {})
        email = await self.repo.get_user_email(user_id)
        if email:
            environment["reporter_email"] = email
        tenant = get_tenant_context()
        if tenant and tenant != "master":
            environment["tenant"] = tenant
        return environment or None

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

        # Rich-text fields are stored as sanitized HTML.
        description = sanitize_html(data.description)
        repro_steps = sanitize_html(data.repro_steps) or None
        system_info = sanitize_html(data.system_info) or None
        acceptance_criteria = sanitize_html(data.acceptance_criteria) or None

        # Capture reporter identity now (tenant is request-scoped and unavailable
        # during background sync) so it can be surfaced on the Azure work item.
        environment = await self._build_environment(user_id, data.environment)

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
                description=description,
                repro_steps=repro_steps,
                system_info=system_info,
                acceptance_criteria=acceptance_criteria,
                ticket_type=data.ticket_type,
                status=canonical.status,
                priority=data.priority or canonical.priority,
                tags=data.tags or canonical.tags,
                environment=environment,
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
            description=description,
            repro_steps=repro_steps,
            system_info=system_info,
            acceptance_criteria=acceptance_criteria,
            ticket_type=data.ticket_type,
            status="sync_pending",
            priority=data.priority,
            tags=_merge_help_center_tags(data.tags, data.ticket_type),
            environment=environment,
            fingerprint=fingerprint,
            vote_count=1,
        )
        ticket = await self.repo.create(ticket)
        await self.repo.add_event(ticket.id, "created", actor_user_id=user_id)

        await self.repo.enqueue_outbox(
            ticket.id,
            "create_work_item",
            payload={"app_base_url": get_help_center_public_base_url()},
        )
        await self._process_outbox_for_ticket(ticket.id)

        refreshed = await self.repo.get_by_id(ticket.id)
        if refreshed:
            ticket = refreshed

        return SupportTicketRead.model_validate(ticket, from_attributes=True)

    async def _process_outbox_for_ticket(self, ticket_id: UUID) -> None:
        try:
            entries = await self.repo.get_pending_outbox_for_ticket(ticket_id)
            for entry in entries:
                await self.sync_service.process_outbox_entry(entry)
        except Exception:
            logger.exception("Support ticket ADO sync failed for %s", ticket_id)

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
        ticket = await self.sync_service.refresh_status(ticket)
        return SupportTicketRead.model_validate(ticket, from_attributes=True)

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
            try:
                connector = get_help_center_ado_connector()
                await connector.add_comment(root.azure_work_item_id, data.body)
            except Exception:
                logger.exception(
                    "Failed to sync comment to Azure DevOps for ticket %s", root.id
                )
                await self.repo.enqueue_outbox(
                    root.id,
                    "add_comment",
                    payload={"text": data.body},
                )
                await self._process_outbox_for_ticket(root.id)
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
