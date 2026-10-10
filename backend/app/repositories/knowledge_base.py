from typing import Any, Dict, List, Optional, Sequence, Tuple

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBaseModel
from app.repositories.db_repository import DbRepository
from app.schemas.filter import KnowledgeBaseListFilter


@inject
class KnowledgeBaseRepository(DbRepository[KnowledgeBaseModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(KnowledgeBaseModel, db)

    async def get_list_paginated(self, filter_obj: KnowledgeBaseListFilter) -> Tuple[list, int]:
        """One page of knowledge bases, newest first, plus the filtered total"""
        conditions = [KnowledgeBaseModel.is_deleted == 0]
        search_condition = self._contains_condition(
            filter_obj.search, KnowledgeBaseModel.name, KnowledgeBaseModel.description
        )
        if search_condition is not None:
            conditions.append(search_condition)
        kb_type = (filter_obj.type or "").strip()
        if kb_type:
            conditions.append(KnowledgeBaseModel.type == kb_type)

        count_stmt = select(func.count(KnowledgeBaseModel.id)).where(*conditions)
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
        ).where(*conditions).order_by(KnowledgeBaseModel.created_at.desc(), KnowledgeBaseModel.id.desc())
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
