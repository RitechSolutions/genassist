from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.future import select
from typing import List
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.operator import OperatorModel
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

@inject
class OperatorRepository:
    """Repository for operator-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
    # def __init__(self, session_factory: async_sessionmaker):
    #     self.session_factory = session_factory

    async def create(self, operator: OperatorModel) -> OperatorModel:
        self.db.add(operator)
        await self.db.commit()
        await self.db.refresh(operator, ["operator_statistics", "user"])
        return operator
        # async with self.session_factory() as session:
        #     session.add(operator)
        #     await session.commit()
        #     await session.refresh(operator, ["operator_statistics", "user"])
        #     return operator


    async def add_and_flush(self, operator: OperatorModel) -> OperatorModel:
        self.db.add(operator)
        await self.db.flush()
        await self.db.refresh(operator, ["operator_statistics", "user"])
        return operator
        # async with self.session_factory() as session:
        #     session.add(operator)
        #     await session.flush()
        #     await session.refresh(operator, ["operator_statistics", "user"])
        #     return operator


    async def get_by_id(self, operator_id: UUID) -> Optional[OperatorModel]:
        """Fetch operator by ID, including operator_statistics."""
        query = (
            select(OperatorModel)
            .options(joinedload(OperatorModel.operator_statistics),
                    joinedload(OperatorModel.user))
            .where(OperatorModel.id == operator_id)
        )
        result = await self.db.execute(query)
        operator = result.scalars().first()

        if not operator:
            raise AppException(error_key=ErrorKey.OPERATOR_NOT_FOUND)

        return operator
        # async with self.session_factory() as session:
        #     query = (
        #         select(OperatorModel)
        #         .options(joinedload(OperatorModel.operator_statistics),
        #                 joinedload(OperatorModel.user))
        #         .where(OperatorModel.id == operator_id)
        #     )
        #     result = await session.execute(query)
        #     operator = result.scalars().first()

        #     if not operator:
        #         raise AppException(error_key=ErrorKey.OPERATOR_NOT_FOUND)

        #     return operator

    async def get_all(self) -> List[OperatorModel]:
        """Fetch all operators including their statistics."""
        query = (
            select(OperatorModel)
            .options(joinedload(OperatorModel.operator_statistics),
                     joinedload(OperatorModel.user))  # Ensure statistics are preloaded
        )
        result = await self.db.execute(query)
        return  result.scalars().all()  # Fetch all operators
        # async with self.session_factory() as session:
        #     query = (
        #         select(OperatorModel)
        #         .options(
        #             joinedload(OperatorModel.operator_statistics),
        #             joinedload(OperatorModel.user)
        #         )
        #     )
        #     result = await session.execute(query)
        #     return result.scalars().all()
