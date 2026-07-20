from typing import List, Optional, Tuple
from uuid import UUID

from injector import inject
from sqlalchemy import and_, delete, exists, func, or_, select, update
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

    async def soft_delete_all_for_suite(self, suite_id: UUID) -> None:
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

    async def get_all_for_suite(self, suite_id: UUID) -> List[TestRunModel]:
        stmt = select(TestRunModel).where(TestRunModel.suite_id == str(suite_id))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_ids(self, ids: List[str]) -> List[TestRunModel]:
        if not ids:
            return []
        stmt = select(TestRunModel).where(TestRunModel.id.in_(ids))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def soft_delete_all_by_ids(self, run_ids: List[str]) -> None:
        if not run_ids:
            return
        await self.db.execute(
            update(TestRunModel)
            .where(TestRunModel.id.in_(run_ids))
            .values(is_deleted=1)
            .execution_options(synchronize_session="fetch")
        )
        await self.db.commit()


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

    async def get_all_for_suite(self, suite_id: UUID) -> List[TestEvaluationModel]:
        stmt = select(TestEvaluationModel).where(
            TestEvaluationModel.suite_id == str(suite_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    def _workflow_condition(self, workflow_id: Optional[UUID]):
        """Match evaluations by effective workflow: own ``workflow_id`` or, when
        absent, their dataset's default. ``workflow_id=None`` = unassigned.

        An evaluation is unassigned when it has no ``workflow_id`` and its suite
        does not resolve to a live workflow — including evals whose suite was
        soft-deleted. This mirrors ``count_by_effective_workflow`` (which coalesces
        against the live suite), so the count and the list always agree.
        """
        evaluation = TestEvaluationModel
        suite = TestSuiteModel
        conditions = [evaluation.is_deleted == 0]
        if workflow_id is None:
            suites_with_workflow = select(suite.id).where(
                suite.workflow_id.is_not(None), suite.is_deleted == 0
            )
            conditions.append(evaluation.workflow_id.is_(None))
            conditions.append(
                or_(
                    evaluation.suite_id.is_(None),
                    evaluation.suite_id.not_in(suites_with_workflow),
                )
            )
        else:
            workflow = str(workflow_id)
            workflow_suites = select(suite.id).where(
                suite.workflow_id == workflow, suite.is_deleted == 0
            )
            conditions.append(
                or_(
                    evaluation.workflow_id == workflow,
                    and_(
                        evaluation.workflow_id.is_(None),
                        evaluation.suite_id.in_(workflow_suites),
                    ),
                )
            )
        return and_(*conditions)

    def _search_condition(self, search: Optional[str]):
        if not search or not search.strip():
            return None
        pattern = f"%{search.strip().lower()}%"
        evaluation = TestEvaluationModel
        return or_(
            func.lower(evaluation.name).like(pattern),
            func.lower(func.coalesce(evaluation.description, "")).like(pattern),
        )

    async def get_page_for_workflow(
        self,
        workflow_id: Optional[UUID],
        offset: int,
        limit: int,
        search: Optional[str] = None,
    ) -> List[TestEvaluationModel]:
        stmt = select(TestEvaluationModel).where(self._workflow_condition(workflow_id))
        search_condition = self._search_condition(search)
        if search_condition is not None:
            stmt = stmt.where(search_condition)
        stmt = (
            stmt.order_by(TestEvaluationModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count_for_workflow(
        self, workflow_id: Optional[UUID], search: Optional[str] = None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(TestEvaluationModel)
            .where(self._workflow_condition(workflow_id))
        )
        search_condition = self._search_condition(search)
        if search_condition is not None:
            stmt = stmt.where(search_condition)
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def get_all_for_workflow(
        self, workflow_id: Optional[UUID]
    ) -> List[TestEvaluationModel]:
        """Every evaluation for a workflow (no paging) — the Run all scope."""
        stmt = (
            select(TestEvaluationModel)
            .where(self._workflow_condition(workflow_id))
            .order_by(TestEvaluationModel.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count_by_effective_workflow(self) -> List[Tuple[Optional[UUID], int]]:
        """(effective_workflow_id, count) per workflow; ``None`` = unassigned bucket."""
        evaluation = TestEvaluationModel
        suite = TestSuiteModel
        effective = func.coalesce(evaluation.workflow_id, suite.workflow_id)
        stmt = (
            select(effective.label("workflow_id"), func.count().label("count"))
            .select_from(evaluation)
            .outerjoin(
                suite,
                and_(suite.id == evaluation.suite_id, suite.is_deleted == 0),
            )
            .where(evaluation.is_deleted == 0)
            .group_by(effective)
        )
        result = await self.db.execute(stmt)
        return [(row.workflow_id, int(row.count)) for row in result.all()]

    async def get_latest_run_pointers(
        self,
    ) -> List[Tuple[Optional[UUID], List[str]]]:
        """(effective_workflow_id, run_ids) for every live evaluation.

        Used to compute per-workflow health: ``run_ids[0]`` is each evaluation's
        latest run. Only the pointer lists are loaded here — not the runs.
        """
        evaluation = TestEvaluationModel
        suite = TestSuiteModel
        effective = func.coalesce(evaluation.workflow_id, suite.workflow_id)
        stmt = (
            select(effective.label("workflow_id"), evaluation.run_ids)
            .select_from(evaluation)
            .outerjoin(
                suite,
                and_(suite.id == evaluation.suite_id, suite.is_deleted == 0),
            )
            .where(evaluation.is_deleted == 0)
        )
        result = await self.db.execute(stmt)
        return [(row.workflow_id, list(row.run_ids or [])) for row in result.all()]

    async def get_run_pointers_for_workflow(
        self, workflow_id: Optional[UUID]
    ) -> List[List[str]]:
        """``run_ids`` for every evaluation targeting one workflow (``None`` = unassigned)."""
        stmt = select(TestEvaluationModel.run_ids).where(
            self._workflow_condition(workflow_id)
        )
        result = await self.db.execute(stmt)
        return [list(run_ids or []) for run_ids in result.scalars().all()]

