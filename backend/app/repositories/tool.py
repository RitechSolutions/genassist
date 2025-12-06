from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ToolModel
from app.repositories.db_repository import DbRepository

@inject
class ToolRepository(DbRepository[ToolModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(ToolModel, db)
