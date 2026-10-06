"""DB-backed proof that a turn with evaluation results can be deleted.

test_results and test_tool_rule_results reference test_cases without ON DELETE,
so a hard delete of a graded turn violates both foreign keys. Deleting a turn
soft-deletes it instead: the results keep their case, and the dataset stops
showing the turn.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.test_suite import (
    TestCaseModel,
    TestResultModel,
    TestRunModel,
    TestSuiteModel,
    TestToolRuleResultModel,
)
from app.db.models.workflow import WorkflowModel
from app.repositories.test_suite import (
    TestCaseRepository,
    TestEvaluationRepository,
    TestResultRepository,
    TestRunRepository,
    TestSuiteRepository,
    TestToolRuleResultRepository,
)
from app.services.test_suite import TestSuiteService


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def _service(session) -> TestSuiteService:
    return TestSuiteService(
        suite_repo=TestSuiteRepository(session),
        case_repo=TestCaseRepository(session),
        run_repo=TestRunRepository(session),
        result_repo=TestResultRepository(session),
        evaluation_repo=TestEvaluationRepository(session),
        tool_rule_result_repo=TestToolRuleResultRepository(session),
        workflow_service=MagicMock(),
        conversation_repo=MagicMock(),
    )


async def _is_deleted(session, case_id) -> int:
    """Read is_deleted directly; the ORM filters soft-deleted rows out."""
    result = await session.execute(
        select(TestCaseModel.is_deleted)
        .execution_options(include_deleted=True)
        .where(TestCaseModel.id == case_id)
    )
    return result.scalar_one()


async def _case_of(session, model, row_id):
    """The case a stored result points at, read from the database."""
    result = await session.execute(select(model.case_id).where(model.id == row_id))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_deleting_a_graded_turn_keeps_its_results(db_session):
    session = db_session
    service = _service(session)
    prefix = f"zz_{uuid4().hex[:8]}_"
    conversation_id = uuid4()
    # Ids are fixed up front so cleanup never reads an expired ORM object.
    ids = SimpleNamespace(workflow=uuid4(), suite=uuid4(), run=uuid4())

    try:
        session.add(WorkflowModel(id=ids.workflow, name=f"{prefix}workflow", version="1"))
        session.add(TestSuiteModel(id=ids.suite, name=f"{prefix}suite", workflow_id=None))
        await session.flush()

        graded = TestCaseModel(
            suite_id=ids.suite,
            source_conversation_id=conversation_id,
            turn_index=0,
            input_data={"message": "first"},
        )
        kept = TestCaseModel(
            suite_id=ids.suite,
            source_conversation_id=conversation_id,
            turn_index=1,
            input_data={"message": "second"},
        )
        session.add_all([graded, kept])
        await session.flush()

        session.add(
            TestRunModel(
                id=ids.run,
                suite_id=ids.suite,
                workflow_id=ids.workflow,
                status="completed",
                techniques=["route_taken"],
            )
        )
        await session.flush()
        result = TestResultModel(run_id=ids.run, case_id=graded.id, status="scored")
        rule_result = TestToolRuleResultModel(
            run_id=ids.run,
            technique="route_taken",
            rule_id="route-1",
            scope="every_turn",
            case_id=graded.id,
            status="passed",
        )
        session.add_all([result, rule_result])
        await session.commit()

        await service.delete_case(graded.id)
        await session.commit()

        assert await _is_deleted(session, graded.id) == 1
        assert [case.id for case in await service.list_cases_for_suite(ids.suite)] == [kept.id]
        assert await _case_of(session, TestResultModel, result.id) == graded.id
        assert await _case_of(session, TestToolRuleResultModel, rule_result.id) == graded.id

        # The partial unique index only covers live rows, so the position can be reused.
        session.add(
            TestCaseModel(
                suite_id=ids.suite,
                source_conversation_id=conversation_id,
                turn_index=0,
                input_data={"message": "first, rewritten"},
            )
        )
        await session.commit()
    finally:
        await session.rollback()
        # Hard-delete in foreign key order so no row is left behind.
        for statement in (
            delete(TestToolRuleResultModel).where(TestToolRuleResultModel.run_id == ids.run),
            delete(TestResultModel).where(TestResultModel.run_id == ids.run),
            delete(TestRunModel).where(TestRunModel.id == ids.run),
            delete(TestCaseModel).where(TestCaseModel.suite_id == ids.suite),
            delete(TestSuiteModel).where(TestSuiteModel.id == ids.suite),
            delete(WorkflowModel).where(WorkflowModel.id == ids.workflow),
        ):
            await session.execute(statement.execution_options(synchronize_session=False))
        await session.commit()
