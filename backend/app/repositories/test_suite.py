from injector import inject
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

