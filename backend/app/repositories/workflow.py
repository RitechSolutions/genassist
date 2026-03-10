from injector import inject
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.workflow import WorkflowModel
from app.repositories.db_repository import DbRepository


@inject
class WorkflowRepository(DbRepository[WorkflowModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowModel, db)

    async def get_all(self, *, filter_obj=None, eager=None, training_only=False):
        stmt = select(WorkflowModel)
        if training_only:
            stmt = stmt.where(
                WorkflowModel.nodes.isnot(None),
                text(
                    "EXISTS (SELECT 1 FROM jsonb_array_elements(workflows.nodes) AS elem "
                    "WHERE elem->>'type' = 'trainModelNode')"
                ),
            )
        stmt = self._apply_eager_options(stmt, eager)
        if filter_obj:
            stmt = self._apply_filters(stmt, filter_obj)
            stmt = self._apply_sorting(stmt, filter_obj)
            stmt = self._apply_pagination(stmt, filter_obj)
        elif hasattr(WorkflowModel, "created_at"):
            stmt = stmt.order_by(WorkflowModel.created_at.asc())
        result = await self.db.execute(stmt)
        return result.scalars().all()
