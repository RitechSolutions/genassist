from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import KnowledgeBaseModel

from app.repositories.db_repository import DbRepository

@inject
class KnowledgeBaseRepository(DbRepository[KnowledgeBaseModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(KnowledgeBaseModel, db)
