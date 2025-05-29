from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.future import select
from typing import List
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.operator import OperatorModel
from app.db.models.operator import OperatorStatisticsModel
from fastapi import Depends
from app.db.session import get_db
from app.schemas.operator import OperatorCreate
from typing import Optional
from starlette_context import context

class OperatorRepository:
    """Repository for operator-related database operations."""

    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db


    async def create(self, operator: OperatorModel) -> OperatorModel:
        self.db.add(operator)
        await self.db.commit()
        await self.db.refresh(operator, ["operator_statistics", "user"])
        return operator


    async def add_and_flush(self, operator: OperatorModel) -> OperatorModel:
        self.db.add(operator)
        await self.db.flush()
        await self.db.refresh(operator, ["operator_statistics", "user"])
        return operator


    async def get_by_id(self, operator_id: UUID) -> Optional[OperatorModel]:
        """Fetch operator by ID, including operator_statistics."""
        query = (
            select(OperatorModel)
            .options(joinedload(OperatorModel.operator_statistics),
                     joinedload(OperatorModel.user))  # Load statistics eagerly
            .where(OperatorModel.id == operator_id)
        )
        result = await self.db.execute(query)
        operator = result.scalars().first()

        if not operator:
            raise AppException(error_key=ErrorKey.OPERATOR_NOT_FOUND)

        return operator

    async def get_all(self) -> List[OperatorModel]:
        """Fetch all operators including their statistics."""
        query = (
            select(OperatorModel)
            .options(joinedload(OperatorModel.operator_statistics),
                     joinedload(OperatorModel.user))  # Ensure statistics are preloaded
        )
        result = await self.db.execute(query)
        return  result.scalars().all()  # Fetch all operators

