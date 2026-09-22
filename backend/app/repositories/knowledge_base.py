from typing import Any, Dict, List, Optional, Sequence, Tuple

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


    async def get_all(
        self,
        *,
        filters: Optional[Dict[str, Any]] = None,
        eager: Sequence[str] | None = None,
    ) -> List[KnowledgeBaseModel]:
        stmt = select(KnowledgeBaseModel)
        stmt = self._apply_eager_options(stmt, eager)

        for field, value in (filters or {}).items():
            if not hasattr(KnowledgeBaseModel, field):
                continue
            col = getattr(KnowledgeBaseModel, field)
            if value is None:
                stmt = stmt.where(col.is_(None))
            elif isinstance(value, bool):
                stmt = stmt.where(col == (1 if value else 0))
            else:
                stmt = stmt.where(col == value)

        stmt = stmt.order_by(KnowledgeBaseModel.created_at.asc())
        result = await self.db.execute(stmt)
        return result.scalars().all()
