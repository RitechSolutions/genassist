from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.workflow import WorkflowModel
from app.db.session import get_db
from app.repositories.db_repository import DbRepository


class WorkflowRepository(DbRepository[WorkflowModel]):
    def __init__(self, db: AsyncSession = Depends(get_db)):
        super().__init__(WorkflowModel, db)
