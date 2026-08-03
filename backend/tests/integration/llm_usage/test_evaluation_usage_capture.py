"""Integration tests for recording evaluation judge LLM usage in the ledger"""

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
from app.db.multi_tenant_session import MultiTenantSessionManager
from app.repositories.agent import AgentRepository
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_read import LlmUsageReadService
from app.services.llm_usage_recorder import LlmUsageRecorder

_USAGE = {"input_tokens": 1000, "output_tokens": 0, "total_tokens": 1000}
JUDGE_CALL_COST = 0.0025


def _entries(*purposes, model="gpt-4o") -> list[dict]:
    return [
        {
            "call_index": index,
            "purpose": purpose,
            "provider": "openai",
            "model": model,
            "usage": dict(_USAGE),
            "llm_provider_id": None,
        }
        for index, purpose in enumerate(purposes)
    ]


def _cost(items: dict, key: str) -> float:
    item = items.get(key)
    return float(item.cost_usd) if item else 0.0


class World:

    def __init__(self, maker, agent_id, workflow_id, historical_workflow_id):
        self.maker = maker
        self.agent_id = agent_id
        self.workflow_id = workflow_id
        self.historical_workflow_id = historical_workflow_id
        self.execution_ids: list[str] = []

    async def record(self, *purposes, execution_id=None, workflow_id=True, agent_id=None, model="gpt-4o") -> str:
        execution_id = execution_id or f"eval:{uuid4()}"
        if execution_id not in self.execution_ids:
            self.execution_ids.append(execution_id)
        target_workflow = self.workflow_id if workflow_id is True else (workflow_id or None)
        await LlmUsageRecorder().record_evaluation_calls(
            execution_id,
            _entries(*purposes, model=model),
            workflow_id=target_workflow,
            agent_id=agent_id,
        )
        return execution_id

    async def events(self, execution_id: str) -> list:
        async with self.maker() as session:
            rows = await session.execute(
                select(
                    LlmUsageEventModel.call_index,
                    LlmUsageEventModel.purpose,
                    LlmUsageEventModel.source_type,
                    LlmUsageEventModel.source,
                    LlmUsageEventModel.agent_id,
                    LlmUsageEventModel.workflow_id,
                    LlmUsageEventModel.cost_usd,
                )
                .where(LlmUsageEventModel.execution_id == execution_id)
                .order_by(LlmUsageEventModel.call_index)
            )
            return list(rows.all())

    async def receipts(self, execution_id: str) -> list:
        async with self.maker() as session:
            rows = await session.execute(
                select(
                    LlmUsageCaptureRunModel.source_type,
                    LlmUsageCaptureRunModel.expected_entries,
                    LlmUsageCaptureRunModel.persisted_events,
                    LlmUsageCaptureRunModel.agent_id,
                    LlmUsageCaptureRunModel.execution_outcome,
                ).where(LlmUsageCaptureRunModel.execution_id == execution_id)
            )
            return list(rows.all())

    async def breakdown(self, dimension: str, *, scoped=True) -> dict:
        params = LlmUsageQueryParams(agent_id=self.agent_id if scoped else None)
        async with self.maker() as session:
            service = LlmUsageReadService(
                LlmUsageReadRepository(session), AgentRepository(session), WorkflowRepository(session)
            )
            response = await service.get_breakdown(params, dimension)
        return {item.key: item for item in response.items}

    async def set_capture(self, enabled: bool) -> None:
        async with self.maker() as session:
            await session.execute(
                text("UPDATE llm_usage_control SET capture_enabled = :on WHERE singleton_key = :k"),
                {"on": enabled, "k": CONTROL_SINGLETON_KEY},
            )
            await session.commit()


