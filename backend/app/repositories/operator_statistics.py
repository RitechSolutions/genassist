from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models.operator import OperatorStatisticsModel,OperatorModel


@inject
class OperatorStatisticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_by_operator_id(self, operator_id: UUID):
        result = await self.db.execute(
                select(OperatorStatisticsModel)
                .join(OperatorStatisticsModel.operator)
                .where(OperatorModel.id == operator_id)
                )
        return result.scalar_one_or_none()


    async def create(self, operator_id: UUID):
        new_stats = OperatorStatisticsModel(id=operator_id)
        self.db.add(new_stats)
        await self.db.commit()
        await self.db.refresh(new_stats)
        return new_stats


    async def update(self, operator_id: UUID, **kwargs):
        # Step 1: Get the statistics_id from operator
        result = await self.db.execute(
                select(OperatorModel.statistics_id).where(OperatorModel.id == operator_id)
                )
        statistics_id = result.scalar_one_or_none()

        # Step 2: Update the statistics table
        await self.db.execute(
                update(OperatorStatisticsModel)
                .where(OperatorStatisticsModel.id == statistics_id)
                .values(**kwargs)
                )
        await self.db.commit()
