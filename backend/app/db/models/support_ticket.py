from __future__ import annotations

import enum
from typing import Optional
from uuid import UUID

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SupportTicketType(str, enum.Enum):
    BUG = "bug"
    FEATURE = "feature"
    TASK = "task"


class SupportTicketStatus(str, enum.Enum):
    NEW = "new"
    SYNC_PENDING = "sync_pending"
    OPEN = "open"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class TicketSyncOutboxStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TicketSyncOperation(str, enum.Enum):
    CREATE_WORK_ITEM = "create_work_item"
    ADD_COMMENT = "add_comment"
    UPDATE_TAGS = "update_tags"


class SupportTicketModel(Base):
    __tablename__ = "support_tickets"

    reporter_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Rich-text (HTML) fields shown per ticket type, mirroring the Azure DevOps
    # work item form: Bug -> repro_steps/system_info/acceptance_criteria,
    # Feature -> description/acceptance_criteria, Task -> description.
    repro_steps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ticket_type: Mapped[str] = mapped_column(String(32), nullable=False, default="bug")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="sync_pending")
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    environment: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    azure_work_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    azure_project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    azure_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    app_settings_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_settings.id"), nullable=True
    )

    duplicate_of_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("support_tickets.id"), nullable=True, index=True
    )
    fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    vote_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    duplicate_of: Mapped[Optional["SupportTicketModel"]] = relationship(
        "SupportTicketModel", remote_side="SupportTicketModel.id", foreign_keys=[duplicate_of_id]
    )
    comments: Mapped[list["SupportTicketCommentModel"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    events: Mapped[list["SupportTicketEventModel"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class SupportTicketCommentModel(Base):
    __tablename__ = "support_ticket_comments"

    ticket_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped[SupportTicketModel] = relationship(back_populates="comments")


class SupportTicketEventModel(Base):
    __tablename__ = "support_ticket_events"

    ticket_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    actor_user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    ticket: Mapped[SupportTicketModel] = relationship(back_populates="events")


class TicketSyncOutboxModel(Base):
    __tablename__ = "ticket_sync_outbox"

    ticket_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("ticket_id", "operation", name="uq_ticket_sync_outbox_ticket_op"),
    )
