from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from injector import inject
from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.db.models.test_suite import (
    TestSuiteModel,
    TestCaseModel,
    TestRunModel,
    TestResultModel,
    TestEvaluationModel,
    TestToolRuleResultModel,
)
from app.db.models.workflow import WorkflowModel
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
        await self.db.flush()

    async def soft_delete_all_for_suite(
        self, suite_id: UUID, commit: bool = True
    ) -> None:
        """Soft-delete every case in a suite. Skip the commit to batch with later writes."""
        await self.db.execute(
            update(TestCaseModel)
            .where(TestCaseModel.suite_id == str(suite_id))
            .values(is_deleted=1)
            .execution_options(synchronize_session="fetch")
        )
        if commit:
            await self.db.flush()

    async def soft_delete_for_conversation(
        self, suite_id: UUID, conversation_id: UUID, commit: bool = True
    ) -> None:
        """Soft-delete the active cases imported from one source conversation."""
        await self.db.execute(
            update(TestCaseModel)
            .where(
                TestCaseModel.suite_id == str(suite_id),
                TestCaseModel.source_conversation_id == conversation_id,
                TestCaseModel.is_deleted == 0,
            )
            .values(is_deleted=1)
            .execution_options(synchronize_session="fetch")
        )
        if commit:
            await self.db.flush()

    async def create_many(self, cases: List[TestCaseModel]) -> List[TestCaseModel]:
        """Insert cases in a single transaction so a partial import cannot persist."""
        self.db.add_all(cases)
        await self.db.flush()
        for case in cases:
            await self.db.refresh(case)
        return cases


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
        await self.db.flush()

    async def mark_stuck_as_failed(
        self,
        queued_before: datetime,
        running_before: datetime,
        error_message: str,
    ) -> int:
        """Fail runs orphaned by a worker/pod crash in one atomic UPDATE:
        queued runs never picked up, and running runs past the max execution age.
        Returns the number of rows transitioned to failed.
        """
        stmt = (
            update(TestRunModel)
            .where(
                TestRunModel.is_deleted == 0,
                or_(
                    and_(
                        TestRunModel.status == "queued",
                        TestRunModel.updated_at < queued_before,
                    ),
                    and_(
                        TestRunModel.status == "running",
                        TestRunModel.updated_at < running_before,
                    ),
                ),
            )
            .values(status="failed", summary_metrics={"error": error_message})
            .execution_options(synchronize_session=False)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount or 0


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
class TestToolRuleResultRepository(DbRepository[TestToolRuleResultModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TestToolRuleResultModel, db)

    async def create_many(
        self, results: List[TestToolRuleResultModel]
    ) -> List[TestToolRuleResultModel]:
        if not results:
            return []
        self.db.add_all(results)
        await self.db.flush()
        return results

    async def get_all_for_run(self, run_id: UUID) -> List[TestToolRuleResultModel]:
        stmt = (
            select(TestToolRuleResultModel)
            .where(
                TestToolRuleResultModel.run_id == str(run_id),
                TestToolRuleResultModel.is_deleted == 0,
            )
            .order_by(TestToolRuleResultModel.created_at)
        )
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

    @staticmethod
    def _version_ids_of(workflow_id: UUID):
        """Every live version of the workflow ``workflow_id`` belongs to.

        Versions are separate ``workflows`` rows sharing an ``agent_id``, and an
        evaluation is pinned to one of them. Users think in workflows, not
        versions, so the overview and its drill-down span all of them. A
        workflow with no agent matches only itself (comparing against a NULL
        agent yields NULL, never true).
        """
        target_agent = (
            select(WorkflowModel.agent_id)
            .where(WorkflowModel.id == str(workflow_id))
            .scalar_subquery()
        )
        return select(WorkflowModel.id).where(
            WorkflowModel.is_deleted == 0,
            or_(
                WorkflowModel.id == str(workflow_id),
                and_(
                    WorkflowModel.agent_id.is_not(None),
                    WorkflowModel.agent_id == target_agent,
                ),
            ),
        )

    def _workflow_condition(self, workflow_id: Optional[UUID]):
        """Match evaluations by effective workflow: own ``workflow_id`` or, when
        absent, their dataset's default. ``workflow_id=None`` = unassigned.

        A workflow id matches every version of that workflow, so evaluations
        pinned to different versions appear under one row rather than splitting
        into look-alike duplicates.

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
            version_ids = self._version_ids_of(workflow_id)
            workflow_suites = select(suite.id).where(
                suite.workflow_id.in_(version_ids), suite.is_deleted == 0
            )
            conditions.append(
                or_(
                    evaluation.workflow_id.in_(version_ids),
                    and_(
                        evaluation.workflow_id.is_(None),
                        evaluation.suite_id.in_(workflow_suites),
                    ),
                )
            )
        return and_(*conditions)

    def _grouped_effective_workflow(self):
        """(group key expression, joins) collapsing versions onto one workflow.

        The key is the agent's live version, so every evaluation of a workflow
        lands in the same bucket whichever version it is pinned to; workflows
        without an agent keep their own id. Agents are group-scoped while
        workflows are not, so the scope filter is bypassed for the join —
        otherwise the same workflow would bucket differently per caller.
        """
        evaluation = TestEvaluationModel
        suite = TestSuiteModel
        effective = func.coalesce(evaluation.workflow_id, suite.workflow_id)
        return func.coalesce(AgentModel.workflow_id, effective), effective

    def _grouped_select(self, *columns):
        evaluation = TestEvaluationModel
        suite = TestSuiteModel
        _, effective = self._grouped_effective_workflow()
        return (
            select(*columns)
            .select_from(evaluation)
            .outerjoin(
                suite, and_(suite.id == evaluation.suite_id, suite.is_deleted == 0)
            )
            .outerjoin(WorkflowModel, WorkflowModel.id == effective)
            .outerjoin(AgentModel, AgentModel.id == WorkflowModel.agent_id)
            .where(evaluation.is_deleted == 0)
            .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        )

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
        """(workflow_id, count) per workflow; ``None`` = unassigned bucket.

        Versions collapse onto one row, so a workflow never appears twice.
        """
        group_key, _ = self._grouped_effective_workflow()
        stmt = self._grouped_select(
            group_key.label("workflow_id"), func.count().label("count")
        ).group_by(group_key)
        result = await self.db.execute(stmt)
        return [(row.workflow_id, int(row.count)) for row in result.all()]

    async def get_latest_run_pointers(
        self,
    ) -> List[Tuple[Optional[UUID], List[str]]]:
        """(workflow_id, run_ids) for every live evaluation.

        Used to compute per-workflow health: ``run_ids[0]`` is each evaluation's
        latest run. Only the pointer lists are loaded here — not the runs. Keyed
        the same way as ``count_by_effective_workflow`` so health lines up with
        the row it is shown on.
        """
        group_key, _ = self._grouped_effective_workflow()
        stmt = self._grouped_select(
            group_key.label("workflow_id"), TestEvaluationModel.run_ids
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

