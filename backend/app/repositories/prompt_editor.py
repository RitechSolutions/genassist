from typing import List, Optional
from uuid import UUID

from injector import inject
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.events.soft_delete import SOFT_DELETE_FLAG
from app.db.models.prompt_editor import PromptConfigModel, PromptVersionModel
from app.repositories.db_repository import DbRepository


@inject
class PromptVersionRepository(DbRepository[PromptVersionModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(PromptVersionModel, db)

    async def get_versions_for_context(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
    ) -> List[PromptVersionModel]:
        stmt = (
            select(PromptVersionModel)
            .where(
                PromptVersionModel.workflow_id == workflow_id,
                PromptVersionModel.node_id == node_id,
                PromptVersionModel.prompt_field == prompt_field,
            )
            .order_by(PromptVersionModel.version_number.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def next_version_number(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
    ) -> int:
        """MAX includes soft-deleted rows to avoid reissuing their numbers.
        Live-only MAX breaks the next insert due to uq_prompt_version_context.
        """
        stmt = (
            select(func.max(PromptVersionModel.version_number))
            .where(
                PromptVersionModel.workflow_id == workflow_id,
                PromptVersionModel.node_id == node_id,
                PromptVersionModel.prompt_field == prompt_field,
            )
            .execution_options(**{SOFT_DELETE_FLAG: True})
        )
        result = await self.db.execute(stmt)
        return (result.scalar() or 0) + 1

    async def deactivate_all_for_context(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
    ) -> None:
        """One UPDATE replaces per-row ORM loop (which audited every version).
        Soft-delete predicate explicit: listeners only rewrite SELECTs.
        """
        await self.db.execute(
            update(PromptVersionModel)
            .where(
                PromptVersionModel.workflow_id == workflow_id,
                PromptVersionModel.node_id == node_id,
                PromptVersionModel.prompt_field == prompt_field,
                PromptVersionModel.is_deleted == 0,
                PromptVersionModel.is_active.is_(True),
            )
            .values(is_active=False)
            .execution_options(synchronize_session="fetch")
        )


@inject
class PromptConfigRepository(DbRepository[PromptConfigModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(PromptConfigModel, db)

    async def get_by_context(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
    ) -> Optional[PromptConfigModel]:
        stmt = select(PromptConfigModel).where(
            PromptConfigModel.workflow_id == workflow_id,
            PromptConfigModel.node_id == node_id,
            PromptConfigModel.prompt_field == prompt_field,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_or_create(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
    ) -> PromptConfigModel:
        existing = await self.get_by_context(workflow_id, node_id, prompt_field)
        if existing is not None:
            return existing

        row = PromptConfigModel(
            workflow_id=workflow_id,
            node_id=node_id,
            prompt_field=prompt_field,
        )
        try:
            # A concurrent first save hits uq_prompt_config_context; the SAVEPOINT
            # rolls back alone and leaves the outer transaction usable
            async with self.db.begin_nested():
                self.db.add(row)
                await self.db.flush()
        except IntegrityError:
            winner = await self.get_by_context(workflow_id, node_id, prompt_field)
            if winner is None:
                raise
            return winner
        await self.db.refresh(row)
        return row
