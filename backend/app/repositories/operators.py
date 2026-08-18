from typing import List, Optional, Tuple
from uuid import UUID

from injector import inject
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import contains_eager, joinedload

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.repositories.db_repository import DbRepository
from app.schemas.filter import OperatorListFilter


@inject
class OperatorRepository(DbRepository[OperatorModel]):
    """Repository for operator-related database operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(OperatorModel, db)
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

    def _search_condition(self, search: Optional[str]):
        """Case-insensitive substring match on first or last name"""
        if not search or not search.strip():
            return None

        term = search.strip()
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        return or_(
            OperatorModel.first_name.ilike(pattern, escape="\\"),
            OperatorModel.last_name.ilike(pattern, escape="\\"),
        )

    async def get_list_paginated(self, filter_obj: OperatorListFilter) -> Tuple[List[OperatorModel], int]:
        """Return one page of operators plus the unpaginated total"""
        search_condition = self._search_condition(filter_obj.search)

        count_stmt = (
            select(func.count(OperatorModel.id))
            .join(OperatorModel.operator_statistics)
            .where(OperatorModel.is_deleted == 0)
        )
        if search_condition is not None:
            count_stmt = count_stmt.where(search_condition)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        data_stmt = (
            select(OperatorModel)
            .join(OperatorModel.operator_statistics)
            .options(contains_eager(OperatorModel.operator_statistics))
            .where(OperatorModel.is_deleted == 0)
        )
        if search_condition is not None:
            data_stmt = data_stmt.where(search_condition)

        data_stmt = data_stmt.order_by(
            OperatorStatisticsModel.avg_positive_sentiment.desc(),
            OperatorStatisticsModel.score.desc(),
            OperatorModel.id.desc(),
        )
        data_stmt = self._apply_pagination(data_stmt, filter_obj)

        result = await self.db.execute(data_stmt)
        return result.scalars().all(), total
