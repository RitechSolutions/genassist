from typing import Tuple
from injector import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import KnowledgeBaseModel
from app.repositories.db_repository import DbRepository
from app.schemas.filter import BaseFilterModel


@inject
class KnowledgeBaseRepository(DbRepository[KnowledgeBaseModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(KnowledgeBaseModel, db)

    async def get_list_paginated(self, filter_obj: BaseFilterModel) -> Tuple[list, int]:
        count_stmt = select(func.count(KnowledgeBaseModel.id))
        total = (await self.db.execute(count_stmt)).scalar() or 0

        data_stmt = select(
            KnowledgeBaseModel.id,
            KnowledgeBaseModel.name,
            KnowledgeBaseModel.type,
            KnowledgeBaseModel.description,
            KnowledgeBaseModel.files,
            KnowledgeBaseModel.urls,
            KnowledgeBaseModel.content,
            KnowledgeBaseModel.sync_active,
            KnowledgeBaseModel.last_synced,
            KnowledgeBaseModel.last_sync_status,
        )
        data_stmt = self._apply_sorting(data_stmt, filter_obj)
        data_stmt = self._apply_pagination(data_stmt, filter_obj)
        rows = (await self.db.execute(data_stmt)).all()
        return rows, total
