"""Integration tests for deriving a run's agent from the workflow it executed"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.agent import AgentModel
from app.db.models.llm_usage import CONTROL_SINGLETON_KEY, LlmUsageCaptureRunModel, LlmUsageEventModel
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.user import UserModel
from app.db.models.workflow import WorkflowModel
from app.modules.workflow.usage_context import WorkflowUsageContext
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_recorder import LlmUsageRecorder

CALL_COST = 0.0025
_ENTRY = {"provider": "openai", "model": "gpt-4o", "input_tokens": 1000, "output_tokens": 0}

_WORKFLOW_KEYS = ("owned", "other", "shared", "orphan", "deleted_owner")
_AGENT_SPECS = (
    ("owner", "owned", 0),
    ("other", "other", 0),
    ("sharer_one", "shared", 0),
    ("sharer_two", "shared", 0),
    ("deleted_owner", "deleted_owner", 1),
)


class World:

    def __init__(self, maker):
        self.maker = maker
        self.workflows: dict[str, WorkflowModel] = {}
        self.agents: dict[str, AgentModel] = {}
        self.operator_ids: list = []
        self.statistics_ids: list = []
        self.execution_ids: list[str] = []

    def workflow_id(self, key):
        return self.workflows[key].id

    def agent_id(self, key):
        return self.agents[key].id

    async def record(self, *, source: str = "workflow_test", **context) -> str:
        execution_id = str(uuid4())
        self.execution_ids.append(execution_id)
        state = SimpleNamespace(
            execution_id=execution_id,
            llm_usage=[dict(_ENTRY)],
            thread_id=None,
            status="completed",
        )
        await LlmUsageRecorder().record_workflow_state(
            state, WorkflowUsageContext(source=source, **context), "returned"
        )
        return execution_id

    async def attribution(self, execution_id: str) -> tuple:
        """(event agent, event workflow, capture-run agent, capture-run workflow)"""
        async with self.maker() as session:
            event = (
                await session.execute(
                    select(LlmUsageEventModel.agent_id, LlmUsageEventModel.workflow_id).where(
                        LlmUsageEventModel.execution_id == execution_id
                    )
                )
            ).one()
            run = (
                await session.execute(
                    select(LlmUsageCaptureRunModel.agent_id, LlmUsageCaptureRunModel.workflow_id).where(
                        LlmUsageCaptureRunModel.execution_id == execution_id
                    )
                )
            ).one()
        return (*event, *run)


def _workflow(name: str) -> WorkflowModel:
    return WorkflowModel(id=uuid4(), name=name, version="1", nodes=[], edges=[], is_deleted=0)


def _operator(user_id, statistics_id) -> OperatorModel:
    return OperatorModel(
        id=uuid4(),
        first_name="Attribution",
        last_name="Fixture",
        statistics_id=statistics_id,
        is_active=1,
        user_id=user_id,
        is_deleted=0,
    )


def _agent(name: str, operator_id, workflow_id, *, is_deleted: int) -> AgentModel:
    return AgentModel(
        id=uuid4(),
        name=name,
        is_active=1,
        operator_id=operator_id,
        welcome_message="Welcome",
        workflow_id=workflow_id,
        is_deleted=is_deleted,
    )


@pytest_asyncio.fixture(loop_scope="module")
async def world(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    built = World(maker)

    async with maker() as session:
        await session.execute(
            text("UPDATE llm_usage_control SET capture_enabled = true WHERE singleton_key = :k"),
            {"k": CONTROL_SINGLETON_KEY},
        )
        user_id = (await session.execute(select(UserModel.id).limit(1))).scalar_one()

        for key in _WORKFLOW_KEYS:
            built.workflows[key] = _workflow(f"attribution-{key}")
        session.add_all(built.workflows.values())

        for name, workflow_key, is_deleted in _AGENT_SPECS:
            statistics = OperatorStatisticsModel(id=uuid4(), is_deleted=0)
            session.add(statistics)
            built.statistics_ids.append(statistics.id)
            operator = _operator(user_id, statistics.id)
            session.add(operator)
            built.operator_ids.append(operator.id)
            built.agents[name] = _agent(
                f"attribution-{name}", operator.id, built.workflows[workflow_key].id, is_deleted=is_deleted
            )
        session.add_all(built.agents.values())
        await session.commit()

    try:
        yield built
    finally:
        async with maker() as session:
            if built.execution_ids:
                await session.execute(
                    delete(LlmUsageEventModel).where(LlmUsageEventModel.execution_id.in_(built.execution_ids))
                )
                await session.execute(
                    delete(LlmUsageCaptureRunModel).where(LlmUsageCaptureRunModel.execution_id.in_(built.execution_ids))
                )
            await session.execute(delete(AgentModel).where(AgentModel.id.in_([a.id for a in built.agents.values()])))
            await session.execute(delete(OperatorModel).where(OperatorModel.id.in_(built.operator_ids)))
            await session.execute(
                delete(OperatorStatisticsModel).where(OperatorStatisticsModel.id.in_(built.statistics_ids))
            )
            await session.execute(
                delete(WorkflowModel).where(WorkflowModel.id.in_([w.id for w in built.workflows.values()]))
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_workflow_only_run_derives_its_owning_agent(world):
    execution_id = await world.record(workflow_id=world.workflow_id("owned"))

    event_agent, event_workflow, run_agent, run_workflow = await world.attribution(execution_id)
    assert event_agent == world.agent_id("owner")
    assert event_workflow == world.workflow_id("owned")
    assert run_agent == world.agent_id("owner")
    assert run_workflow == world.workflow_id("owned")


@pytest.mark.asyncio(loop_scope="module")
async def test_explicit_agent_wins_over_the_workflow_owner(world):
    execution_id = await world.record(
        source="chat", agent_id=world.agent_id("other"), workflow_id=world.workflow_id("owned")
    )

    event_agent, _, run_agent, _ = await world.attribution(execution_id)
    assert event_agent == world.agent_id("other")
    assert run_agent == world.agent_id("other")


@pytest.mark.asyncio(loop_scope="module")
async def test_unknown_workflow_stays_unattributed(world):
    execution_id = await world.record(workflow_id=uuid4())

    assert await world.attribution(execution_id) == (None, None, None, None)


@pytest.mark.asyncio(loop_scope="module")
async def test_run_without_a_workflow_stays_unattributed(world):
    execution_id = await world.record(source="node_test")

    assert await world.attribution(execution_id) == (None, None, None, None)


@pytest.mark.asyncio(loop_scope="module")
async def test_unowned_workflow_stays_unattributed(world):
    execution_id = await world.record(workflow_id=world.workflow_id("orphan"))

    event_agent, event_workflow, run_agent, _ = await world.attribution(execution_id)
    assert event_agent is None and run_agent is None
    assert event_workflow == world.workflow_id("orphan")


@pytest.mark.asyncio(loop_scope="module")
async def test_workflow_shared_by_two_agents_stays_unattributed(world):
    execution_id = await world.record(workflow_id=world.workflow_id("shared"))

    event_agent, _, run_agent, _ = await world.attribution(execution_id)
    assert event_agent is None and run_agent is None


@pytest.mark.asyncio(loop_scope="module")
async def test_soft_deleted_owner_stays_unattributed(world):
    execution_id = await world.record(workflow_id=world.workflow_id("deleted_owner"))

    event_agent, _, run_agent, _ = await world.attribution(execution_id)
    assert event_agent is None and run_agent is None


@pytest.mark.asyncio(loop_scope="module")
async def test_agent_filtered_summary_sees_derived_studio_test_cost(world):
    await world.record(workflow_id=world.workflow_id("owned"))
    await world.record(workflow_id=world.workflow_id("other"))
    await world.record(workflow_id=world.workflow_id("orphan"))

    async with world.maker() as session:
        row = await LlmUsageReadRepository(session).summary(LlmUsageQueryParams(), [world.agent_id("owner")])

    total_cost, total_calls = row["sum_cost"], row["total_calls"]
    studio_test_cost = row["agent_studio_test_cost"]
    assert total_calls == 1, "the other agent's run and the unattributed run must stay out of scope"
    assert float(total_cost) == pytest.approx(CALL_COST)
    assert float(studio_test_cost) == pytest.approx(CALL_COST)


@pytest.mark.asyncio(loop_scope="module")
async def test_studio_test_cost_counts_only_studio_test_sources(world):
    workflow_id = world.workflow_id("owned")
    for source in ("workflow_test", "node_test", "test_suite", "schedule", "chat"):
        await world.record(source=source, workflow_id=workflow_id)

    async with world.maker() as session:
        row = await LlmUsageReadRepository(session).summary(LlmUsageQueryParams(), [world.agent_id("owner")])

    total_cost, total_calls = row["sum_cost"], row["total_calls"]
    studio_test_cost = row["agent_studio_test_cost"]
    assert total_calls == 5
    assert float(total_cost) == pytest.approx(CALL_COST * 5)
    assert float(studio_test_cost) == pytest.approx(CALL_COST * 2), "only /test and /test-node runs count"
