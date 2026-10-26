from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.mcp_server import MCPServerModel, MCPServerWorkflowModel
from app.db.models.ml_model import MLModel, ModelType
from app.db.models.ml_model_pipeline import MLModelPipelineConfig
from app.db.models.test_suite import TestEvaluationModel, TestSuiteModel
from app.db.models.user import UserModel
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


async def _read(session, column, row_id):
    result = await session.execute(
        select(column).where(column.class_.id == row_id).execution_options(include_deleted=True)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_deleting_a_version_hides_it_and_keeps_its_test_data(db_session):
    session = db_session
    repository = WorkflowRepository(session)
    service = WorkflowService(repository)
    prefix = f"zz_{uuid4().hex[:8]}_"
    ids = SimpleNamespace(v=uuid4(), w=uuid4(), suite=uuid4(), evaluation=uuid4(), model=uuid4(), config=uuid4())

    try:
        user_id = (await session.execute(select(UserModel.id).limit(1))).scalar_one()
        session.add_all(
            [
                WorkflowModel(id=ids.v, name=f"{prefix}workflow", version="1.0", agent_id=None),
                WorkflowModel(id=ids.w, name=f"{prefix}workflow", version="1.1", agent_id=None),
            ]
        )
        await session.flush()
        session.add(TestSuiteModel(id=ids.suite, name=f"{prefix}suite", workflow_id=ids.v))
        live_server = MCPServerModel(name=f"{prefix}live", auth_values={}, user_id=user_id)
        gone_server = MCPServerModel(name=f"{prefix}gone", auth_values={}, user_id=user_id, is_deleted=1)
        session.add_all(
            [
                live_server,
                gone_server,
                MLModel(
                    id=ids.model,
                    name=f"{prefix}model",
                    description="scratch",
                    model_type=ModelType.XGBOOST,
                    features=[],
                    target_variable="y",
                ),
            ]
        )
        await session.flush()
        session.add(
            TestEvaluationModel(
                id=ids.evaluation,
                name=f"{prefix}evaluation",
                suite_id=ids.suite,
                workflow_id=ids.v,
                techniques=[],
                run_ids=[],
            )
        )
        live_link = MCPServerWorkflowModel(
            mcp_server_id=live_server.id, workflow_id=ids.v, tool_name="live", tool_description="live"
        )
        session.add_all(
            [
                live_link,
                MCPServerWorkflowModel(
                    mcp_server_id=gone_server.id, workflow_id=ids.v, tool_name="gone", tool_description="gone"
                ),
            ]
        )
        config = MLModelPipelineConfig(id=ids.config, model_id=ids.model, workflow_id=ids.v)
        session.add(config)
        await session.flush()

        with pytest.raises(AppException) as exc:
            await service.delete(ids.v)
        assert exc.value.status_code == 409
        assert exc.value.error_key == ErrorKey.WORKFLOW_VERSION_IN_USE_BY_MCP_SERVER
        assert exc.value.error_variables == [f"{prefix}live"]

        await session.delete(live_link)
        await session.flush()
        with pytest.raises(AppException) as exc:
            await service.delete(ids.v)
        assert exc.value.status_code == 409
        assert exc.value.error_key == ErrorKey.WORKFLOW_VERSION_IN_USE_BY_ML_MODEL
        assert exc.value.error_variables == [f"{prefix}model"]

        config.is_deleted = 1
        await session.flush()

        await repository.repoint_test_data(ids.v, ids.w)
        await session.flush()
        assert await _read(session, TestSuiteModel.workflow_id, ids.suite) == ids.w
        assert await _read(session, TestEvaluationModel.workflow_id, ids.evaluation) == ids.w

        await repository.repoint_test_data(ids.w, ids.v)
        await session.flush()
        assert await _read(session, TestSuiteModel.workflow_id, ids.suite) == ids.v
        assert await _read(session, TestEvaluationModel.workflow_id, ids.evaluation) == ids.v

        await service.delete(ids.v)
        await session.flush()
        assert await _read(session, WorkflowModel.is_deleted, ids.v) == 1
        assert await _read(session, TestSuiteModel.workflow_id, ids.suite) is None
        assert await _read(session, TestEvaluationModel.workflow_id, ids.evaluation) is None
        assert await _read(session, MLModelPipelineConfig.workflow_id, ids.config) == ids.v
    finally:
        await session.rollback()
