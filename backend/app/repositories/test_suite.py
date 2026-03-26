from uuid import UUID

from injector import inject
from sqlalchemy import delete, update
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

    async def delete_all_for_suite(self, suite_id: UUID) -> None:
        await self.db.execute(
            update(TestCaseModel)
            .where(TestCaseModel.suite_id == str(suite_id))
            .values(is_deleted=1)
            .execution_options(synchronize_session="fetch")
        )
        await self.db.commit()


@inject
class TestRunRepository(DbRepository[TestRunModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestRunModel, db)


@inject
class TestResultRepository(DbRepository[TestResultModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestResultModel, db)


@inject
class TestEvaluationRepository(DbRepository[TestEvaluationModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestEvaluationModel, db)

