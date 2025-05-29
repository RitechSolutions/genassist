from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ToolModel
from app.db.session import get_db
from app.repositories.db_repository import DbRepository


class ToolRepository(DbRepository[ToolModel]):
    def __init__(self, db: AsyncSession = Depends(get_db)):
        super().__init__(ToolModel, db)
