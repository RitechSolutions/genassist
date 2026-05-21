from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from injector import inject
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.db.models.conversation import ConversationModel
from app.db.models.ml_model_pipeline import MLModelPipelineRun, PipelineRunStatus
from app.db.models.test_suite import TestRunModel
from app.auth.utils import current_user_is_admin
from app.repositories.notification import NotificationRepository
from app.schemas.notification import NotificationItem
from app.services.realtime_notifications import transcript_conversation_notification_url

NotificationTypeFilter = Literal[
    "all",
    "conversation_started",
    "conversation_hostility",
    "conversation_finalized_hostility",
]

@inject
class NotificationFeedService:
    def __init__(
        self,
        db: AsyncSession,
        notification_repository: NotificationRepository,
    ):
        self.db = db
        self._notification_repo = notification_repository

    async def get_feed(
        self,
        *,
        user_id: UUID,
        user_group_id: UUID | None,
        supervised_group_ids: list[UUID],
        limit: int = 50,
        skip: int = 0,
        include_conversation_started: bool = True,
        include_conversation_hostility: bool = True,
        include_conversation_finalized_hostility: bool = True,
        include_workflow_failed: bool = True,
        notification_type: NotificationTypeFilter = "all",
        unread_only: bool = False,
    ) -> tuple[list[NotificationItem], bool]:
        all_items = await self._collect_merged_items(
            user_id=user_id,
            user_group_id=user_group_id,
            supervised_group_ids=supervised_group_ids,
            include_conversation_started=include_conversation_started,
            include_conversation_hostility=include_conversation_hostility,
            include_conversation_finalized_hostility=include_conversation_finalized_hostility,
            include_workflow_failed=include_workflow_failed,
            notification_type=notification_type,
            merge_cap=500 if unread_only else min(max(skip + limit, limit), 500),
        )
        all_items = await self._apply_read_state(user_id=user_id, items=all_items)
        if unread_only:
            all_items = [item for item in all_items if not item.read]
        page = all_items[skip : skip + limit]
        has_more = len(all_items) > skip + limit
        return page, has_more

    async def get_bell_preview(
        self,
        *,
        user_id: UUID,
        user_group_id: UUID | None,
        supervised_group_ids: list[UUID],
        include_conversation_started: bool = True,
        include_conversation_hostility: bool = True,
        include_conversation_finalized_hostility: bool = True,
        include_workflow_failed: bool = True,
    ) -> tuple[list[NotificationItem], int]:
        all_items = await self._collect_merged_items(
            user_id=user_id,
            user_group_id=user_group_id,
            supervised_group_ids=supervised_group_ids,
            include_conversation_started=include_conversation_started,
            include_conversation_hostility=include_conversation_hostility,
            include_conversation_finalized_hostility=include_conversation_finalized_hostility,
            include_workflow_failed=include_workflow_failed,
            notification_type="all",
            merge_cap=500,
        )
        all_items = await self._apply_read_state(user_id=user_id, items=all_items)
        unread_count = sum(1 for item in all_items if not item.read)
        return all_items[:10], unread_count

    async def _collect_merged_items(
        self,
        *,
        user_id: UUID,
        user_group_id: UUID | None,
        supervised_group_ids: list[UUID],
        include_conversation_started: bool,
        include_conversation_hostility: bool,
        include_conversation_finalized_hostility: bool,
        include_workflow_failed: bool,
        notification_type: NotificationTypeFilter,
        merge_cap: int,
    ) -> list[NotificationItem]:
        audience = await self._notification_repo.build_audience_flags_for_user(
            user_id=user_id,
            user_group_id=user_group_id,
            supervised_group_ids=supervised_group_ids,
            bypass_audience_restrictions=current_user_is_admin(),
        )

        include_started = (
            include_conversation_started
            and notification_type in ("all", "conversation_started")
            and audience.get("conversation_started", False)
        )
        include_hostility = (
            include_conversation_hostility
            and notification_type in ("all", "conversation_hostility")
            and audience.get("conversation_hostility", False)
        )
        include_finalized_hostility = (
            notification_type in ("all", "conversation_finalized_hostility")
            and include_conversation_finalized_hostility
            and audience.get("conversation_finalized_hostility", False)
        )
        include_failed = (
            include_workflow_failed
            and notification_type == "all"
            and audience.get("workflow_failed", False)
        )

        started = (
            await self._conversation_started_notifications(limit=merge_cap)
            if include_started
            else []
        )
        hostility = (
            await self._hostility_notifications(limit=merge_cap)
            if include_hostility
            else []
        )
        finalized_hostile = (
            await self._finalized_high_hostility_notifications(limit=merge_cap)
            if include_finalized_hostility
            else []
        )
        workflow_failed = (
            await self._workflow_failed_notifications(limit=merge_cap)
            if include_failed
            else []
        )

        all_items = [*started, *hostility, *finalized_hostile, *workflow_failed]
        all_items.sort(key=lambda item: item.timestamp, reverse=True)
        return all_items

    async def _apply_read_state(
        self, *, user_id: UUID, items: list[NotificationItem]
    ) -> list[NotificationItem]:
        if not items:
            return items
        read_ids = await self._notification_repo.get_read_notification_ids(
            user_id,
            [item.id for item in items],
        )
        return [
            item.model_copy(update={"read": item.id in read_ids}) for item in items
        ]

    async def _conversation_started_notifications(self, limit: int) -> list[NotificationItem]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.created_at >= datetime.now(timezone.utc) - timedelta(days=7))
            .order_by(desc(ConversationModel.created_at))
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        items: list[NotificationItem] = []
        for row in rows:
            items.append(
                NotificationItem(
                    id=f"conversation_started:{row.id}",
                    title="Conversation Started",
                    description=f"A new conversation started (ID: {str(row.id)[:8]}...).",
                    timestamp=row.created_at or row.updated_at or datetime.now(timezone.utc),
                    type="info",
                    action_url=transcript_conversation_notification_url(row.id),
                    group_id=str(row.group_id) if row.group_id else None,
                )
            )
        return items

    async def _hostility_notifications(self, limit: int) -> list[NotificationItem]:
        """Live spike OR recently finalized rows that still qualify (keeps 'High Hostility Detected' after finalize)."""
        recent = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.in_progress_hostility_score >= 50)
            .where(
                or_(
                    ConversationModel.status.in_(
                        (
                            ConversationStatus.IN_PROGRESS.value,
                            ConversationStatus.TAKE_OVER.value,
                        )
                    ),
                    and_(
                        ConversationModel.status == ConversationStatus.FINALIZED.value,
                        ConversationModel.updated_at >= recent,
                    ),
                )
            )
            .order_by(desc(ConversationModel.updated_at))
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        items: list[NotificationItem] = []
        for row in rows:
            score = int(row.in_progress_hostility_score or 0)
            items.append(
                NotificationItem(
                    id=f"conversation_hostility:{row.id}",
                    title="High Hostility Detected",
                    description=f"Conversation {str(row.id)[:8]}... reached hostility score {score}%.",
                    timestamp=row.updated_at or row.created_at or datetime.now(timezone.utc),
                    type="warning",
                    action_url=transcript_conversation_notification_url(row.id),
                    group_id=str(row.group_id) if row.group_id else None,
                )
            )
        return items

    async def _finalized_high_hostility_notifications(self, limit: int) -> list[NotificationItem]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.status == ConversationStatus.FINALIZED.value)
            .where(ConversationModel.in_progress_hostility_score >= 50)
            .where(
                ConversationModel.updated_at
                >= datetime.now(timezone.utc) - timedelta(days=7)
            )
            .order_by(desc(ConversationModel.updated_at))
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        items: list[NotificationItem] = []
        for row in rows:
            score = int(row.in_progress_hostility_score or 0)
            items.append(
                NotificationItem(
                    id=f"conversation_finalized_hostility:{row.id}",
                    title="Live conversation finalized",
                    description=(
                        f"Conversation {str(row.id)[:8]}... finalized with hostility score {score}%."
                    ),
                    timestamp=row.updated_at or row.created_at or datetime.now(timezone.utc),
                    type="warning",
                    action_url=transcript_conversation_notification_url(row.id),
                    group_id=str(row.group_id) if row.group_id else None,
                )
            )
        return items

    async def _workflow_failed_notifications(self, limit: int) -> list[NotificationItem]:
        items: list[NotificationItem] = []

        pipeline_stmt = (
            select(MLModelPipelineRun)
            .where(MLModelPipelineRun.status == PipelineRunStatus.FAILED)
            .order_by(desc(MLModelPipelineRun.updated_at))
            .limit(limit)
        )
        pipeline_rows = (await self.db.execute(pipeline_stmt)).scalars().all()
        for row in pipeline_rows:
            items.append(
                NotificationItem(
                    id=f"workflow_failed:pipeline:{row.id}",
                    title="Workflow Run Failed",
                    description=f"Pipeline run {str(row.id)[:8]}... failed.",
                    timestamp=row.updated_at or row.created_at or datetime.now(timezone.utc),
                    type="error",
                    action_url="/ml-models",
                )
            )

        test_stmt = (
            select(TestRunModel)
            .where(TestRunModel.status == "failed")
            .order_by(desc(TestRunModel.updated_at))
            .limit(limit)
        )
        test_rows = (await self.db.execute(test_stmt)).scalars().all()
        for row in test_rows:
            items.append(
                NotificationItem(
                    id=f"workflow_failed:test:{row.id}",
                    title="Workflow Run Failed",
                    description=f"Test run {str(row.id)[:8]}... failed.",
                    timestamp=row.updated_at or row.created_at or datetime.now(timezone.utc),
                    type="error",
                    action_url="/tests/evaluations",
                )
            )

        return items
