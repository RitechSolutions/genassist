"""Integration tests for the V2 analytics aggregation service path"""

import json
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import delete, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette_context import context, request_cycle_context

from app.core.config.settings import settings
from app.db.events.soft_delete import SOFT_DELETE_FLAG
from app.db.models.agent import AgentModel
from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.analytics_aggregation_state import AnalyticsAggregationStateModel
from app.db.models.conversation import ConversationModel
from app.db.models.message_model import TranscriptMessageModel
from app.db.models.node_execution_daily_stats import NodeExecutionDailyStatsModel
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.user import UserModel
from app.db.models.user_group import UserGroupModel
from app.db.models.workflow import WorkflowModel
from app.repositories.analytics_aggregation import AnalyticsAggregationRepository
from app.services.analytics_aggregation import AnalyticsAggregationService

TODAY = date(2026, 3, 12)
YESTERDAY = date(2026, 3, 11)
D1 = date(2026, 3, 10)
FAKE_NOW = datetime(2026, 3, 12, 12, 0, 0, tzinfo=timezone.utc)
OLD_STAMP = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
QUIET_START = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
QUIET_END = datetime(2026, 3, 20, 23, 59, 59, tzinfo=timezone.utc)


@contextmanager
def acting_as(user_id):
    with request_cycle_context():
        context["user_id"] = user_id
        context["group_id"] = None
        context["supervised_group_ids"] = []
        context["user_roles"] = [SimpleNamespace(name="admin")]
        yield


def _raw(agent_id) -> str:
    return json.dumps(
        {
            "agent_id": str(agent_id),
            "status": "success",
            "row_agent_response": {
                "state": {"nodeExecutionStatus": {"n1": {"type": "apiToolNode", "status": "success"}}}
            },
        }
    )


class World:
    def __init__(self, maker):
        self.maker = maker
        self.group = None
        self.user = None
        self.statistics_ids = []
        self.operator_ids = []
        self.operator_id = None
        self.workflow_id = None
        self.agent_id = None
        self.agent2_id = None
        self.conversation_ids = []
        self.message_ids = []
        self.created_state_table = False


