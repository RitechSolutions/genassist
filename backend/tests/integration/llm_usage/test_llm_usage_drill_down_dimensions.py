"""Integration tests for the agent-scoped LLM and evaluation-method breakdowns"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.agent import AgentModel
from app.db.models.llm_usage import LlmUsageEventModel
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.user import UserModel
from app.db.models.workflow import WorkflowModel
from app.repositories.agent import AgentRepository
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_read import LlmUsageReadService

_EVENTS = (
    ("workflow", None, "openai", "gpt-4o", "0.10"),
    ("workflow", None, "openai", "gpt-4o", "0.05"),
    ("workflow", None, "anthropic", "claude-sonnet", "0.02"),
    ("workflow", None, None, None, None),
    ("llm_analyst", None, "openai", "gpt-4o-mini", "0.30"),
    ("evaluation", "llm_judge", "openai", "gpt-4o", "0.01"),
    ("evaluation", "provenance_judge", "openai", "gpt-4o", "0.02"),
)


class World:

    def __init__(self, maker, agent_id, execution_ids):
        self.maker = maker
        self.agent_id = agent_id
        self.execution_ids = execution_ids

    async def breakdown(self, dimension: str, *, agent_id=True) -> dict:
        params = LlmUsageQueryParams(agent_id=self.agent_id if agent_id else None)
        async with self.maker() as session:
            service = LlmUsageReadService(
                LlmUsageReadRepository(session), AgentRepository(session), WorkflowRepository(session)
            )
            response = await service.get_breakdown(params, dimension)
        return {item.key: item for item in response.items}


def _event(agent_id, source_type, purpose, provider, model, cost) -> LlmUsageEventModel:
    return LlmUsageEventModel(
        id=uuid4(),
        execution_id=f"drilldown-{uuid4()}",
        call_index=0,
        source_type=source_type,
        source="test_suite" if source_type == "evaluation" else "chat",
        purpose=purpose,
        agent_id=agent_id,
        provider_key=provider,
        model_key=model,
        input_tokens=10,
        prompt_tokens=10,
        output_tokens=5,
        total_tokens=15,
        cost_usd=None if cost is None else Decimal(cost),
        pricing_status="unpriced" if cost is None else "configured",
        occurred_at=datetime.now(timezone.utc),
        is_deleted=0,
    )


@pytest_asyncio.fixture(loop_scope="module")
async def world(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        user_id = (await session.execute(select(UserModel.id).limit(1))).scalar_one()
        workflow = WorkflowModel(id=uuid4(), name="drilldown", version="1", nodes=[], edges=[], is_deleted=0)
        statistics = OperatorStatisticsModel(id=uuid4(), is_deleted=0)
        session.add_all([workflow, statistics])
        operator = OperatorModel(
            id=uuid4(),
            first_name="Drilldown",
            last_name="Fixture",
            statistics_id=statistics.id,
            is_active=1,
            user_id=user_id,
            is_deleted=0,
        )
        session.add(operator)
        agent = AgentModel(
            id=uuid4(),
            name="drilldown-agent",
            is_active=1,
            operator_id=operator.id,
            welcome_message="Welcome",
            workflow_id=workflow.id,
            is_deleted=0,
        )
        session.add(agent)
        await session.flush()
        events = [_event(agent.id, *spec) for spec in _EVENTS]
        session.add_all(events)
        await session.commit()
        execution_ids = [e.execution_id for e in events]

    try:
        yield World(maker, agent.id, execution_ids)
    finally:
        async with maker() as session:
            await session.execute(
                delete(LlmUsageEventModel).where(LlmUsageEventModel.execution_id.in_(execution_ids))
            )
            await session.execute(delete(AgentModel).where(AgentModel.id == agent.id))
            await session.execute(delete(OperatorModel).where(OperatorModel.id == operator.id))
            await session.execute(delete(OperatorStatisticsModel).where(OperatorStatisticsModel.id == statistics.id))
            await session.execute(delete(WorkflowModel).where(WorkflowModel.id == workflow.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_llm_dimension_groups_the_provider_model_pair(world):
    rows = await world.breakdown("llm")
    assert float(rows["openai · gpt-4o"].cost_usd) == pytest.approx(0.15)
    assert rows["openai · gpt-4o"].calls == 2
    assert float(rows["anthropic · claude-sonnet"].cost_usd) == pytest.approx(0.02)


@pytest.mark.asyncio(loop_scope="module")
async def test_llm_dimension_excludes_analyst_and_evaluation_rows(world):
    rows = await world.breakdown("llm")
    assert "openai · gpt-4o-mini" not in rows, "analyst models are not models the agent ran"
    assert rows["openai · gpt-4o"].calls == 2, "judge calls on the same pair must stay out"


@pytest.mark.asyncio(loop_scope="module")
async def test_llm_dimension_labels_missing_keys_as_unknown(world):
    rows = await world.breakdown("llm")
    assert rows["unknown · unknown"].calls == 1
    assert rows["unknown · unknown"].cost_is_partial is True


@pytest.mark.asyncio(loop_scope="module")
async def test_evaluation_method_dimension_splits_the_two_judges(world):
    rows = await world.breakdown("evaluation_method")
    assert {k: r.label for k, r in rows.items()} == {
        "llm_judge": "LLM Judge",
        "provenance_judge": "Provenance",
    }
    assert float(rows["llm_judge"].cost_usd) == pytest.approx(0.01)
    assert float(rows["provenance_judge"].cost_usd) == pytest.approx(0.02)


@pytest.mark.asyncio(loop_scope="module")
async def test_source_dimension_lists_evaluations_beside_workflow_and_analyst(world):
    rows = await world.breakdown("source")
    assert rows["workflow"].label == "Workflow"
    assert rows["llm_analyst"].label == "Conversation Analyst"
    assert rows["evaluation"].label == "Evaluations"
    assert float(rows["evaluation"].cost_usd) == pytest.approx(0.03)
