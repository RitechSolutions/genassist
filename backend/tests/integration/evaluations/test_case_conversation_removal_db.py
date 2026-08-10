"""DB-backed proof that removing one conversation's cases is scoped correctly.

The soft-delete must match on both dataset and conversation: removing A from
dataset Y must leave Y's other conversation alone and must not touch the same
conversation imported into a different dataset.
"""
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.test_suite import TestCaseModel, TestSuiteModel
from app.repositories.test_suite import TestCaseRepository, TestSuiteRepository


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _add_case(session, suite_id, conversation_id, turn_index):
    case = TestCaseModel(
        suite_id=suite_id,
        source_conversation_id=conversation_id,
        turn_index=turn_index,
        input_data={"message": f"turn {turn_index}"},
    )
    session.add(case)
    await session.commit()
    return case


async def _is_deleted(session, case_id) -> int:
    """Read is_deleted directly; the ORM filters soft-deleted rows out."""
    result = await session.execute(
        select(TestCaseModel.is_deleted)
        .execution_options(include_deleted=True)
        .where(TestCaseModel.id == case_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_removal_is_scoped_by_dataset_and_conversation(db_session):
    session = db_session
    case_repo = TestCaseRepository(session)
    suite_repo = TestSuiteRepository(session)

    prefix = f"zz_{uuid4().hex[:8]}_"
    conversation_a, conversation_b = uuid4(), uuid4()

    suite_y = await suite_repo.create(
        TestSuiteModel(name=f"{prefix}y", workflow_id=None)
    )
    suite_z = await suite_repo.create(
        TestSuiteModel(name=f"{prefix}z", workflow_id=None)
    )
    cases = []
    try:
        y_a = [
            await _add_case(session, suite_y.id, conversation_a, i) for i in range(2)
        ]
        y_b = [
            await _add_case(session, suite_y.id, conversation_b, i) for i in range(2)
        ]
        z_a = [
            await _add_case(session, suite_z.id, conversation_a, i) for i in range(2)
        ]
        cases = y_a + y_b + z_a

        await case_repo.soft_delete_for_conversation(suite_y.id, conversation_a)

        for case in y_a:
            assert await _is_deleted(session, case.id) == 1
        for case in y_b:
            assert await _is_deleted(session, case.id) == 0
        for case in z_a:
            assert await _is_deleted(session, case.id) == 0
    finally:
        # Hard-delete: the models soft-delete on session.delete, which would leave rows behind.
        if cases:
            await session.execute(
                delete(TestCaseModel).where(
                    TestCaseModel.id.in_([case.id for case in cases])
                )
            )
        await session.execute(
            delete(TestSuiteModel).where(
                TestSuiteModel.id.in_([suite_y.id, suite_z.id])
            )
        )
        await session.commit()