@pytest_asyncio.fixture(loop_scope="module")
async def world(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    built = World(maker)

    async with maker() as session:
        earliest_log = (await session.execute(select(func.min(AgentResponseLogModel.logged_at)))).scalar_one_or_none()
        stat_mins = [
            (await session.execute(select(func.min(AgentExecutionDailyStatsModel.stat_date)))).scalar_one_or_none(),
            (await session.execute(select(func.min(NodeExecutionDailyStatsModel.stat_date)))).scalar_one_or_none(),
        ]
        earliest_stat = min((d for d in stat_mins if d is not None), default=None)
        changed_conversations = (
            await session.execute(
                select(func.count())
                .select_from(ConversationModel)
                .where(ConversationModel.updated_at >= QUIET_START, ConversationModel.updated_at <= QUIET_END)
                .execution_options(**{SOFT_DELETE_FLAG: True})
            )
        ).scalar_one()
    if (
        (earliest_log is not None and earliest_log <= QUIET_END)
        or (earliest_stat is not None and earliest_stat <= QUIET_END.date())
        or changed_conversations
    ):
        await engine.dispose()
        pytest.skip("local data overlaps the fixed 2026-02/03 test epoch; refusing authoritative reconciliation")

    async with engine.begin() as conn:
        has_table = await conn.run_sync(lambda c: sa_inspect(c).has_table("analytics_aggregation_state"))
        if not has_table:
            await conn.run_sync(AnalyticsAggregationStateModel.__table__.create)
            built.created_state_table = True

    async with maker() as session:
        state_snapshot = (
            await session.execute(
                select(
                    AnalyticsAggregationStateModel.id,
                    AnalyticsAggregationStateModel.state_key,
                    AnalyticsAggregationStateModel.last_incremental_run_at,
                )
            )
        ).all()

        user_type_id = (await session.execute(select(UserModel.user_type_id).limit(1))).scalar_one()
        built.group = UserGroupModel(id=uuid4(), name=f"aggv2-{uuid4().hex[:8]}", is_deleted=0)
        session.add(built.group)
        suffix = uuid4().hex[:12]
        built.user = UserModel(
            id=uuid4(),
            username=f"aggv2-{suffix}",
            email=f"aggv2-{suffix}@example.test",
            hashed_password="x",
            user_type_id=user_type_id,
            is_active=1,
            group_id=built.group.id,
            is_deleted=0,
        )
        session.add(built.user)
        await session.flush()

        with acting_as(built.user.id):
            workflow = WorkflowModel(
                id=uuid4(),
                name=f"aggv2-{suffix}",
                version="1",
                nodes=[],
                edges=[],
                user_id=built.user.id,
                is_deleted=0,
            )
            session.add(workflow)
            built.workflow_id = workflow.id
            for attr in ("agent_id", "agent2_id"):
                statistics = OperatorStatisticsModel(id=uuid4(), is_deleted=0)
                session.add(statistics)
                built.statistics_ids.append(statistics.id)
                operator = OperatorModel(
                    id=uuid4(),
                    first_name="AggV2",
                    last_name=attr,
                    statistics_id=statistics.id,
                    is_active=1,
                    user_id=built.user.id,
                    is_deleted=0,
                )
                session.add(operator)
                built.operator_ids.append(operator.id)
                agent = AgentModel(
                    id=uuid4(),
                    name=f"aggv2-{attr}-{suffix}",
                    is_active=1,
                    operator_id=operator.id,
                    welcome_message="Welcome",
                    workflow_id=workflow.id,
                    is_deleted=0,
                )
                session.add(agent)
                setattr(built, attr, agent.id)
            built.operator_id = built.operator_ids[0]
            await session.flush()
        await session.commit()

    try:
        yield built
    finally:
        async with maker() as session:
            await session.execute(delete(AgentModel).where(AgentModel.id.in_([built.agent_id, built.agent2_id])))
            await session.execute(delete(OperatorModel).where(OperatorModel.id.in_(built.operator_ids)))
            await session.execute(
                delete(OperatorStatisticsModel).where(OperatorStatisticsModel.id.in_(built.statistics_ids))
            )
            await session.execute(delete(WorkflowModel).where(WorkflowModel.id == built.workflow_id))
            await session.execute(delete(UserModel).where(UserModel.id == built.user.id))
            await session.execute(delete(UserGroupModel).where(UserGroupModel.id == built.group.id))
            await session.execute(delete(AnalyticsAggregationStateModel))
            for row in state_snapshot:
                session.add(
                    AnalyticsAggregationStateModel(
                        id=row.id, state_key=row.state_key, last_incremental_run_at=row.last_incremental_run_at
                    )
                )
            await session.commit()
        if built.created_state_table:
            async with engine.begin() as conn:
                await conn.run_sync(AnalyticsAggregationStateModel.__table__.drop)
        await engine.dispose()


@pytest_asyncio.fixture(loop_scope="module", autouse=True)
async def _clean_between_tests(world):
    yield
    async with world.maker() as session:
        if world.conversation_ids:
            await session.execute(
                delete(AgentResponseLogModel).where(AgentResponseLogModel.conversation_id.in_(world.conversation_ids))
            )
            await session.execute(
                delete(TranscriptMessageModel).where(TranscriptMessageModel.id.in_(world.message_ids))
            )
            await session.execute(delete(ConversationModel).where(ConversationModel.id.in_(world.conversation_ids)))
        agent_ids = [world.agent_id, world.agent2_id]
        await session.execute(
            delete(AgentExecutionDailyStatsModel).where(AgentExecutionDailyStatsModel.agent_id.in_(agent_ids))
        )
        await session.execute(
            delete(NodeExecutionDailyStatsModel).where(NodeExecutionDailyStatsModel.agent_id.in_(agent_ids))
        )
        await session.execute(delete(AnalyticsAggregationStateModel))
        await session.commit()
    world.conversation_ids.clear()
    world.message_ids.clear()


def _service(world, session):
    repo = AnalyticsAggregationRepository(session)
    return AnalyticsAggregationService(repo, session), repo


def _pin_db_now(repo, now):
    async def _now():
        return now

    repo.get_db_now = _now


async def _seed_conversation(world, session, *, updated_at, is_deleted=0, conversation_date=None, log_at=()):
    conversation_id = uuid4()
    world.conversation_ids.append(conversation_id)
    with acting_as(world.user.id):
        session.add(
            ConversationModel(
                id=conversation_id,
                operator_id=world.operator_id,
                group_id=world.group.id,
                conversation_type="chat",
                conversation_date=conversation_date,
                status="finalized",
                updated_at=updated_at,
                is_deleted=is_deleted,
            )
        )
        await session.flush()
        for index, logged_at in enumerate(log_at):
            message_id = uuid4()
            world.message_ids.append(message_id)
            session.add(
                TranscriptMessageModel(
                    id=message_id,
                    conversation_id=conversation_id,
                    start_time=float(index),
                    end_time=float(index + 1),
                    speaker="agent",
                    text=f"aggv2 {index}",
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
                    raw_response=_raw(world.agent_id),
                    logged_at=logged_at,
                    is_deleted=0,
                )
            )
    await session.commit()
    return conversation_id


async def _set_cursor(session, cursor):
    await session.execute(delete(AnalyticsAggregationStateModel))
    session.add(AnalyticsAggregationStateModel(state_key=1, last_incremental_run_at=cursor))
    await session.commit()


async def _get_cursor(session):
    return (await session.execute(select(AnalyticsAggregationStateModel.last_incremental_run_at))).scalar_one_or_none()


def _add_agent_phantom(session, agent_id, stat_date, **overrides):
    row = AgentExecutionDailyStatsModel(
        agent_id=agent_id,
        stat_date=stat_date,
        execution_count=overrides.pop("execution_count", 3),
        last_aggregated_at=overrides.pop("last_aggregated_at", OLD_STAMP),
        **overrides,
    )
    session.add(row)
    return row


async def _agent_row(session, agent_id, stat_date):
    return (
        await session.execute(
            select(AgentExecutionDailyStatsModel).where(
                AgentExecutionDailyStatsModel.agent_id == agent_id,
                AgentExecutionDailyStatsModel.stat_date == stat_date,
            )
        )
    ).scalar_one_or_none()


@pytest.mark.asyncio(loop_scope="module")
async def test_v1_flag_off_runs_legacy_and_swallows_dry_run_failure(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", False)
    async with world.maker() as session:
        service, repo = _service(world, session)
        watermark_calls = []
        original = repo.get_last_aggregation_timestamp

        async def spy():
            watermark_calls.append(True)
            return await original()

        repo.get_last_aggregation_timestamp = spy

        async def sql_broken_preview():
            await session.execute(text("SELECT 1 FROM analytics_agg_missing_relation"))

        repo.get_aggregation_state = sql_broken_preview

        async def no_writes(stat_date):
            return [], []

        monkeypatch.setattr(service, "_aggregate_single_date", no_writes)

        result = await service.aggregate_daily_stats()
        assert "agent_stats_upserted" in result
        assert "dates_selected" not in result, "flag off must take the legacy path, not V2"
        assert watermark_calls, "legacy path must still read the watermark on a healthy session"
        cursor_rows = (await session.execute(select(AnalyticsAggregationStateModel))).scalars().all()
        assert cursor_rows == [], "flag-off must never write the V2 cursor"


@pytest.mark.asyncio(loop_scope="module")
async def test_v2_v6_v11_changed_conversation_selects_historical_log_date(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        await _set_cursor(session, FAKE_NOW - timedelta(hours=6))
        await _seed_conversation(
            world,
            session,
            updated_at=FAKE_NOW - timedelta(hours=1),
            log_at=[datetime.combine(D1, time(10, 0), tzinfo=timezone.utc)],
        )
        _add_agent_phantom(
            session,
            world.agent2_id,
            YESTERDAY,
            total_input_tokens=1,
            last_aggregated_at=datetime.now(timezone.utc),
        )
        await session.commit()
        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats()

        row = await _agent_row(session, world.agent_id, D1)
        assert row is not None, "historical log date of the changed conversation must be rebuilt"
        assert row.execution_count == 1
        assert row.unique_conversations == 1
        assert row.finalized_conversations == 1
        assert await _get_cursor(session) == FAKE_NOW, "cursor must advance to the captured DB cutoff"


@pytest.mark.asyncio(loop_scope="module")
async def test_v3_soft_deleted_conversation_discovered_but_dropped_from_counts(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        await _set_cursor(session, FAKE_NOW - timedelta(hours=6))
        await _seed_conversation(
            world,
            session,
            updated_at=FAKE_NOW - timedelta(hours=1),
            is_deleted=1,
            log_at=[datetime.combine(D1, time(10, 0), tzinfo=timezone.utc)],
        )
        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats()

        row = await _agent_row(session, world.agent_id, D1)
        assert row is not None, "soft-deleted conversation must still select its log date"
        assert row.execution_count == 1
        assert row.unique_conversations == 0, "the rebuild must drop the soft-deleted conversation"


@pytest.mark.asyncio(loop_scope="module")
async def test_v4_v7_logless_conversation_selects_creation_date_and_heals_phantoms(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        await _set_cursor(session, FAKE_NOW - timedelta(hours=6))
        await _seed_conversation(
            world,
            session,
            updated_at=FAKE_NOW - timedelta(hours=1),
            conversation_date=datetime.combine(D1, time(9, 0), tzinfo=timezone.utc),
            log_at=(),
        )
        _add_agent_phantom(session, world.agent_id, D1)
        _add_agent_phantom(session, world.agent2_id, D1, total_input_tokens=5, total_cost_usd=0.5)
        session.add(NodeExecutionDailyStatsModel(agent_id=world.agent_id, node_type="ghostNode", stat_date=D1))
        await session.commit()

        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats()

        assert await _agent_row(session, world.agent_id, D1) is None, "cost-free phantom must be deleted"
        survivor = await _agent_row(session, world.agent2_id, D1)
        assert survivor is not None, "cost-bearing phantom must be kept"
        assert survivor.execution_count == 0
        assert survivor.total_input_tokens == 5
        assert survivor.total_cost_usd == 0.5
        assert survivor.last_aggregated_at != OLD_STAMP, "timestamps are stamped, not zeroed"
        node_rows = (
            (
                await session.execute(
                    select(NodeExecutionDailyStatsModel).where(
                        NodeExecutionDailyStatsModel.agent_id == world.agent_id,
                        NodeExecutionDailyStatsModel.stat_date == D1,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert node_rows == [], "phantom node rows must be deleted"


@pytest.mark.asyncio(loop_scope="module")
async def test_v5_sweep_seeds_minimal_without_state_and_covers_outage(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        old_day = TODAY - timedelta(days=10)
        await _seed_conversation(
            world,
            session,
            updated_at=datetime.combine(old_day, time(10, 0), tzinfo=timezone.utc),
            log_at=[datetime.combine(old_day, time(10, 0), tzinfo=timezone.utc)],
        )
        _add_agent_phantom(
            session, world.agent2_id, YESTERDAY, total_input_tokens=1, last_aggregated_at=FAKE_NOW - timedelta(hours=1)
        )
        await session.commit()

        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        result = await service.aggregate_daily_stats()
        assert result["dates_selected"] == 2, "no state row: sweep must seed yesterday+today only"
        assert await _agent_row(session, world.agent_id, old_day) is None, "history outside the window stays untouched"

        await _set_cursor(session, FAKE_NOW - timedelta(days=4))
        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        result = await service.aggregate_daily_stats()
        assert result["dates_selected"] == 5, "cursor-derived sweep must span the outage gap"
        assert await _get_cursor(session) == FAKE_NOW

        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        result = await service.aggregate_daily_stats()
        assert result["dates_selected"] == 1, "a same-day second run must add no historical dates"


@pytest.mark.asyncio(loop_scope="module")
async def test_v8_today_rebuilt_but_reconciled_only_once_past(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        await _set_cursor(session, FAKE_NOW - timedelta(hours=6))
        await _seed_conversation(
            world,
            session,
            updated_at=FAKE_NOW - timedelta(hours=1),
            log_at=[FAKE_NOW - timedelta(hours=2)],
        )
        _add_agent_phantom(session, world.agent2_id, TODAY)
        await session.commit()

        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats()
        assert (await _agent_row(session, world.agent_id, TODAY)) is not None, "today must be rebuilt"
        assert (await _agent_row(session, world.agent2_id, TODAY)) is not None, "today must NOT be reconciled"

        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW + timedelta(days=1))
        await service.aggregate_daily_stats()
        assert (await _agent_row(session, world.agent2_id, TODAY)) is None, "yesterday's phantom is reconciled away"
        assert (await _agent_row(session, world.agent_id, TODAY)) is not None, "real activity survives reconciliation"


@pytest.mark.asyncio(loop_scope="module")
async def test_v9_v10_failed_date_rolls_back_and_retry_is_idempotent(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        cursor = FAKE_NOW - timedelta(hours=54)
        await _set_cursor(session, cursor)
        await _seed_conversation(
            world,
            session,
            updated_at=datetime.combine(D1, time(8, 0), tzinfo=timezone.utc),
            log_at=[
                datetime.combine(D1, time(10, 0), tzinfo=timezone.utc),
                datetime.combine(YESTERDAY, time(10, 0), tzinfo=timezone.utc),
            ],
        )
        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        original_upsert = repo.upsert_node_daily_stats

        async def failing_upsert(stats_list):
            if any(s["stat_date"] == YESTERDAY for s in stats_list):
                raise RuntimeError("node upsert boom")
            return await original_upsert(stats_list)

        repo.upsert_node_daily_stats = failing_upsert
        with pytest.raises(RuntimeError, match="node upsert boom"):
            await service.aggregate_daily_stats()

        assert (await _agent_row(session, world.agent_id, D1)) is not None, "earlier date stays committed"
        assert (await _agent_row(session, world.agent_id, YESTERDAY)) is None, "failed date must roll back"
        assert await _get_cursor(session) == cursor, "cursor must not advance after a failure"

        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats()
        d1_row = await _agent_row(session, world.agent_id, D1)
        assert d1_row.execution_count == 1, "recomputing a committed date must not double-count"
        assert (await _agent_row(session, world.agent_id, YESTERDAY)) is not None, "retry rediscovers the failed date"
        assert await _get_cursor(session) == FAKE_NOW


@pytest.mark.asyncio(loop_scope="module")
async def test_v11_stale_cutoff_cannot_regress_cursor(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        future_cursor = FAKE_NOW + timedelta(hours=2)
        await _set_cursor(session, future_cursor)
        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats()
        assert await _get_cursor(session) == future_cursor, "GREATEST must reject the older cutoff"


@pytest.mark.asyncio(loop_scope="module")
async def test_v12_v15_backfill_heals_stats_only_phantom_dates_and_leaves_cursor(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        phantom_day = date(2026, 2, 20)
        _add_agent_phantom(session, world.agent_id, phantom_day)
        _add_agent_phantom(session, world.agent2_id, phantom_day, total_output_tokens=7)
        session.add(NodeExecutionDailyStatsModel(agent_id=world.agent_id, node_type="ghostNode", stat_date=phantom_day))
        await session.commit()

        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats(force_full=True, to_date=date(2026, 2, 25))

        assert await _agent_row(session, world.agent_id, phantom_day) is None
        survivor = await _agent_row(session, world.agent2_id, phantom_day)
        assert survivor is not None and survivor.execution_count == 0 and survivor.total_output_tokens == 7
        assert await _get_cursor(session) is None, "backfill must never write the incremental cursor"


@pytest.mark.asyncio(loop_scope="module")
async def test_v16_backfill_window_with_today_rebuilds_but_never_reconciles_it(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        await _seed_conversation(
            world,
            session,
            updated_at=FAKE_NOW - timedelta(hours=1),
            log_at=[FAKE_NOW - timedelta(hours=2)],
        )
        _add_agent_phantom(session, world.agent2_id, TODAY)
        await session.commit()

        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats(force_full=True, from_date=TODAY)

        assert (await _agent_row(session, world.agent_id, TODAY)) is not None, "today is rebuilt"
        assert (await _agent_row(session, world.agent2_id, TODAY)) is not None, "today is never reconciled"
        assert await _get_cursor(session) is None


@pytest.mark.asyncio(loop_scope="module")
async def test_soft_time_limit_during_today_rebuild_surfaces_and_blocks_cursor(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        cursor = FAKE_NOW - timedelta(hours=6)
        await _set_cursor(session, cursor)
        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)

        async def timing_out(stat_date):
            raise SoftTimeLimitExceeded()

        monkeypatch.setattr(service, "_aggregate_single_date", timing_out)
        with pytest.raises(SoftTimeLimitExceeded):
            await service.aggregate_daily_stats()
        assert await _get_cursor(session) == cursor, "a soft timeout must surface, not advance the cursor"


@pytest.mark.asyncio(loop_scope="module")
async def test_soft_time_limit_in_flag_off_preview_is_not_swallowed(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", False)
    async with world.maker() as session:
        service, repo = _service(world, session)

        async def timing_out():
            raise SoftTimeLimitExceeded()

        repo.get_db_now = timing_out
        with pytest.raises(SoftTimeLimitExceeded):
            await service.aggregate_daily_stats()


@pytest.mark.asyncio(loop_scope="module")
async def test_v13_midnight_boundary_logs_land_on_their_utc_dates(world, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", True)
    async with world.maker() as session:
        await _set_cursor(session, FAKE_NOW - timedelta(hours=6))
        await _seed_conversation(
            world,
            session,
            updated_at=FAKE_NOW - timedelta(hours=1),
            log_at=[
                datetime.combine(D1, time(23, 30), tzinfo=timezone.utc),
                datetime.combine(YESTERDAY, time(0, 30), tzinfo=timezone.utc),
            ],
        )
        service, repo = _service(world, session)
        _pin_db_now(repo, FAKE_NOW)
        await service.aggregate_daily_stats()

        for day in (D1, YESTERDAY):
            row = await _agent_row(session, world.agent_id, day)
            assert row is not None and row.execution_count == 1, f"log near midnight must land on {day} exactly"
