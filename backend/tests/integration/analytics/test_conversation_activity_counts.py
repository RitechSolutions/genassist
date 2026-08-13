"""Integration tests pinning the canonical conversation-activity counts against the database"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
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
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.conversation import ConversationModel
from app.db.models.message_model import TranscriptMessageModel
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.user import UserModel
from app.db.models.user_group import UserGroupModel
from app.db.models.workflow import WorkflowModel
from app.repositories.analytics_read import AnalyticsReadRepository
from app.repositories.dashboard import DashboardRepository
from app.services.dashboard import DashboardService

PROBE_START = date(2097, 3, 1)
WINDOW_START_HOUR = 6
WINDOW_END_HOUR = 18

CONVERSATIONS = (
    ("multi_log", "a1", "finalized", 0, ((7, 0), (8, 0), (9, 0))),
    ("at_start", "a1", "in_progress", 0, ((WINDOW_START_HOUR, 0),)),
    ("at_end", "a1", "finalized", 0, ((WINDOW_END_HOUR, 0),)),
    ("silent", "a1", "finalized", 0, ()),
    ("deleted_log", "a1", "finalized", 0, ((10, 1),)),
    ("soft_deleted", "a1", "finalized", 1, ((11, 0),)),
    ("other_agent", "a2", "finalized", 0, ((12, 0),)),
)

IN_EXACT_WINDOW = {"multi_log", "at_start", "other_agent"}
IN_WHOLE_DAY = IN_EXACT_WINDOW | {"at_end"}
PER_AGENT_IN_WINDOW = {"a1": 2, "a2": 1}


@contextmanager
def caller(*, user_id=None, group_id=None, supervised=(), admin=False):
    with request_cycle_context():
        context["user_id"] = user_id
        context["group_id"] = group_id
        context["supervised_group_ids"] = list(supervised)
        context["user_roles"] = [SimpleNamespace(name="admin" if admin else "operator")]
        yield


@contextmanager
def acting_as(user_id):
    with caller(user_id=user_id, admin=True):
        yield


async def _free_day(session) -> date:
    day = PROBE_START
    for _ in range(365):
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        stmt = select(func.count()).select_from(AgentResponseLogModel).where(
            AgentResponseLogModel.logged_at >= start,
            AgentResponseLogModel.logged_at < start + timedelta(days=1),
        )
        if not (await session.execute(stmt)).scalar():
            return day
        day += timedelta(days=1)
    raise AssertionError("no collision-free window found")


class World:

    def __init__(self, maker):
        self.maker = maker
        self.group = None
        self.user = None
        self.agents: dict[str, AgentModel] = {}
        self.workflow_ids: list = []
        self.operator_ids: list = []
        self.statistics_ids: list = []
        self.conversation_ids: dict[str, object] = {}
        self.message_ids: list = []
        self.day: date = PROBE_START

    def agent_id(self, key):
        return self.agents[key].id

    def at(self, hour: int, **delta) -> datetime:
        midnight = datetime.combine(self.day, datetime.min.time(), tzinfo=timezone.utc)
        return midnight + timedelta(hours=hour, **delta)

    @property
    def window_start(self) -> datetime:
        return self.at(WINDOW_START_HOUR)

    @property
    def window_end(self) -> datetime:
        return self.at(WINDOW_END_HOUR)


@pytest_asyncio.fixture(loop_scope="module")
async def world(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    built = World(maker)

    async with maker() as session:
        built.day = await _free_day(session)
        user_type_id = (await session.execute(select(UserModel.user_type_id).limit(1))).scalar_one()

        built.group = UserGroupModel(id=uuid4(), name=f"convcount-{uuid4().hex[:8]}", is_deleted=0)
        session.add(built.group)
        suffix = uuid4().hex[:12]
        built.user = UserModel(
            id=uuid4(),
            username=f"convcount-{suffix}",
            email=f"convcount-{suffix}@example.test",
            hashed_password="x",
            user_type_id=user_type_id,
            is_active=1,
            group_id=built.group.id,
            is_deleted=0,
        )
        session.add(built.user)
        await session.flush()

        for agent_key in ("a1", "a2"):
            with acting_as(built.user.id):
                statistics = OperatorStatisticsModel(id=uuid4(), is_deleted=0)
                session.add(statistics)
                built.statistics_ids.append(statistics.id)
                operator = OperatorModel(
                    id=uuid4(),
                    first_name="Conv",
                    last_name=agent_key,
                    statistics_id=statistics.id,
                    is_active=1,
                    user_id=built.user.id,
                    is_deleted=0,
                )
                session.add(operator)
                built.operator_ids.append(operator.id)
                workflow = WorkflowModel(
                    id=uuid4(),
                    name=f"convcount-{agent_key}",
                    version="1",
                    nodes=[],
                    edges=[],
                    user_id=built.user.id,
                    is_deleted=0,
                )
                session.add(workflow)
                built.workflow_ids.append(workflow.id)
                agent = AgentModel(
                    id=uuid4(),
                    name=f"convcount-{agent_key}",
                    is_active=1,
                    operator_id=operator.id,
                    welcome_message="Welcome",
                    workflow_id=workflow.id,
                    is_deleted=0,
                )
                built.agents[agent_key] = agent
                session.add(agent)
                await session.flush()

        for key, agent_key, status, conversation_deleted, logs in CONVERSATIONS:
            conversation_id = uuid4()
            built.conversation_ids[key] = conversation_id
            session.add(
                ConversationModel(
                    id=conversation_id,
                    operator_id=built.agents[agent_key].operator_id,
                    group_id=built.group.id,
                    conversation_type="chat",
                    conversation_date=built.at(12),
                    status=status,
                    is_deleted=conversation_deleted,
                )
            )
            await session.flush()

            for index, (hour, log_deleted) in enumerate(logs):
                message_id = uuid4()
                built.message_ids.append(message_id)
                session.add(
                    TranscriptMessageModel(
                        id=message_id,
                        conversation_id=conversation_id,
                        start_time=float(index),
                        end_time=float(index + 1),
                        speaker="agent",
                        text=f"convcount {key} {index}",
                        type="text",
                        sequence_number=index + 1,
                        is_deleted=0,
                    )
                )
                await session.flush()
                session.add(
                    AgentResponseLogModel(
                        id=uuid4(),
                        transcript_message_id=message_id,
                        conversation_id=conversation_id,
                        raw_response="{}",
                        logged_at=built.at(hour),
                        is_deleted=log_deleted,
                    )
                )
        await session.commit()

    try:
        yield built
    finally:
        conversation_ids = list(built.conversation_ids.values())
        agent_ids = [a.id for a in built.agents.values()]
        async with maker() as session:
            await session.execute(
                delete(AgentResponseLogModel).where(AgentResponseLogModel.conversation_id.in_(conversation_ids))
            )
            await session.execute(
                delete(TranscriptMessageModel).where(TranscriptMessageModel.id.in_(built.message_ids))
            )
            await session.execute(delete(ConversationModel).where(ConversationModel.id.in_(conversation_ids)))
            await session.execute(delete(AgentModel).where(AgentModel.id.in_(agent_ids)))
            await session.execute(delete(OperatorModel).where(OperatorModel.id.in_(built.operator_ids)))
            await session.execute(
                delete(OperatorStatisticsModel).where(OperatorStatisticsModel.id.in_(built.statistics_ids))
            )
            await session.execute(delete(WorkflowModel).where(WorkflowModel.id.in_(built.workflow_ids)))
            await session.execute(delete(UserModel).where(UserModel.id == built.user.id))
            await session.execute(delete(UserGroupModel).where(UserGroupModel.id == built.group.id))
            await session.commit()
        await engine.dispose()


async def _counts(world, **kwargs) -> dict:
    async with world.maker() as session:
        with caller(user_id=uuid4(), admin=True):
            rows = await AnalyticsReadRepository(session).get_conversation_status_counts(**kwargs)
    return rows[0]


@pytest.mark.asyncio(loop_scope="module")
async def test_repeated_logs_count_their_conversation_once(world):
    row = await _counts(
        world,
        activity_from_datetime=world.window_start,
        activity_to_datetime=world.window_end,
    )
    assert row["total_unique_conversations"] == len(IN_EXACT_WINDOW)
    assert row["total_finalized_conversations"] == 2
    assert row["total_in_progress_conversations"] == 1


@pytest.mark.asyncio(loop_scope="module")
async def test_exact_start_is_inclusive(world):
    row = await _counts(
        world,
        activity_from_datetime=world.at(WINDOW_START_HOUR, microseconds=1),
        activity_to_datetime=world.window_end,
    )
    assert row["total_unique_conversations"] == len(IN_EXACT_WINDOW) - 1


@pytest.mark.asyncio(loop_scope="module")
async def test_exact_end_is_exclusive(world):
    row = await _counts(
        world,
        activity_from_datetime=world.window_start,
        activity_to_datetime=world.at(WINDOW_END_HOUR, microseconds=1),
    )
    assert row["total_unique_conversations"] == len(IN_EXACT_WINDOW) + 1


@pytest.mark.asyncio(loop_scope="module")
async def test_a_conversation_without_response_activity_is_excluded(world):
    row = await _counts(world, from_date=world.day, to_date=world.day)
    assert row["total_unique_conversations"] == len(IN_WHOLE_DAY)


@pytest.mark.asyncio(loop_scope="module")
async def test_deleted_response_logs_do_not_count(world):
    row = await _counts(
        world,
        activity_from_datetime=world.at(10),
        activity_to_datetime=world.at(10, minutes=1),
    )
    assert row["total_unique_conversations"] == 0


@pytest.mark.asyncio(loop_scope="module")
async def test_soft_deleted_conversations_drop_out_via_the_global_filter(world):
    row = await _counts(
        world,
        activity_from_datetime=world.at(11),
        activity_to_datetime=world.at(11, minutes=1),
    )
    assert row["total_unique_conversations"] == 0


@pytest.mark.asyncio(loop_scope="module")
async def test_per_agent_rows_sum_to_the_summary_total(world):
    async with world.maker() as session:
        repo = AnalyticsReadRepository(session)
        bounds = {
            "activity_from_datetime": world.window_start,
            "activity_to_datetime": world.window_end,
        }
        with caller(user_id=uuid4(), admin=True):
            grouped = await repo.get_conversation_status_counts(group_by_agent=True, **bounds)
            ungrouped = await repo.get_conversation_status_counts(**bounds)

    by_agent = {row["agent_id"]: row["unique_conversations"] for row in grouped}
    assert by_agent == {world.agent_id(key): count for key, count in PER_AGENT_IN_WINDOW.items()}
    assert sum(by_agent.values()) == ungrouped[0]["total_unique_conversations"]


@pytest.mark.asyncio(loop_scope="module")
async def test_dashboard_and_agent_performance_agree_for_the_same_caller_and_interval(world):
    bounds = {
        "activity_from_datetime": world.window_start,
        "activity_to_datetime": world.window_end,
    }
    for principal in (
        {"user_id": uuid4(), "admin": True},
        {"user_id": world.user.id, "group_id": world.group.id},
    ):
        async with world.maker() as session:
            with caller(**principal):
                dashboard = DashboardService(DashboardRepository(session), AnalyticsReadRepository(session))
                summary = await dashboard.get_summary_stats(world.window_start, world.window_end, exact=True)
                performance = await AnalyticsReadRepository(session).get_agent_stats_summary(
                    from_date=world.day, to_date=world.day, **bounds
                )

        assert summary.conversations == performance["total_unique_conversations"] == len(IN_EXACT_WINDOW)
        assert summary.workflow_runs == summary.conversations
