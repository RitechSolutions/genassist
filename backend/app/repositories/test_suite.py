from typing import List
from uuid import UUID

from injector import inject
from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.test_suite import (
    TestSuiteModel,
    TestCaseModel,
    TestRunModel,
    TestResultModel,
    TestEvaluationModel,
)
from app.repositories.db_repository import DbRepository


@inject
class TestSuiteRepository(DbRepository[TestSuiteModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestSuiteModel, db)


@inject
class TestCaseRepository(DbRepository[TestCaseModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestCaseModel, db)

    async def get_all_for_suite(self, suite_id: UUID) -> List[TestCaseModel]:
        stmt = (
            select(TestCaseModel)
            .where(TestCaseModel.suite_id == str(suite_id))
            .order_by(TestCaseModel.id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_all_for_suite(self, suite_id: UUID) -> None:
        await self.db.execute(
            delete(TestCaseModel).where(TestCaseModel.suite_id == str(suite_id))
        )
        await self.db.commit()


@inject
class TestRunRepository(DbRepository[TestRunModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestRunModel, db)

    async def get_all_for_suite(self, suite_id: UUID) -> List[TestRunModel]:
        stmt = select(TestRunModel).where(TestRunModel.suite_id == str(suite_id))
        result = await self.db.execute(stmt)
        return result.scalars().all()


@inject
class TestResultRepository(DbRepository[TestResultModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestResultModel, db)

    async def exists_for_suite(self, suite_id: UUID) -> bool:
        case_ids_stmt = select(TestCaseModel.id).where(
            TestCaseModel.suite_id == str(suite_id)
        )
        stmt = select(exists().where(TestResultModel.case_id.in_(case_ids_stmt)))
        result = await self.db.execute(stmt)
        return bool(result.scalar())

    async def get_all_for_run(self, run_id: UUID) -> List[TestResultModel]:
        stmt = select(TestResultModel).where(TestResultModel.run_id == str(run_id))
        result = await self.db.execute(stmt)
        return result.scalars().all()


@inject
class TestEvaluationRepository(DbRepository[TestEvaluationModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestEvaluationModel, db)

