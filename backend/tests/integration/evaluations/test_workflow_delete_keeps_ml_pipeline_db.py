from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model import MLModel, ModelType
from app.db.models.ml_model_pipeline import MLModelPipelineConfig, MLModelPipelineRun
from app.db.models.workflow import WorkflowModel
from app.repositories.workflow import WorkflowRepository
from app.services.workflow import WorkflowService


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _seed_pipeline(session, *, agent_id=None):
    """A workflow version, a model trained on it, its pipeline config and one run."""
    prefix = f"zz_{uuid4().hex[:8]}_"
    workflow_id, model_id, config_id, run_id = uuid4(), uuid4(), uuid4(), uuid4()
    session.add(WorkflowModel(id=workflow_id, name=f"{prefix}workflow", version="1.0", agent_id=agent_id))
    session.add(
        MLModel(
            id=model_id,
            name=f"{prefix}model",
            description="scratch",
            model_type=ModelType.XGBOOST,
            features=[],
            target_variable="y",
        )
    )
    await session.flush()
    session.add(MLModelPipelineConfig(id=config_id, model_id=model_id, workflow_id=workflow_id))
    await session.flush()
    session.add(
        MLModelPipelineRun(id=run_id, model_id=model_id, pipeline_config_id=config_id, workflow_id=workflow_id)
    )
    await session.flush()
    return prefix, workflow_id, config_id


@pytest.mark.asyncio
async def test_a_workflow_row_with_a_pipeline_cannot_be_hard_deleted(db_session):
    """Before migration 00128 this delete removed the config and every run with it."""
    session = db_session
    try:
        _, workflow_id, _ = await _seed_pipeline(session)
        with pytest.raises(IntegrityError):
            await session.execute(delete(WorkflowModel).where(WorkflowModel.id == workflow_id))
    finally:
        await session.rollback()


@pytest.mark.asyncio
async def test_deleting_an_agent_whose_workflow_trains_a_live_model_is_refused(db_session):
    session = db_session
    service = WorkflowService(WorkflowRepository(session))
    agent_id = uuid4()
    try:
        prefix, workflow_id, config_id = await _seed_pipeline(session, agent_id=agent_id)

        with pytest.raises(AppException) as exc:
            await service.soft_delete_by_agent(agent_id, commit=False)
        assert exc.value.status_code == 409
        assert exc.value.error_key == ErrorKey.AGENT_IN_USE_BY_ML_MODEL
        assert exc.value.error_variables == [f"{prefix}model"]
        is_deleted = (
            await session.execute(
                select(WorkflowModel.is_deleted)
                .where(WorkflowModel.id == workflow_id)
                .execution_options(include_deleted=True)
            )
        ).scalar_one()
        assert is_deleted == 0

        # Once the configuration is removed, the agent's versions can be retired.
        config = await session.get(MLModelPipelineConfig, config_id)
        config.is_deleted = 1
        await session.flush()
        await service.soft_delete_by_agent(agent_id, commit=False)
        is_deleted = (
            await session.execute(
                select(WorkflowModel.is_deleted)
                .where(WorkflowModel.id == workflow_id)
                .execution_options(include_deleted=True)
            )
        ).scalar_one()
        assert is_deleted == 1
    finally:
        await session.rollback()


async def _wait_until_blocked_on_a_lock(session, pid, timeout=10.0):
    """Poll pg_stat_activity until backend `pid` waits on a lock."""
    import asyncio

    from sqlalchemy import text

    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        waiting = (
            await session.execute(
                text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
            )
        ).scalar()
        if waiting:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"backend {pid} never waited on a lock")


async def _pid(session):
    from sqlalchemy import text

    return (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()


@pytest_asyncio.fixture
async def committed_pipeline_workflow():
    """An agent's workflow and a model, committed (concurrency needs two sessions); removed afterwards."""
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    agent_id = uuid4()
    async with maker() as setup:
        _, workflow_id, config_id = await _seed_pipeline(setup, agent_id=agent_id)
        model_id = (await setup.get(MLModelPipelineConfig, config_id)).model_id
        await setup.execute(delete(MLModelPipelineRun).where(MLModelPipelineRun.pipeline_config_id == config_id))
        await setup.execute(delete(MLModelPipelineConfig).where(MLModelPipelineConfig.id == config_id))
        await setup.commit()
    try:
        yield maker, agent_id, workflow_id, model_id
    finally:
        async with maker() as cleanup:
            await cleanup.execute(delete(MLModelPipelineConfig).where(MLModelPipelineConfig.workflow_id == workflow_id))
            await cleanup.execute(delete(WorkflowModel).where(WorkflowModel.id == workflow_id))
            await cleanup.execute(delete(MLModel).where(MLModel.id == model_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_an_agent_delete_started_during_a_config_write_sees_the_new_config(committed_pipeline_workflow):
    """The config write holds its version; the delete waits for it, then refuses.

    Without this, the delete found no config, then retired the version the new
    config was about to train on.
    """
    import asyncio

    maker, agent_id, workflow_id, model_id = committed_pipeline_workflow
    async with maker() as configuring, maker() as deleting, maker() as observer:
        assert await WorkflowRepository(configuring).lock_live_shared(workflow_id)
        configuring.add(MLModelPipelineConfig(model_id=model_id, workflow_id=workflow_id))
        await configuring.flush()

        deleting_pid = await _pid(deleting)
        delete_task = asyncio.create_task(
            WorkflowService(WorkflowRepository(deleting)).soft_delete_by_agent(agent_id, commit=False)
        )
        try:
            await _wait_until_blocked_on_a_lock(observer, deleting_pid)
            await configuring.commit()
            with pytest.raises(AppException) as exc:
                await asyncio.wait_for(delete_task, timeout=10)
            assert exc.value.error_key == ErrorKey.AGENT_IN_USE_BY_ML_MODEL
            await deleting.commit()
            assert await WorkflowRepository(observer).lock_live_shared(workflow_id)  # still live
            await observer.rollback()
        finally:
            if not delete_task.done():
                delete_task.cancel()
            await asyncio.gather(delete_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_a_config_write_started_during_an_agent_delete_finds_the_version_gone(committed_pipeline_workflow):
    import asyncio

    maker, agent_id, workflow_id, _ = committed_pipeline_workflow
    async with maker() as deleting, maker() as configuring, maker() as observer:
        await WorkflowService(WorkflowRepository(deleting)).soft_delete_by_agent(agent_id, commit=False)
        configuring_pid = await _pid(configuring)
        lock_task = asyncio.create_task(WorkflowRepository(configuring).lock_live_shared(workflow_id))
        try:
            await _wait_until_blocked_on_a_lock(observer, configuring_pid)
            await deleting.commit()
            assert await asyncio.wait_for(lock_task, timeout=10) is False
        finally:
            if not lock_task.done():
                lock_task.cancel()
            await asyncio.gather(lock_task, return_exceptions=True)
            await configuring.rollback()
