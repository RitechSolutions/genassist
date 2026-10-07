"""DB-backed proof that orphaned test runs are failed with the right reason.

A queued run whose job left the broker never started, so it must not be told
its worker crashed; a running run past the max age keeps the crash message.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.test_suite import TestRunModel, TestSuiteModel
from app.db.models.workflow import WorkflowModel
from app.repositories.test_suite import TestRunRepository


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_queued_and_running_runs_get_their_own_reason(db_session):
    session = db_session
    prefix = f"zz_{uuid4().hex[:8]}_"
    ids = SimpleNamespace(workflow=uuid4(), suite=uuid4(), lost=uuid4(), stuck=uuid4(), waiting=uuid4())
    long_ago = datetime.now(timezone.utc) - timedelta(days=1)

    try:
        session.add(WorkflowModel(id=ids.workflow, name=f"{prefix}workflow", version="1"))
        session.add(TestSuiteModel(id=ids.suite, name=f"{prefix}suite", workflow_id=None))
        await session.flush()
        for run_id, status in ((ids.lost, "queued"), (ids.stuck, "running"), (ids.waiting, "queued")):
            session.add(
                TestRunModel(
                    id=run_id,
                    suite_id=ids.suite,
                    workflow_id=ids.workflow,
                    status=status,
                    techniques=[],
                    updated_at=long_ago,
                )
            )
        await session.commit()

        failed = await TestRunRepository(session).mark_orphaned_as_failed(
            waiting_ids=[str(ids.lost)],
            running_before=datetime.now(timezone.utc),
            error_message="crashed",
            waiting_error_message="never picked up",
        )
        await session.commit()

        rows = await session.execute(
            select(TestRunModel.id, TestRunModel.status, TestRunModel.summary_metrics).where(
                TestRunModel.suite_id == ids.suite
            )
        )
        by_id = {row.id: (row.status, row.summary_metrics) for row in rows}
        assert failed == 2
        assert by_id[ids.lost] == ("failed", {"error": "never picked up"})
        assert by_id[ids.stuck] == ("failed", {"error": "crashed"})
        # Still in the broker, so it is left alone.
        assert by_id[ids.waiting] == ("queued", None)
    finally:
        await session.rollback()
        for statement in (
            delete(TestRunModel).where(TestRunModel.suite_id == ids.suite),
            delete(TestSuiteModel).where(TestSuiteModel.id == ids.suite),
            delete(WorkflowModel).where(WorkflowModel.id == ids.workflow),
        ):
            await session.execute(statement.execution_options(synchronize_session=False))
        await session.commit()
