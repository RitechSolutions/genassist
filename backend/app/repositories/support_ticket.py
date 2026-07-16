from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config.azure_devops_defaults import CLOSED_STATE_KEYWORDS
from app.db.models.support_ticket import (
    SupportTicketCommentModel,
    SupportTicketEventModel,
    SupportTicketModel,
    TicketSyncOutboxModel,
)
from app.db.models.user import UserModel
from app.repositories.db_repository import DbRepository
from app.services.support_ticket_dedup import normalize_title


@inject
class SupportTicketRepository(DbRepository[SupportTicketModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(SupportTicketModel, db)

    async def get_user_email(self, user_id: UUID) -> Optional[str]:
        result = await self.db.execute(
            select(UserModel.email).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, ticket_id: UUID) -> Optional[SupportTicketModel]:
        result = await self.db.execute(
            select(SupportTicketModel)
            .options(joinedload(SupportTicketModel.duplicate_of))
            .where(
                SupportTicketModel.id == ticket_id,
                SupportTicketModel.is_deleted == 0,
            )
        )
        return result.scalars().first()

    async def list_tickets(
        self,
        *,
        reporter_user_id: Optional[UUID] = None,
        include_all: bool = False,
        status: Optional[str] = None,
        ticket_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[SupportTicketModel], int]:
        query = select(SupportTicketModel).where(SupportTicketModel.is_deleted == 0)
        count_query = select(func.count()).select_from(SupportTicketModel).where(
            SupportTicketModel.is_deleted == 0
        )

        if not include_all and reporter_user_id:
            query = query.where(SupportTicketModel.reporter_user_id == reporter_user_id)
            count_query = count_query.where(
                SupportTicketModel.reporter_user_id == reporter_user_id
            )
        if status:
            query = query.where(SupportTicketModel.status == status)
            count_query = count_query.where(SupportTicketModel.status == status)
        if ticket_type:
            query = query.where(SupportTicketModel.ticket_type == ticket_type)
            count_query = count_query.where(SupportTicketModel.ticket_type == ticket_type)

        query = query.order_by(SupportTicketModel.created_at.desc()).offset(skip).limit(limit)

        items = (await self.db.execute(query)).scalars().all()
        total = (await self.db.execute(count_query)).scalar_one()
        return list(items), int(total)

    async def find_by_fingerprint_open(
        self, fingerprint: str
    ) -> Optional[SupportTicketModel]:
        result = await self.db.execute(
            select(SupportTicketModel)
            .where(
                SupportTicketModel.fingerprint == fingerprint,
                SupportTicketModel.is_deleted == 0,
                SupportTicketModel.duplicate_of_id.is_(None),
                func.lower(SupportTicketModel.status).notin_(CLOSED_STATE_KEYWORDS),
            )
            .order_by(SupportTicketModel.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def find_recent_duplicate_by_user(
        self, reporter_user_id: UUID, fingerprint: str, hours: int = 24
    ) -> Optional[SupportTicketModel]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await self.db.execute(
            select(SupportTicketModel)
            .where(
                SupportTicketModel.reporter_user_id == reporter_user_id,
                SupportTicketModel.fingerprint == fingerprint,
                SupportTicketModel.is_deleted == 0,
                SupportTicketModel.created_at >= since,
            )
            .order_by(SupportTicketModel.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def search_similar_titles(
        self, title: str, *, limit: int = 5
    ) -> list[SupportTicketModel]:
        normalized = normalize_title(title)
        if len(normalized) < 3:
            return []
        pattern = f"%{normalized[:80]}%"
        result = await self.db.execute(
            select(SupportTicketModel)
            .where(
                SupportTicketModel.is_deleted == 0,
                SupportTicketModel.duplicate_of_id.is_(None),
                func.lower(SupportTicketModel.status).notin_(CLOSED_STATE_KEYWORDS),
                func.lower(SupportTicketModel.title).like(pattern),
            )
            .order_by(SupportTicketModel.vote_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_by_azure_work_item_id(
        self, work_item_id: int
    ) -> Optional[SupportTicketModel]:
        result = await self.db.execute(
            select(SupportTicketModel).where(
                SupportTicketModel.azure_work_item_id == work_item_id,
                SupportTicketModel.is_deleted == 0,
            )
        )
        return result.scalars().first()

    async def save(self, ticket: SupportTicketModel) -> SupportTicketModel:
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket

    async def add_event(
        self,
        ticket_id: UUID,
        event_type: str,
        *,
        payload: Optional[dict] = None,
        actor_user_id: Optional[UUID] = None,
    ) -> SupportTicketEventModel:
        event = SupportTicketEventModel(
            ticket_id=ticket_id,
            event_type=event_type,
            payload=payload,
            actor_user_id=actor_user_id,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def add_comment(
        self, ticket_id: UUID, author_user_id: UUID, body: str
    ) -> SupportTicketCommentModel:
        comment = SupportTicketCommentModel(
            ticket_id=ticket_id,
            author_user_id=author_user_id,
            body=body,
        )
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def list_comments(self, ticket_id: UUID) -> list[SupportTicketCommentModel]:
        result = await self.db.execute(
            select(SupportTicketCommentModel)
            .where(
                SupportTicketCommentModel.ticket_id == ticket_id,
                SupportTicketCommentModel.is_deleted == 0,
            )
            .order_by(SupportTicketCommentModel.created_at.asc())
        )
        return list(result.scalars().all())

    async def enqueue_outbox(
        self,
        ticket_id: UUID,
        operation: str,
        payload: Optional[dict] = None,
    ) -> TicketSyncOutboxModel:
        existing = await self.db.execute(
            select(TicketSyncOutboxModel).where(
                TicketSyncOutboxModel.ticket_id == ticket_id,
                TicketSyncOutboxModel.operation == operation,
                TicketSyncOutboxModel.is_deleted == 0,
            )
        )
        row = existing.scalars().first()
        if row and row.status in ("pending", "failed"):
            row.payload = payload
            row.status = "pending"
            row.last_error = None
            await self.db.commit()
            await self.db.refresh(row)
            return row

        outbox = TicketSyncOutboxModel(
            ticket_id=ticket_id,
            operation=operation,
            payload=payload,
            status="pending",
        )
        self.db.add(outbox)
        await self.db.commit()
        await self.db.refresh(outbox)
        return outbox

    async def get_pending_outbox_for_ticket(
        self, ticket_id: UUID, limit: int = 5
    ) -> list[TicketSyncOutboxModel]:
        result = await self.db.execute(
            select(TicketSyncOutboxModel)
            .where(
                TicketSyncOutboxModel.ticket_id == ticket_id,
                TicketSyncOutboxModel.is_deleted == 0,
                TicketSyncOutboxModel.status.in_(("pending", "failed")),
                TicketSyncOutboxModel.attempts < 5,
            )
            .order_by(TicketSyncOutboxModel.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_outbox(self, limit: int = 20) -> list[TicketSyncOutboxModel]:
        result = await self.db.execute(
            select(TicketSyncOutboxModel)
            .where(
                TicketSyncOutboxModel.is_deleted == 0,
                TicketSyncOutboxModel.status.in_(("pending", "failed")),
                TicketSyncOutboxModel.attempts < 5,
            )
            .order_by(TicketSyncOutboxModel.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def increment_vote(self, ticket_id: UUID) -> Optional[SupportTicketModel]:
        ticket = await self.get_by_id(ticket_id)
        if not ticket:
            return None
        ticket.vote_count = (ticket.vote_count or 1) + 1
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket
