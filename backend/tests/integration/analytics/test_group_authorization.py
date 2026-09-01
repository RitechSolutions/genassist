"""Integration tests for cross-group authorization of the analytics and LLM-usage reads"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette_context import context, request_cycle_context

from app.core.config.settings import settings
from app.db.models.agent import AgentModel
from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.conversation import ConversationModel
from app.db.models.llm_usage import LlmUsageEventModel
from app.db.models.message_model import TranscriptMessageModel
from app.db.models.node_execution_daily_stats import NodeExecutionDailyStatsModel
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.user import UserModel
from app.db.models.user_group import UserGroupModel
from app.db.models.workflow import WorkflowModel
from app.repositories.agent import AgentRepository
from app.repositories.analytics_read import AnalyticsReadRepository
from app.repositories.dashboard import DashboardRepository
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_read import LlmUsageReadService

COST = {"a1": Decimal("0.11"), "a2": Decimal("0.22"), "a1_deleted": Decimal("0.33"), "unattributed": Decimal("0.44")}
TOTAL_COST = float(sum(COST.values()))

# Distinct per agent so a weighted average differs by scope: (ms, executions).
RESPONSE = {"a1": (100.0, 10), "a2": (500.0, 30), "a1_deleted": (900.0, 5)}
BLENDED_MS = int(sum(ms * n for ms, n in RESPONSE.values()) / sum(n for _, n in RESPONSE.values()))

NODE_TYPE = {"a1": "authzNodeA", "a2": "authzNodeB"}
ATTRIBUTE_KEY = {"a1": "authz_attr_a", "a2": "authz_attr_b"}
PROVIDER = {"a1": "authzprov-a", "a2": "authzprov-b", "a1_deleted": "authzprov-del", "unattributed": "authzprov-none"}
MODEL = {k: f"{v}-model" for k, v in PROVIDER.items()}

PROBE_START = date(2099, 1, 15)


@contextmanager
def caller(*, user_id=None, group_id=None, supervised=(), admin=False):
    """Request context for one principal — the four keys ``auth()`` populates."""
    with request_cycle_context():
        context["user_id"] = user_id
        context["group_id"] = group_id
        context["supervised_group_ids"] = list(supervised)
        context["user_roles"] = [SimpleNamespace(name="admin" if admin else "operator")]
        yield


@contextmanager
def acting_as(user_id):
    """Own the rows flushed inside this block.

    The audit ``before_flush`` listener overwrites ``created_by`` with the request
    context's user on every insert, so a constructor-set ``created_by`` is discarded.
    Admin roles keep the group-scope listener off the fixture's own reads.
    """
    with caller(user_id=user_id, admin=True):
        yield


def _workflow(name: str, user_id, attribute_key: str) -> WorkflowModel:
    nodes = [
        {
            "id": "chat-input",
            "type": "chatInputNode",
            "data": {"inputSchema": {attribute_key: {"useInFilter": True}}},
        }
    ]
    return WorkflowModel(id=uuid4(), name=name, version="1", nodes=nodes, edges=[], user_id=user_id, is_deleted=0)


def _event(agent_id, *, provider: str, occurred_at: datetime, cost: Decimal) -> LlmUsageEventModel:
    return LlmUsageEventModel(
        id=uuid4(),
        execution_id=f"authz-{uuid4()}",
        call_index=0,
        source_type="workflow",
        source="chat",
        agent_id=agent_id,
        provider_key=provider,
        model_key=f"{provider}-model",
        input_tokens=100,
        prompt_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost_usd=cost,
        pricing_status="configured",
        occurred_at=occurred_at,
        is_deleted=0,
    )


async def _free_window(session) -> date:
    """First far-future day with no rows in any table this suite asserts totals over.

    The local database keeps seeded and prior-run rows, and admin reads are tenant-wide,
    so every total below is only deterministic inside an otherwise empty day.
    """
    day = PROBE_START
    for _ in range(365):
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        counts = [
            select(func.count()).select_from(LlmUsageEventModel).where(
                LlmUsageEventModel.occurred_at >= start, LlmUsageEventModel.occurred_at < end
            ),
            select(func.count()).select_from(AgentExecutionDailyStatsModel).where(
                AgentExecutionDailyStatsModel.stat_date == day
            ),
            select(func.count()).select_from(NodeExecutionDailyStatsModel).where(
                NodeExecutionDailyStatsModel.stat_date == day
            ),
            select(func.count()).select_from(AgentResponseLogModel).where(
                AgentResponseLogModel.logged_at >= start, AgentResponseLogModel.logged_at < end
            ),
        ]
        occupied = False
        for stmt in counts:
            if (await session.execute(stmt)).scalar():
                occupied = True
                break
        if not occupied:
            return day
        day += timedelta(days=1)
    raise AssertionError("no collision-free window found")


class World:

    def __init__(self, maker):
        self.maker = maker
        self.groups: dict[str, UserGroupModel] = {}
        self.users: dict[str, UserModel] = {}
        self.agents: dict[str, AgentModel] = {}
        self.workflows: dict[str, WorkflowModel] = {}
        self.operator_ids: list = []
        self.statistics_ids: list = []
        self.event_ids: list = []
        self.conversation_id = None
        self.message_id = None
        self.response_log_id = None
        self.day: date = PROBE_START

    def agent_id(self, key):
        return self.agents[key].id

    def group_id(self, key):
        return self.groups[key].id

    def user_id(self, key):
        return self.users[key].id

    @property
    def window(self) -> tuple[datetime, datetime]:
        start = datetime.combine(self.day, datetime.min.time(), tzinfo=timezone.utc)
        return start, start

    @property
    def params(self) -> LlmUsageQueryParams:
        return LlmUsageQueryParams(from_date=self.day, to_date=self.day)


@pytest_asyncio.fixture(loop_scope="module")
async def world(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    built = World(maker)

    async with maker() as session:
        built.day = await _free_window(session)
        noon = datetime.combine(built.day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
        user_type_id = (await session.execute(select(UserModel.user_type_id).limit(1))).scalar_one()

        for key in ("g1", "g2"):
            built.groups[key] = UserGroupModel(id=uuid4(), name=f"authz-{key}-{uuid4().hex[:8]}", is_deleted=0)
        session.add_all(built.groups.values())

        for user_key, group_key in (("u1", "g1"), ("u2", "g2")):
            suffix = uuid4().hex[:12]
            built.users[user_key] = UserModel(
                id=uuid4(),
                username=f"authz-{user_key}-{suffix}",
                email=f"authz-{user_key}-{suffix}@example.test",
                hashed_password="x",
                user_type_id=user_type_id,
                is_active=1,
                group_id=built.groups[group_key].id,
                is_deleted=0,
            )
        session.add_all(built.users.values())
        await session.flush()

        # a1_deleted needs its own operator: AgentModel.operator_id is unique.
        for agent_key, user_key, is_deleted in (("a1", "u1", 0), ("a2", "u2", 0), ("a1_deleted", "u1", 1)):
            user_id = built.users[user_key].id
            with acting_as(user_id):
                statistics = OperatorStatisticsModel(id=uuid4(), is_deleted=0)
                session.add(statistics)
                built.statistics_ids.append(statistics.id)
                operator = OperatorModel(
                    id=uuid4(),
                    first_name="Authz",
                    last_name=agent_key,
                    statistics_id=statistics.id,
                    is_active=1,
                    user_id=user_id,
                    is_deleted=0,
                )
                session.add(operator)
                built.operator_ids.append(operator.id)
                workflow = _workflow(
                    f"authz-{agent_key}", user_id, ATTRIBUTE_KEY.get(agent_key, f"authz_attr_{agent_key}")
                )
                built.workflows[agent_key] = workflow
                session.add(workflow)
                agent = AgentModel(
                    id=uuid4(),
                    name=f"authz-{agent_key}",
                    is_active=1,
                    operator_id=operator.id,
                    welcome_message="Welcome",
                    workflow_id=workflow.id,
                    is_deleted=is_deleted,
                )
                built.agents[agent_key] = agent
                session.add(agent)
                await session.flush()

        for agent_key, (avg_ms, executions) in RESPONSE.items():
            session.add(
                AgentExecutionDailyStatsModel(
                    id=uuid4(),
                    agent_id=built.agent_id(agent_key),
                    stat_date=built.day,
                    execution_count=executions,
                    success_count=executions,
                    error_count=0,
                    avg_response_ms=avg_ms,
                    avg_success_rate=100.0,
                    last_aggregated_at=noon,
                    is_deleted=0,
                )
            )
        for agent_key, node_type in NODE_TYPE.items():
            session.add(
                NodeExecutionDailyStatsModel(
                    id=uuid4(),
                    agent_id=built.agent_id(agent_key),
                    node_type=node_type,
                    stat_date=built.day,
                    execution_count=RESPONSE[agent_key][1],
                    success_count=RESPONSE[agent_key][1],
                    failure_count=0,
                    total_execution_ms=1000.0,
                    is_deleted=0,
                )
            )

        for key, cost in COST.items():
            agent_id = None if key == "unattributed" else built.agent_id(key)
            event = _event(agent_id, provider=PROVIDER[key], occurred_at=noon, cost=cost)
            built.event_ids.append(event.id)
            session.add(event)

        # Group B conversation chain — the foreign-conversation regression only.
        built.conversation_id = uuid4()
        session.add(
            ConversationModel(
                id=built.conversation_id,
                operator_id=built.agents["a2"].operator_id,
                group_id=built.group_id("g2"),
                conversation_type="chat",
                conversation_date=noon,
                status="finalized",
                is_deleted=0,
            )
        )
        await session.flush()
        built.message_id = uuid4()
        session.add(
            TranscriptMessageModel(
                id=built.message_id,
                conversation_id=built.conversation_id,
                start_time=0.0,
                end_time=1.0,
                speaker="agent",
                text="authz fixture message",
                type="text",
                sequence_number=1,
                is_deleted=0,
            )
        )
        await session.flush()
        built.response_log_id = uuid4()
        session.add(
            AgentResponseLogModel(
                id=built.response_log_id,
                transcript_message_id=built.message_id,
                conversation_id=built.conversation_id,
                raw_response="{}",
                logged_at=noon,
                is_deleted=0,
            )
        )
        await session.commit()

    try:
        yield built
    finally:
        agent_ids = [a.id for a in built.agents.values()]
        async with maker() as session:
            await session.execute(delete(LlmUsageEventModel).where(LlmUsageEventModel.id.in_(built.event_ids)))
            await session.execute(delete(AgentResponseLogModel).where(AgentResponseLogModel.id == built.response_log_id))
            await session.execute(delete(TranscriptMessageModel).where(TranscriptMessageModel.id == built.message_id))
            await session.execute(delete(ConversationModel).where(ConversationModel.id == built.conversation_id))
            await session.execute(
                delete(AgentExecutionDailyStatsModel).where(AgentExecutionDailyStatsModel.agent_id.in_(agent_ids))
            )
            await session.execute(
                delete(NodeExecutionDailyStatsModel).where(NodeExecutionDailyStatsModel.agent_id.in_(agent_ids))
            )
            await session.execute(delete(AgentModel).where(AgentModel.id.in_(agent_ids)))
            await session.execute(delete(OperatorModel).where(OperatorModel.id.in_(built.operator_ids)))
            await session.execute(
                delete(OperatorStatisticsModel).where(OperatorStatisticsModel.id.in_(built.statistics_ids))
            )
            await session.execute(
                delete(WorkflowModel).where(WorkflowModel.id.in_([w.id for w in built.workflows.values()]))
            )
            await session.execute(delete(UserModel).where(UserModel.id.in_([u.id for u in built.users.values()])))
            await session.execute(delete(UserGroupModel).where(UserGroupModel.id.in_([g.id for g in built.groups.values()])))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_admin_reads_remain_tenant_wide_including_unattributed_spend(world):
    async with world.maker() as session:
        repo = LlmUsageReadRepository(session)
        with caller(user_id=uuid4(), admin=True):
            scope = await repo.resolve_scope(world.params)
            row = await repo.summary(world.params, scope)

    assert scope is None
    assert float(row["sum_cost"]) == pytest.approx(TOTAL_COST)
    assert row["total_calls"] == len(COST)


@pytest.mark.asyncio(loop_scope="module")
async def test_regular_user_sees_only_their_groups_agent_stats(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            daily = await repo.get_agent_daily_stats(from_date=world.day, to_date=world.day)
            nodes = await repo.get_node_daily_stats(from_date=world.day, to_date=world.day)
            summary = await repo.get_agent_stats_summary(from_date=world.day, to_date=world.day)

    assert [row.agent_id for row in daily] == [world.agent_id("a1")]
    assert [row.node_type for row in nodes] == [NODE_TYPE["a1"]]
    assert summary["total_executions"] == RESPONSE["a1"][1]


@pytest.mark.asyncio(loop_scope="module")
async def test_regular_user_cannot_widen_scope_with_a_foreign_group_filter(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            daily = await repo.get_agent_daily_stats(
                group_id=world.group_id("g2"), from_date=world.day, to_date=world.day
            )
            summary = await repo.get_agent_stats_summary(
                group_id=world.group_id("g2"), from_date=world.day, to_date=world.day
            )

    assert daily == []
    assert summary["total_executions"] == 0


@pytest.mark.asyncio(loop_scope="module")
async def test_foreign_group_filter_reveals_no_foreign_conversations(world):
    """Conversation counts keep their own group visibility — foreign rows stay hidden."""
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            restricted = await repo.get_agent_stats_summary(
                group_id=world.group_id("g2"), from_date=world.day, to_date=world.day
            )
        with caller(user_id=uuid4(), admin=True):
            unrestricted = await repo.get_agent_stats_summary(
                group_id=world.group_id("g2"), from_date=world.day, to_date=world.day
            )

    assert restricted["total_unique_conversations"] == 0
    assert unrestricted["total_unique_conversations"] == 1


@pytest.mark.asyncio(loop_scope="module")
async def test_foreign_agent_filter_returns_empty_rather_than_existence_info(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            rows = await repo.get_agent_daily_stats(
                agent_id=world.agent_id("a2"), from_date=world.day, to_date=world.day
            )
    assert rows == []


@pytest.mark.asyncio(loop_scope="module")
async def test_agent_and_group_mismatch_resolves_to_nothing(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            rows = await repo.get_agent_daily_stats(
                agent_id=world.agent_id("a1"),
                group_id=world.group_id("g2"),
                from_date=world.day,
                to_date=world.day,
            )
    assert rows == []


@pytest.mark.asyncio(loop_scope="module")
async def test_node_breakdown_is_denied_for_foreign_agents_and_served_for_own(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            foreign = await repo.get_node_type_breakdown(world.agent_id("a2"), world.day, world.day)
            own = await repo.get_node_type_breakdown(world.agent_id("a1"), world.day, world.day)

    assert foreign == []
    assert [row["node_type"] for row in own] == [NODE_TYPE["a1"]]


@pytest.mark.asyncio(loop_scope="module")
async def test_group_agent_dropdown_only_lists_agents_the_caller_can_see(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            foreign = await repo.get_agents_for_group(world.group_id("g2"))
            own = await repo.get_agents_for_group(world.group_id("g1"))
        with caller(user_id=uuid4(), admin=True):
            as_admin = await repo.get_agents_for_group(world.group_id("g2"))

    assert foreign == []
    assert [row["id"] for row in own] == [world.agent_id("a1")]
    assert [row["id"] for row in as_admin] == [world.agent_id("a2")]


@pytest.mark.asyncio(loop_scope="module")
async def test_supervisor_context_grants_supervised_groups_and_their_own(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(
            user_id=world.user_id("u1"),
            group_id=world.group_id("g1"),
            supervised=[world.group_id("g2")],
        ):
            rows = await repo.get_agent_daily_stats(from_date=world.day, to_date=world.day)

    assert {row.agent_id for row in rows} == {world.agent_id("a1"), world.agent_id("a2")}


@pytest.mark.asyncio(loop_scope="module")
async def test_soft_deleted_agents_are_invisible_to_non_admins(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            rows = await repo.get_agent_daily_stats(from_date=world.day, to_date=world.day)
            denied = await repo.get_agent_daily_stats(
                agent_id=world.agent_id("a1_deleted"), from_date=world.day, to_date=world.day
            )

    assert world.agent_id("a1_deleted") not in {row.agent_id for row in rows}
    assert denied == []


@pytest.mark.asyncio(loop_scope="module")
async def test_missing_context_fails_closed_for_every_scoped_read(world):
    async with world.maker() as session:
        analytics = AnalyticsReadRepository(session)
        daily = await analytics.get_agent_daily_stats(from_date=world.day, to_date=world.day)
        nodes = await analytics.get_node_daily_stats(from_date=world.day, to_date=world.day)
        breakdown = await analytics.get_node_type_breakdown(world.agent_id("a1"), world.day, world.day)
        keys = await analytics.get_custom_attribute_keys()
        summary = await analytics.get_agent_stats_summary(from_date=world.day, to_date=world.day)
        ledger_scope = await LlmUsageReadRepository(session).resolve_scope(world.params)
        dashboard_scope = await DashboardRepository(session).resolve_visible_agent_ids()

    assert (daily, nodes, breakdown, keys) == ([], [], [], [])
    assert summary["total_executions"] == 0
    assert ledger_scope == [] and dashboard_scope == []


@pytest.mark.asyncio(loop_scope="module")
async def test_custom_attribute_keys_are_limited_to_visible_workflows(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            keys = await repo.get_custom_attribute_keys()

    assert ATTRIBUTE_KEY["a1"] in keys
    assert ATTRIBUTE_KEY["a2"] not in keys


@pytest.mark.asyncio(loop_scope="module")
async def test_llm_usage_filter_options_expose_only_visible_providers_models_and_agents(world):
    async with world.maker() as session:
        service = LlmUsageReadService(
            LlmUsageReadRepository(session), AgentRepository(session), WorkflowRepository(session)
        )
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            options = await service.get_filter_options(world.params)

    assert options.providers == [PROVIDER["a1"]]
    assert options.models == [MODEL["a1"]]
    assert [a.id for a in options.agents] == [world.agent_id("a1")]


@pytest.mark.asyncio(loop_scope="module")
async def test_llm_usage_scope_excludes_foreign_and_unattributed_events(world):
    async with world.maker() as session:
        repo = LlmUsageReadRepository(session)
        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            scope = await repo.resolve_scope(world.params)
            row = await repo.summary(world.params, scope)

    assert scope == [world.agent_id("a1")]
    assert row["total_calls"] == 1
    assert float(row["sum_cost"]) == pytest.approx(float(COST["a1"]))


@pytest.mark.asyncio(loop_scope="module")
async def test_dashboard_cost_and_response_time_follow_the_visible_scope(world):
    start, end = world.window
    async with world.maker() as session:
        dashboard = DashboardRepository(session)
        service = LlmUsageReadService(
            LlmUsageReadRepository(session), AgentRepository(session), WorkflowRepository(session)
        )

        with caller(user_id=uuid4(), admin=True):
            admin_scope = await dashboard.resolve_visible_agent_ids()
            admin_cost = await dashboard.get_total_cost_usd(start, end, agent_ids=admin_scope)
            admin_ms = await dashboard.get_avg_response_time(world.day, world.day, agent_ids=admin_scope)
            admin_explorer = (await service.get_summary(world.params)).total_cost_usd

        with caller(user_id=world.user_id("u1"), group_id=world.group_id("g1")):
            user_scope = await dashboard.resolve_visible_agent_ids()
            user_cost = await dashboard.get_total_cost_usd(start, end, agent_ids=user_scope)
            user_ms = await dashboard.get_avg_response_time(world.day, world.day, agent_ids=user_scope)
            user_explorer = (await service.get_summary(world.params)).total_cost_usd

    assert admin_scope is None and user_scope == [world.agent_id("a1")]
    assert admin_cost == pytest.approx(TOTAL_COST) and admin_ms == BLENDED_MS
    assert user_cost == pytest.approx(float(COST["a1"])) and user_ms == int(RESPONSE["a1"][0])
    assert admin_explorer == pytest.approx(admin_cost)
    assert user_explorer == pytest.approx(user_cost)
