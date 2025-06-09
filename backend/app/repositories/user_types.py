from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from sqlalchemy.future import select

from app.db.models import UserTypeModel
from app.db.session import get_db
from app.schemas.user import UserTypeCreate

class UserTypesRepository:
    """Repository for user-related database operations."""

    def __init__(self, db: AsyncSession = Depends(get_db)):  # Auto-inject db
        self.db = db

    async def create(self, user_type: UserTypeCreate):
        new_user_type = UserTypeModel(
                name=user_type.name,
                )
        self.db.add(new_user_type)
        await self.db.commit()
        await self.db.refresh(new_user_type)
        return new_user_type


    async def get_by_id(self, user_type_id: UUID) -> UserTypeModel | None:
        return await self.db.get(UserTypeModel, user_type_id)


    async def update(self, user_type: UserTypeModel):
        self.db.add(user_type)
        await self.db.commit()
        await self.db.refresh(user_type)
        return user_type


    async def delete(self, user_type: UserTypeModel):
        await self.db.delete(user_type)
        await self.db.commit()


    async def get_all(self) -> list[UserTypeModel]:
        result = await self.db.execute(select(UserTypeModel))
        return result.scalars().all()


    async def get_by_name(self, name: str) -> UserTypeModel | None:
        result = await self.db.execute(select(UserTypeModel).where(UserTypeModel.name == name))
        return result.scalars().first()
