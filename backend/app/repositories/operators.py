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


<<<<<<< HEAD
    async def create(self, operator_data: OperatorCreate):
        """Create an operator with statistics ensuring correct foreign key linking."""

        # Create `OperatorStatistics` first
        new_statistics = OperatorStatisticsModel(
                avg_positive_sentiment=operator_data.operator_statistics.avg_positive_sentiment,
                avg_negative_sentiment=operator_data.operator_statistics.avg_negative_sentiment,
                avg_neutral_sentiment=operator_data.operator_statistics.avg_neutral_sentiment,
                total_duration=operator_data.operator_statistics.total_duration,
                score=operator_data.operator_statistics.score,
                call_count=operator_data.operator_statistics.call_count,
                created_by=context["user_id"]
                )
        self.db.add(new_statistics)
        await self.db.flush()  # Get `id` for statistics

        # Create `Operator` and manually set the relationship
        new_operator = OperatorModel(
                first_name=operator_data.first_name,
                last_name=operator_data.last_name,
                email=operator_data.email,
                is_active=1,
                avatar=operator_data.avatar,
                statistics_id=new_statistics.id,
                operator_statistics=new_statistics,
                created_by = context["user_id"]
                )
        self.db.add(new_operator)
        await self.db.flush()  # Get `id` for operator

        await self.db.commit()
        await self.db.refresh(new_operator, ["operator_statistics"])

        return new_operator
=======
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
>>>>>>> development


    async def get_by_id(self, operator_id: UUID) -> Optional[OperatorModel]:
        """Fetch operator by ID, including operator_statistics."""
        query = (
            select(OperatorModel)
<<<<<<< HEAD
            .options(joinedload(OperatorModel.operator_statistics))  # Load statistics eagerly
=======
            .options(joinedload(OperatorModel.operator_statistics),
                     joinedload(OperatorModel.user))  # Load statistics eagerly
>>>>>>> development
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
<<<<<<< HEAD
            .options(joinedload(OperatorModel.operator_statistics))  # Ensure statistics are preloaded
=======
            .options(joinedload(OperatorModel.operator_statistics),
                     joinedload(OperatorModel.user))  # Ensure statistics are preloaded
>>>>>>> development
        )
        result = await self.db.execute(query)
        return  result.scalars().all()  # Fetch all operators

