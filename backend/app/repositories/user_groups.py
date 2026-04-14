from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_group import UserGroupModel
from app.repositories.db_repository import DbRepository


@inject
class UserGroupRepository(DbRepository[UserGroupModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserGroupModel, db)