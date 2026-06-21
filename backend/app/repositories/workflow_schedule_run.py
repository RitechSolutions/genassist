import logging
from uuid import UUID
from typing import List, Optional, Sequence
from datetime import datetime, timezone

from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
from app.db.models.workflow_schedule import WorkflowScheduleRunModel
from app.repositories.db_repository import DbRepository

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {
    WorkflowScheduleRunStatus.COMPLETED,
    WorkflowScheduleRunStatus.FAILED,
    WorkflowScheduleRunStatus.CANCELLED,
}


@inject
class WorkflowScheduleRunRepository(DbRepository[WorkflowScheduleRunModel]):
    """Repository for workflow schedule runs. Extends the generic DbRepository,
    overriding reads to honour soft-delete and raise NOT_FOUND."""

    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowScheduleRunModel, db)

    async def create(
        self,
        schedule_id: UUID,
        agent_id: UUID,
        workflow_id: Optional[UUID] = None,
        thread_id: Optional[str] = None,
    ) -> WorkflowScheduleRunModel:
        run = WorkflowScheduleRunModel(
            schedule_id=schedule_id,
            agent_id=agent_id,
            workflow_id=workflow_id,
            thread_id=thread_id,
            status=WorkflowScheduleRunStatus.PENDING,
        )
        return await super().create(run)

    async def get_by_id(
        self, run_id: UUID, *, eager: Sequence[str] | None = None
    ) -> WorkflowScheduleRunModel:
        run = await super().get_by_id(run_id, eager=eager)
        if not run or run.is_deleted:
            raise AppException(error_key=ErrorKey.NOT_FOUND)
        return run

    async def list_by_schedule(
        self,
        schedule_id: UUID,
        status: Optional[WorkflowScheduleRunStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowScheduleRunModel]:
        query = select(WorkflowScheduleRunModel).where(
            WorkflowScheduleRunModel.schedule_id == schedule_id,
            WorkflowScheduleRunModel.is_deleted == 0,
        )
        if status:
            query = query.where(WorkflowScheduleRunModel.status == status)
        query = (
            query.order_by(WorkflowScheduleRunModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_last_run(
        self, schedule_id: UUID
    ) -> Optional[WorkflowScheduleRunModel]:
        query = (
            select(WorkflowScheduleRunModel)
            .where(
                WorkflowScheduleRunModel.schedule_id == schedule_id,
                WorkflowScheduleRunModel.is_deleted == 0,
            )
            .order_by(WorkflowScheduleRunModel.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def update_status(
        self,
        run_id: UUID,
        status: WorkflowScheduleRunStatus,
        error_message: Optional[str] = None,
        execution_output: Optional[dict] = None,
        execution_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        thread_id: Optional[str] = None,
    ) -> WorkflowScheduleRunModel:
        run = await self.get_by_id(run_id)

        run.status = status

        if status == WorkflowScheduleRunStatus.RUNNING and not run.started_at:
            run.started_at = datetime.now(timezone.utc)

        if status in _TERMINAL_STATUSES and not run.completed_at:
            run.completed_at = datetime.now(timezone.utc)

        if error_message is not None:
            run.error_message = error_message
        if execution_output is not None:
            run.execution_output = execution_output
        if execution_id is not None:
            run.execution_id = execution_id
        if workflow_id is not None:
            run.workflow_id = workflow_id
        if thread_id is not None:
            run.thread_id = thread_id

        try:
            run.updated_by = context.get("user_id")
        except (LookupError, ContextDoesNotExistError):
            pass

        return await super().update(run)