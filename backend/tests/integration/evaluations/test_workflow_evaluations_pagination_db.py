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
        # % and _ are searched as typed, not as wildcards.
        assert await eval_repo.count_for_workflow(None, search=f"{prefix}eval%7") == 0
        assert await eval_repo.count_by_effective_workflow(f"{prefix}eval_0_") == []

        # Run all scope (full, unpaginated) and the summary group-by — the paths
        all_scope = await eval_repo.get_all_for_workflow(None)
        assert {e.id for e in created} <= {e.id for e in all_scope}
        summary = dict(await eval_repo.count_by_effective_workflow())
        assert summary.get(None, 0) >= 25  # unassigned bucket includes ours

        # A search counts only what it matches, and drops workflows with no match.
        assert dict(await eval_repo.count_by_effective_workflow(f"{prefix}eval_07")) == {None: 1}
        assert await eval_repo.count_by_effective_workflow(f"{prefix}nope") == []
        assert len(await eval_repo.get_latest_run_pointers(f"{prefix}eval_1")) == 10
    finally:
        for evaluation in created:
            await session.delete(evaluation)
        await session.delete(suite)
        await session.commit()


@pytest.mark.asyncio
async def test_category_filter_and_list_run_in_the_database(db_session):
    session = db_session
    eval_repo = TestEvaluationRepository(session)
    suite_repo = TestSuiteRepository(session)

    prefix = f"zz_{uuid4().hex[:8]}_"
    refunds, escalation = f"{prefix}Refunds", f"{prefix}Escalation"
    suite = await suite_repo.create(
        TestSuiteModel(name=f"{prefix}suite", workflow_id=None, category=escalation)
    )
    created = []
    try:
        for i, category in enumerate([refunds, refunds, None]):
            created.append(
                await eval_repo.create(
                    TestEvaluationModel(
                        name=f"{prefix}eval_{i}",
                        suite_id=suite.id,
                        workflow_id=None,
                        category=category,
                        techniques=[],
                        run_ids=[],
                    )
                )
            )

        # A category matches whatever its case, in SQL.
        assert await eval_repo.count_for_workflow(None, search=prefix, category=refunds.lower()) == 2
        # "" keeps the evaluations with none set.
        none_set = await eval_repo.get_page_for_workflow(None, 0, 10, search=prefix, category="")
        assert [e.name for e in none_set] == [f"{prefix}eval_2"]
        assert dict(await eval_repo.count_by_effective_workflow(prefix, refunds)) == {None: 2}
        assert len(await eval_repo.get_latest_run_pointers(prefix, "")) == 1

        # The list holds datasets' and evaluations' categories, each once.
        categories = await eval_repo.categories()
        assert categories.count(refunds) == 1
        assert escalation in categories
        # A save finds the spelling in use, whatever the case it is typed in.
        assert await eval_repo.category_spelling(escalation.upper()) == escalation
        assert await eval_repo.category_spelling(f"{prefix}nope") is None

        # Run all and export pick the same evaluations as the lists.
        in_refunds = {created[0].id, created[1].id}
        run_all = await eval_repo.get_all_for_workflow(None, category=refunds.upper())
        assert {e.id for e in run_all} == in_refunds
        assert await eval_repo.ids_in_category(refunds.lower()) == in_refunds
        none_set = await eval_repo.ids_in_category("")
        assert created[2].id in none_set and not in_refunds & none_set
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
