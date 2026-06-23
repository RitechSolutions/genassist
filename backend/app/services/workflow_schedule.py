import logging
from uuid import UUID
from typing import List, Optional

from injector import inject
from croniter import croniter, CroniterBadCronError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
from app.repositories.agent import AgentRepository
from app.repositories.workflow_schedule import WorkflowScheduleRepository
from app.repositories.workflow_schedule_run import WorkflowScheduleRunRepository
from app.schemas.workflow_schedule import (
    WorkflowScheduleCreate,
    WorkflowScheduleUpdate,
    WorkflowScheduleRead,
    WorkflowScheduleRunRead,
)

logger = logging.getLogger(__name__)


def validate_cron_expression(cron: Optional[str]) -> bool:
    """Validate a 5-field cron expression. None/empty is treated as invalid here
    because a schedule requires a cron."""
    if cron is None or cron.strip() == "":
        return False
    try:
        return bool(croniter.is_valid(cron.strip()))
    except (CroniterBadCronError, ValueError):
        return False


@inject
class WorkflowScheduleService:
    """Business logic for workflow schedules and their run history."""

    def __init__(
        self,
        schedule_repository: WorkflowScheduleRepository,
        run_repository: WorkflowScheduleRunRepository,
        agent_repository: AgentRepository,
    ):
        self.schedule_repository = schedule_repository
        self.run_repository = run_repository
        self.agent_repository = agent_repository

    async def _validate_agent(self, agent_id: UUID) -> None:
        agent = await self.agent_repository.get_by_id(agent_id)
        if not agent:
            raise AppException(
                error_key=ErrorKey.NOT_FOUND,
                error_detail="Agent not found",
            )

    async def _to_read(self, schedule) -> WorkflowScheduleRead:
        read = WorkflowScheduleRead.model_validate(schedule)
        last_run = await self.run_repository.get_last_run(schedule.id)
        if last_run:
            read.last_run_status = last_run.status
        return read

    async def create(self, data: WorkflowScheduleCreate) -> WorkflowScheduleRead:
        await self._validate_agent(data.agent_id)

        if not validate_cron_expression(data.cron_schedule):
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail="Invalid cron expression. Expected format: * * * * * (minute hour day month weekday)",
            )

        schedule = await self.schedule_repository.create(data)
        return await self._to_read(schedule)

    async def get_by_id(self, schedule_id: UUID) -> WorkflowScheduleRead:
        schedule = await self.schedule_repository.get_by_id(schedule_id)
        return await self._to_read(schedule)

    async def list(
        self, is_active: Optional[bool] = None
    ) -> List[WorkflowScheduleRead]:
        schedules = await self.schedule_repository.list(is_active=is_active)
        return [await self._to_read(s) for s in schedules]

    async def update(
        self, schedule_id: UUID, data: WorkflowScheduleUpdate
    ) -> WorkflowScheduleRead:
        schedule = await self.schedule_repository.get_by_id(schedule_id)

        if data.agent_id is not None:
            await self._validate_agent(data.agent_id)

        if data.cron_schedule is not None and not validate_cron_expression(
            data.cron_schedule
        ):
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail="Invalid cron expression. Expected format: * * * * * (minute hour day month weekday)",
            )

        updated = await self.schedule_repository.apply_update(schedule, data)
        return await self._to_read(updated)

    async def delete(self, schedule_id: UUID) -> None:
        # Ensures existence (raises NOT_FOUND) before soft-deleting.
        schedule = await self.schedule_repository.get_by_id(schedule_id)
        await self.schedule_repository.soft_delete(schedule)

    async def get_runs(
        self,
        schedule_id: UUID,
        status: Optional[WorkflowScheduleRunStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowScheduleRunRead]:
        # Ensures the schedule exists / is visible to this tenant.
        await self.schedule_repository.get_by_id(schedule_id)
        runs = await self.run_repository.list_by_schedule(
            schedule_id, status=status, limit=limit, offset=offset
        )
        return [WorkflowScheduleRunRead.model_validate(r) for r in runs]

    async def create_manual_run(self, schedule_id: UUID) -> WorkflowScheduleRunRead:
        """Create a PENDING run for an on-demand execution. The caller (route)
        is responsible for dispatching the Celery task."""
        schedule = await self.schedule_repository.get_by_id(schedule_id)
        run = await self.run_repository.create(
            schedule_id=schedule.id,
            agent_id=schedule.agent_id,
        )
        return WorkflowScheduleRunRead.model_validate(run)