@pytest_asyncio.fixture(loop_scope="module")
async def world(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        await session.execute(
            text("UPDATE llm_usage_control SET capture_enabled = true WHERE singleton_key = :k"),
            {"k": CONTROL_SINGLETON_KEY},
        )
        user_id = (await session.execute(select(UserModel.id).limit(1))).scalar_one()
        workflow = WorkflowModel(id=uuid4(), name="eval-capture", version="1", nodes=[], edges=[], is_deleted=0)
        statistics = OperatorStatisticsModel(id=uuid4(), is_deleted=0)
        session.add_all([workflow, statistics])
        operator = OperatorModel(
            id=uuid4(),
            first_name="Evaluation",
            last_name="Fixture",
            statistics_id=statistics.id,
            is_active=1,
            user_id=user_id,
            is_deleted=0,
        )
        session.add(operator)
        agent = AgentModel(
            id=uuid4(),
            name="eval-capture-agent",
            is_active=1,
            operator_id=operator.id,
            welcome_message="Welcome",
            workflow_id=workflow.id,
            is_deleted=0,
        )
        session.add(agent)
        historical = WorkflowModel(
            id=uuid4(),
            name="eval-capture",
            version="0",
            nodes=[],
            edges=[],
            agent_id=agent.id,
            is_deleted=0,
        )
        session.add(historical)
        await session.commit()

    built = World(maker, agent.id, workflow.id, historical.id)
    try:
        yield built
    finally:
        async with maker() as session:
            if built.execution_ids:
                await session.execute(
                    delete(LlmUsageEventModel).where(LlmUsageEventModel.execution_id.in_(built.execution_ids))
                )
                await session.execute(
                    delete(LlmUsageCaptureRunModel).where(
                        LlmUsageCaptureRunModel.execution_id.in_(built.execution_ids)
                    )
                )
            await session.execute(delete(AgentModel).where(AgentModel.id == agent.id))
            await session.execute(delete(OperatorModel).where(OperatorModel.id == operator.id))
            await session.execute(delete(OperatorStatisticsModel).where(OperatorStatisticsModel.id == statistics.id))
            await session.execute(delete(WorkflowModel).where(WorkflowModel.id.in_([workflow.id, historical.id])))
            await session.execute(
                text("UPDATE llm_usage_control SET capture_enabled = true WHERE singleton_key = :k"),
                {"k": CONTROL_SINGLETON_KEY},
            )
            await session.commit()
        await engine.dispose()
        await MultiTenantSessionManager().close_all()


@pytest.mark.asyncio(loop_scope="module")
async def test_a_case_writes_one_event_per_judge_and_one_receipt(world):
    execution_id = await world.record("llm_judge", "provenance_judge")

    events = await world.events(execution_id)
    assert [(e.call_index, e.purpose) for e in events] == [(0, "llm_judge"), (1, "provenance_judge")]
    assert {e.source_type for e in events} == {"evaluation"}
    assert {e.source for e in events} == {"test_suite"}

    receipt = (await world.receipts(execution_id))[0]
    assert (receipt.source_type, receipt.expected_entries, receipt.persisted_events) == ("evaluation", 2, 2)
    assert receipt.execution_outcome == "returned"


@pytest.mark.asyncio(loop_scope="module")
async def test_judge_events_are_attributed_to_the_workflows_owning_agent(world):
    execution_id = await world.record("llm_judge")

    events = await world.events(execution_id)
    receipt = (await world.receipts(execution_id))[0]
    assert events[0].agent_id == world.agent_id and events[0].workflow_id == world.workflow_id
    assert receipt.agent_id == world.agent_id


@pytest.mark.asyncio(loop_scope="module")
async def test_evaluating_a_historical_version_still_bills_its_owning_agent(world):
    before_source = await world.breakdown("source")
    before_method = await world.breakdown("evaluation_method")

    execution_id = await world.record(
        "llm_judge",
        "provenance_judge",
        workflow_id=world.historical_workflow_id,
        agent_id=world.agent_id,
    )

    events = await world.events(execution_id)
    receipt = (await world.receipts(execution_id))[0]
    assert {e.workflow_id for e in events} == {world.historical_workflow_id}
    assert {e.agent_id for e in events} == {world.agent_id}, "no agent has this version active any more"
    assert receipt.agent_id == world.agent_id

    after_source = await world.breakdown("source")
    after_method = await world.breakdown("evaluation_method")
    assert _cost(after_source, "evaluation") - _cost(before_source, "evaluation") == pytest.approx(2 * JUDGE_CALL_COST)
    assert _cost(after_method, "llm_judge") - _cost(before_method, "llm_judge") == pytest.approx(JUDGE_CALL_COST)
    assert _cost(after_method, "provenance_judge") - _cost(before_method, "provenance_judge") == pytest.approx(
        JUDGE_CALL_COST
    )


@pytest.mark.asyncio(loop_scope="module")
async def test_a_run_without_a_workflow_stays_unattributed_but_still_counts(world):
    execution_id = await world.record("llm_judge", workflow_id=False)

    events = await world.events(execution_id)
    assert len(events) == 1
    assert events[0].agent_id is None and events[0].workflow_id is None


@pytest.mark.asyncio(loop_scope="module")
async def test_flushing_the_same_case_twice_does_not_double_bill(world):
    execution_id = await world.record("llm_judge", "provenance_judge")
    await world.record("llm_judge", "provenance_judge", execution_id=execution_id)

    assert len(await world.events(execution_id)) == 2
    receipt = (await world.receipts(execution_id))[0]
    assert (receipt.expected_entries, receipt.persisted_events) == (2, 2)


@pytest.mark.asyncio(loop_scope="module")
async def test_a_genuine_re_execution_bills_its_new_provider_calls(world):
    first = await world.record("llm_judge")
    second = await world.record("llm_judge")

    assert first != second
    assert len(await world.events(first)) == 1
    assert len(await world.events(second)) == 1, "a retry really called the provider again"


@pytest.mark.asyncio(loop_scope="module")
async def test_judge_calls_are_priced_from_the_resolved_model(world):
    execution_id = await world.record("llm_judge")

    events = await world.events(execution_id)
    assert float(events[0].cost_usd) == pytest.approx(JUDGE_CALL_COST)


@pytest.mark.asyncio(loop_scope="module")
async def test_an_unpriced_judge_model_is_counted_without_a_fabricated_cost(world):
    execution_id = await world.record("llm_judge", model="totally-unknown-model")

    events = await world.events(execution_id)
    assert len(events) == 1 and events[0].cost_usd is None


@pytest.mark.asyncio(loop_scope="module")
async def test_capture_disabled_records_nothing(world):
    await world.set_capture(False)
    try:
        execution_id = await world.record("llm_judge", "provenance_judge")
    finally:
        await world.set_capture(True)

    assert await world.events(execution_id) == []
    assert await world.receipts(execution_id) == []


@pytest.mark.asyncio(loop_scope="module")
async def test_recorded_spend_surfaces_under_evaluations_and_its_methods(world):
    await world.record("llm_judge", "provenance_judge")

    by_source = await world.breakdown("source")
    assert by_source["evaluation"].label == "Evaluations"

    by_method = await world.breakdown("evaluation_method")
    assert {"llm_judge", "provenance_judge"} <= set(by_method)
    assert by_method["llm_judge"].label == "LLM Judge"
    assert by_method["provenance_judge"].label == "Provenance"


@pytest.mark.asyncio(loop_scope="module")
async def test_the_agents_llm_panel_excludes_its_judge_models(world):
    await world.record("llm_judge", model="judge-only-model")

    by_llm = await world.breakdown("llm")
    assert "openai · judge-only-model" not in by_llm, "judge models are not models the agent ran"
