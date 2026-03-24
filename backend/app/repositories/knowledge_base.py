from typing import Dict, Any, List, Optional, Sequence

from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBaseModel
from app.repositories.db_repository import DbRepository


@inject
class KnowledgeBaseRepository(DbRepository[KnowledgeBaseModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(KnowledgeBaseModel, db)

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
