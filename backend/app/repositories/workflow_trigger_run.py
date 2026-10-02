import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from injector import inject
from sqlalchemy import and_, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
from app.db.models.workflow_trigger_run import WorkflowTriggerRunModel
from app.repositories.db_repository import DbRepository

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {
    WorkflowScheduleRunStatus.COMPLETED,
    WorkflowScheduleRunStatus.FAILED,
    WorkflowScheduleRunStatus.CANCELLED,
}


@inject
class WorkflowTriggerRunRepository(DbRepository[WorkflowTriggerRunModel]):
    """Run history of Webhook Trigger deliveries. Mirrors the schedule-run
    repository so the stuck-run reconciler can drive both."""

    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowTriggerRunModel, db)

    async def create(
        self,
        *,
        webhook_id: UUID,
        agent_id: UUID,
        node_id: str,
        workflow_id: Optional[UUID],
        thread_id: Optional[str],
        input_data: Optional[Dict[str, Any]],
        idempotency_key: Optional[str] = None,
    ) -> WorkflowTriggerRunModel:
        run = WorkflowTriggerRunModel(
            webhook_id=webhook_id,
            agent_id=agent_id,
            node_id=node_id,
            workflow_id=workflow_id,
            thread_id=thread_id,
            input_data=input_data,
            idempotency_key=idempotency_key,
            status=WorkflowScheduleRunStatus.PENDING,
        )
        return await super().create(run)

    async def get_by_id(
        self, run_id: UUID, *, eager: Sequence[str] | None = None
    ) -> WorkflowTriggerRunModel:
        run = await super().get_by_id(run_id, eager=eager)
        if not run:
            raise AppException(error_key=ErrorKey.NOT_FOUND)
        return run

    async def get_by_idempotency_key(
        self, webhook_id: UUID, idempotency_key: str
    ) -> Optional[WorkflowTriggerRunModel]:
        query = select(WorkflowTriggerRunModel).where(
            WorkflowTriggerRunModel.webhook_id == webhook_id,
            WorkflowTriggerRunModel.idempotency_key == idempotency_key,
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_by_webhook(
        self,
        webhook_id: UUID,
        status: Optional[WorkflowScheduleRunStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowTriggerRunModel]:
        query = select(WorkflowTriggerRunModel).where(
            WorkflowTriggerRunModel.webhook_id == webhook_id,
        )
        if status:
            query = query.where(WorkflowTriggerRunModel.status == status)
        query = (
            query.order_by(WorkflowTriggerRunModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_last_run(self, webhook_id: UUID) -> Optional[WorkflowTriggerRunModel]:
        query = (
            select(WorkflowTriggerRunModel)
            .where(WorkflowTriggerRunModel.webhook_id == webhook_id)
            .order_by(WorkflowTriggerRunModel.created_at.desc())
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
    ) -> WorkflowTriggerRunModel:
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

    # --- used by the stuck-run reconciler (same contract as schedule runs) ---

    async def get_waiting_ids_older_than(self, before: datetime) -> List[str]:
        stmt = select(WorkflowTriggerRunModel.id).where(
            WorkflowTriggerRunModel.is_deleted == 0,
            WorkflowTriggerRunModel.status == WorkflowScheduleRunStatus.PENDING,
            WorkflowTriggerRunModel.created_at < before,
        )
        result = await self.db.execute(stmt)
        return [str(run_id) for run_id in result.scalars().all()]

    async def mark_orphaned_as_failed(
        self,
        waiting_ids: List[str],
        running_before: datetime,
        error_message: str,
    ) -> int:
        conditions = [
            and_(
                WorkflowTriggerRunModel.status == WorkflowScheduleRunStatus.RUNNING,
                func.coalesce(
                    WorkflowTriggerRunModel.started_at,
                    WorkflowTriggerRunModel.created_at,
                )
                < running_before,
            )
        ]
        if waiting_ids:
            conditions.append(
                and_(
                    WorkflowTriggerRunModel.status == WorkflowScheduleRunStatus.PENDING,
                    WorkflowTriggerRunModel.id.in_(waiting_ids),
                )
            )
        stmt = (
            update(WorkflowTriggerRunModel)
            .where(WorkflowTriggerRunModel.is_deleted == 0, or_(*conditions))
            .values(
                status=WorkflowScheduleRunStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_message=error_message,
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount or 0
