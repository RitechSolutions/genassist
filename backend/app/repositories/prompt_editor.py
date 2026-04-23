from typing import List, Optional
from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
                PromptVersionModel.is_deleted == 0,
            )
            .order_by(PromptVersionModel.version_number.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_next_version_number(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
    ) -> int:
        stmt = select(func.max(PromptVersionModel.version_number)).where(
            PromptVersionModel.workflow_id == workflow_id,
            PromptVersionModel.node_id == node_id,
            PromptVersionModel.prompt_field == prompt_field,
            PromptVersionModel.is_deleted == 0,
        )
        result = await self.db.execute(stmt)
        max_version = result.scalar()
        return (max_version or 0) + 1

    async def deactivate_all_for_context(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
    ) -> None:
        versions = await self.get_versions_for_context(workflow_id, node_id, prompt_field)
        for v in versions:
            v.is_active = False
        await self.db.flush()


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
            PromptConfigModel.is_deleted == 0,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
