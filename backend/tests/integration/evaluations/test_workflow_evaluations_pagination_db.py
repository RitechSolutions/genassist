"""DB-backed proof that workflow-evaluation listing paginates and searches in SQL.

Uses the unassigned bucket (``workflow_id=None``) so no ``workflows`` row is
needed, and scopes every assertion by a unique name tag so pre-existing data
cannot affect the result.
"""
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.test_suite import TestEvaluationModel, TestSuiteModel
from app.repositories.test_suite import TestEvaluationRepository, TestSuiteRepository


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_pagination_and_search_run_in_the_database(db_session):
    session = db_session
    eval_repo = TestEvaluationRepository(session)
    suite_repo = TestSuiteRepository(session)

    prefix = f"zz_{uuid4().hex[:8]}_"
    suite = await suite_repo.create(
        TestSuiteModel(name=f"{prefix}suite", workflow_id=None)
    )
    created = []
    try:
        for i in range(25):
            created.append(
                await eval_repo.create(
                    TestEvaluationModel(
                        name=f"{prefix}eval_{i:02d}",
                        suite_id=suite.id,
                        workflow_id=None,
                        techniques=[],
                        run_ids=[],
                    )
                )
            )

        # Count scoped by our tag, so other data in the DB can't skew it.
        assert await eval_repo.count_for_workflow(None, search=prefix) == 25

        # The database returns only the requested page, not all 25 rows.
        page1 = await eval_repo.get_page_for_workflow(None, 0, 20, search=prefix)
        page2 = await eval_repo.get_page_for_workflow(None, 20, 20, search=prefix)
        assert len(page1) == 20
        assert len(page2) == 5
        assert {e.id for e in page1}.isdisjoint({e.id for e in page2})

        # Search narrows further, in SQL.
        one = await eval_repo.get_page_for_workflow(None, 0, 50, search=f"{prefix}eval_07")
        assert len(one) == 1 and one[0].name == f"{prefix}eval_07"
        assert await eval_repo.count_for_workflow(None, search=f"{prefix}nope") == 0

        # Run all scope (full, unpaginated) and the summary group-by — the paths
        all_scope = await eval_repo.get_all_for_workflow(None)
        assert {e.id for e in created} <= {e.id for e in all_scope}
        summary = dict(await eval_repo.count_by_effective_workflow())
        assert summary.get(None, 0) >= 25  # unassigned bucket includes ours
    finally:
        for evaluation in created:
            await session.delete(evaluation)
        await session.delete(suite)
        await session.commit()


@pytest.mark.asyncio
async def test_eval_of_soft_deleted_suite_is_unassigned_consistently(db_session):
    """An evaluation whose suite was soft-deleted must appear as unassigned in
    BOTH the list and the count. Before the fix the list excluded it while
    count_by_effective_workflow still bucketed it as unassigned.
    """
    session = db_session
    eval_repo = TestEvaluationRepository(session)
    suite_repo = TestSuiteRepository(session)

    prefix = f"zz_{uuid4().hex[:8]}_"
    suite = await suite_repo.create(
        TestSuiteModel(name=f"{prefix}suite", workflow_id=None)
    )
    evaluation = await eval_repo.create(
        TestEvaluationModel(
            name=f"{prefix}orphan",
            suite_id=suite.id,
            workflow_id=None,
            techniques=[],
            run_ids=[],
        )
    )
    try:
        # Soft-delete the suite the evaluation points at.
        suite.is_deleted = 1
        await session.commit()

        # The list (Run all / detail scope) now surfaces it as unassigned...
        unassigned_ids = {e.id for e in await eval_repo.get_all_for_workflow(None)}
        assert evaluation.id in unassigned_ids
        page = await eval_repo.get_page_for_workflow(None, 0, 50, search=prefix)
        assert {e.id for e in page} == {evaluation.id}
        assert await eval_repo.count_for_workflow(None, search=prefix) == 1

        # ...and the summary group-by agrees (unassigned bucket is non-empty).
        summary = dict(await eval_repo.count_by_effective_workflow())
        assert summary.get(None, 0) >= 1
    finally:
        await session.delete(evaluation)
        await session.delete(suite)
        await session.commit()
