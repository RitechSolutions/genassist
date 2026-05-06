from datetime import datetime, timedelta, timezone
from typing import Literal

from injector import inject
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.db.models.conversation import ConversationModel
from app.db.models.ml_model_pipeline import MLModelPipelineRun, PipelineRunStatus
from app.db.models.test_suite import TestRunModel
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
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_feed(
        self,
        *,
        limit: int = 50,
        skip: int = 0,
        include_conversation_started: bool = True,
        include_conversation_hostility: bool = True,
        include_conversation_finalized_hostility: bool = True,
        include_workflow_failed: bool = True,
        notification_type: NotificationTypeFilter = "all",
    ) -> tuple[list[NotificationItem], bool]:
        fetch_cap = min(max(skip + limit, limit), 500)
        include_started = (
            include_conversation_started
            and notification_type in ("all", "conversation_started")
        )
        include_hostility = (
            include_conversation_hostility
            and notification_type in ("all", "conversation_hostility")
        )
        include_finalized_hostility = notification_type in (
            "all",
            "conversation_finalized_hostility",
        ) and include_conversation_finalized_hostility
        include_failed = include_workflow_failed and notification_type == "all"

        started = (
            await self._conversation_started_notifications(limit=fetch_cap)
            if include_started
            else []
        )
        hostility = (
            await self._hostility_notifications(limit=fetch_cap)
            if include_hostility
            else []
        )
        finalized_hostile = (
            await self._finalized_high_hostility_notifications(limit=fetch_cap)
            if include_finalized_hostility
            else []
        )
        workflow_failed = (
            await self._workflow_failed_notifications(limit=fetch_cap)
            if include_failed
            else []
        )

        all_items = [*started, *hostility, *finalized_hostile, *workflow_failed]
        all_items.sort(key=lambda item: item.timestamp, reverse=True)
        page = all_items[skip : skip + limit]
        has_more = len(all_items) > skip + limit
        return page, has_more

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
                )
            )
        return items

    async def _hostility_notifications(self, limit: int) -> list[NotificationItem]:
        """Live spike OR recently finalized rows that still qualify (keeps 'High Hostility Detected' after finalize)."""
        recent = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.in_progress_hostility_score > 50)
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
