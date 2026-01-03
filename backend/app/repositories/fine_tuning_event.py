from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from injector import inject

from app.db.models.fine_tuning import FineTuningEventModel
from app.repositories.db_repository import DbRepository


@inject
class FineTuningEventRepository(DbRepository[FineTuningEventModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(FineTuningEventModel, db)


    async def get_events_by_job_id(
            self,
            job_id: UUID,
            limit: Optional[int] = None,
            order_desc: bool = True
            ) -> List[FineTuningEventModel]:
        """
        Get all events for a specific job.

        Args:
            job_id: Job UUID
            limit: Maximum number of events to return
            order_desc: If True, newest first. If False, oldest first.

        Returns:
            List of event records
        """
        query = select(FineTuningEventModel).where(
                FineTuningEventModel.job_id == job_id
                )

        if order_desc:
            query = query.order_by(desc(FineTuningEventModel.event_created_at))
        else:
            query = query.order_by(FineTuningEventModel.event_created_at)

        if limit:
            query = query.limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def get_latest_event_by_job_id(
            self,
            job_id: UUID
            ) -> Optional[FineTuningEventModel]:
        """
        Get the most recent event for a job.

        Args:
            job_id: Job UUID

        Returns:
            Latest event or None
        """
        query = (
            select(FineTuningEventModel)
            .where(FineTuningEventModel.job_id == job_id)
            .order_by(desc(FineTuningEventModel.event_created_at))
            .limit(1)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()


    async def event_exists(self, openai_event_id: str) -> bool:
        """
        Check if an event already exists by OpenAI event ID.

        Args:
            openai_event_id: OpenAI's event ID

        Returns:
            True if exists, False otherwise
        """
        query = select(FineTuningEventModel.id).where(
                FineTuningEventModel.openai_event_id == openai_event_id
                )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None


    async def bulk_create_events(
            self,
            events: List[FineTuningEventModel]
            ) -> List[FineTuningEventModel]:
        """
        Bulk create multiple events.

        Args:
            events: List of event models to create

        Returns:
            List of created events
        """
        self.db.add_all(events)
        await self.db.commit()

        for event in events:
            await self.db.refresh(event)

        return events


    async def get_events_with_metrics_by_job_id(
            self,
            job_id: UUID
            ) -> List[FineTuningEventModel]:
        """
        Get all events that have metrics for a specific job.

        Args:
            job_id: Job UUID

        Returns:
            List of events with metrics
        """
        query = (
            select(FineTuningEventModel)
            .where(
                    and_(
                            FineTuningEventModel.job_id == job_id,
                            FineTuningEventModel.metrics.isnot(None)
                            )
                    )
            .order_by(FineTuningEventModel.event_created_at)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())