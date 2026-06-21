import logging
from uuid import UUID
from typing import List, Optional, Sequence

from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.workflow_schedule import WorkflowScheduleModel
from app.repositories.db_repository import DbRepository
from app.schemas.workflow_schedule import (
    WorkflowScheduleCreate,
    WorkflowScheduleUpdate,
)

logger = logging.getLogger(__name__)


@inject
class WorkflowScheduleRepository(DbRepository[WorkflowScheduleModel]):
    """Repository for workflow schedules. Extends the generic DbRepository,
    overriding reads to honour soft-delete and raise NOT_FOUND."""

    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowScheduleModel, db)

    # create(obj) on the base takes a built ORM object; override to build it
    # from the create schema so callers stay at the schema level.
    async def create(self, data: WorkflowScheduleCreate) -> WorkflowScheduleModel:
        schedule = WorkflowScheduleModel(
            name=data.name,
            agent_id=data.agent_id,
            cron_schedule=data.cron_schedule,
            is_active=data.is_active,
            input_data=data.input_data,
            thread_id_mode=data.thread_id_mode.value,
            fixed_thread_id=data.fixed_thread_id,
        )
        return await super().create(schedule)

    # Base get_by_id returns None for soft-deleted rows (the global soft-delete
    # filter excludes them); we just upgrade the miss to a NOT_FOUND error.
    async def get_by_id(
        self, schedule_id: UUID, *, eager: Sequence[str] | None = None
    ) -> WorkflowScheduleModel:
        schedule = await super().get_by_id(schedule_id, eager=eager)
        if not schedule:
            raise AppException(error_key=ErrorKey.NOT_FOUND)
        return schedule

    async def list(
        self, is_active: Optional[bool] = None
    ) -> List[WorkflowScheduleModel]:
        query = select(WorkflowScheduleModel)
        if is_active is not None:
            query = query.where(WorkflowScheduleModel.is_active == is_active)
        query = query.order_by(WorkflowScheduleModel.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_with_cron(self) -> List[WorkflowScheduleModel]:
        """Schedules eligible for the beat task: active, with a cron."""
        query = select(WorkflowScheduleModel).where(
            WorkflowScheduleModel.is_active.is_(True),
            WorkflowScheduleModel.cron_schedule.isnot(None),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def apply_update(
        self, schedule: WorkflowScheduleModel, data: WorkflowScheduleUpdate
    ) -> WorkflowScheduleModel:
        """Mutate a managed schedule from the update schema and commit via base update()."""
        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if key == "thread_id_mode" and value is not None:
                value = value.value if hasattr(value, "value") else value
            if hasattr(schedule, key):
                setattr(schedule, key, value)

        try:
            schedule.updated_by = context.get("user_id")
        except (LookupError, ContextDoesNotExistError):
            pass

        return await super().update(schedule)