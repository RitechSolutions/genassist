import logging
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from injector import inject
from sqlalchemy import Date, cast, exists, func, select, tuple_, union, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.date_time_utils import utc_now
from app.db.base import generate_sequential_uuid
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.events.soft_delete import SOFT_DELETE_FLAG
from app.db.models.agent import AgentModel
from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.analytics_aggregation_state import AnalyticsAggregationStateModel
from app.db.models.conversation import ConversationModel
from app.db.models.node_execution_daily_stats import NodeExecutionDailyStatsModel

logger = logging.getLogger(__name__)

# Max rows per INSERT ... ON CONFLICT statement. Each row binds ~20 params and
# Postgres caps a statement at 65535 bind params, so keep batches well under that
# (also bounds the size of a single backfill statement at scale).
_UPSERT_BATCH_SIZE = 500

# Discovery must see soft-deleted conversations and runs without a request context.
_DISCOVERY_FLAGS = {SOFT_DELETE_FLAG: True, GROUP_SCOPE_BYPASS_FLAG: True}


def _utc_date(column):
    """Explicit-UTC day truncation; bare date() truncates in the connection TimeZone GUC."""
    return cast(func.timezone("UTC", column), Date)


class AnalyticsAggregationRepository:
    @inject
    def __init__(self, db: AsyncSession):
        self.db = db

    # ───────────── real-time incremental upserts ─────────────
    # Single-execution counterparts of the batch aggregation below. Each issues one
    # INSERT ... ON CONFLICT DO UPDATE with atomic += increments. They do NOT commit;
    # the caller owns the transaction boundary (one commit per unit of work).
    async def increment_agent_daily_stats(self, data: dict) -> None:
        """Upsert a single execution's contribution into agent_execution_daily_stats."""
        now = datetime.now(timezone.utc)
        response_ms = data["response_ms"]
        nodes = data["nodes"]

        # Compute per-execution node success rate
        node_success_rate = None
        if nodes:
            success_nodes = sum(1 for n in nodes if n["is_success"])
            node_success_rate = success_nodes / len(nodes)

        input_tokens = data.get("input_tokens")
        output_tokens = data.get("output_tokens")
        cost_usd = data.get("cost_usd") or 0.0

        row = {
            "id": generate_sequential_uuid(),
            "agent_id": data["agent_id"],
            "stat_date": data["stat_date"],
            "execution_count": 1,
            "success_count": 1 if data["is_success"] else 0,
            "error_count": 0 if data["is_success"] else 1,
            "avg_response_ms": response_ms,
            "min_response_ms": response_ms,
            "max_response_ms": response_ms,
            "total_response_ms": response_ms,
            "total_nodes_executed": data["total_nodes_executed"],
            "avg_success_rate": node_success_rate,
            "total_success_rate_sum": node_success_rate,
            "rag_used_count": 1 if data["rag_used"] else 0,
            "unique_conversations": 0,
            "finalized_conversations": 0,
            "in_progress_conversations": 0,
            "thumbs_up_count": 0,
            "thumbs_down_count": 0,
            "total_input_tokens": input_tokens or 0,
            "total_output_tokens": output_tokens or 0,
            "total_cost_usd": cost_usd,
            "last_aggregated_at": now,
            "is_deleted": 0,
            "created_at": now,
            "updated_at": now,
        }

        stmt = insert(AgentExecutionDailyStatsModel).values(row)
        tbl = AgentExecutionDailyStatsModel.__table__

        update_set = {
            "execution_count": tbl.c.execution_count + stmt.excluded.execution_count,
            "success_count": tbl.c.success_count + stmt.excluded.success_count,
            "error_count": tbl.c.error_count + stmt.excluded.error_count,
            "total_nodes_executed": tbl.c.total_nodes_executed + stmt.excluded.total_nodes_executed,
            "rag_used_count": tbl.c.rag_used_count + stmt.excluded.rag_used_count,
            "total_input_tokens": func.coalesce(tbl.c.total_input_tokens, 0) + (input_tokens or 0),
            "total_output_tokens": func.coalesce(tbl.c.total_output_tokens, 0) + (output_tokens or 0),
            "total_cost_usd": func.coalesce(tbl.c.total_cost_usd, 0.0) + cost_usd,
            "last_aggregated_at": stmt.excluded.last_aggregated_at,
            "is_deleted": stmt.excluded.is_deleted,
            "updated_at": stmt.excluded.updated_at,
        }

        if response_ms is not None:
            update_set["total_response_ms"] = (
                func.coalesce(tbl.c.total_response_ms, 0.0) + response_ms
            )
            update_set["avg_response_ms"] = (
                (func.coalesce(tbl.c.total_response_ms, 0.0) + response_ms)
                / (tbl.c.execution_count + 1)
            )
            update_set["min_response_ms"] = func.least(
                func.coalesce(tbl.c.min_response_ms, response_ms), response_ms
            )
            update_set["max_response_ms"] = func.greatest(
                func.coalesce(tbl.c.max_response_ms, response_ms), response_ms
            )

        if node_success_rate is not None:
            update_set["total_success_rate_sum"] = (
                func.coalesce(tbl.c.total_success_rate_sum, 0.0) + node_success_rate
            )
            update_set["avg_success_rate"] = (
                (func.coalesce(tbl.c.total_success_rate_sum, 0.0) + node_success_rate)
                / (tbl.c.execution_count + 1)
            )

        stmt = stmt.on_conflict_do_update(
            constraint="uq_agent_execution_daily_stats_agent_date",
            set_=update_set,
        )
        await self.db.execute(stmt)

    async def increment_node_daily_stats(self, data: dict) -> None:
        """Upsert each node's contribution into node_execution_daily_stats."""
        now = datetime.now(timezone.utc)

        for node in data["nodes"]:
            exec_ms = node["execution_ms"]

            row = {
                "id": generate_sequential_uuid(),
                "agent_id": data["agent_id"],
                "node_type": node["type"],
                "stat_date": data["stat_date"],
                "execution_count": 1,
                "success_count": 1 if node["is_success"] else 0,
                "failure_count": 0 if node["is_success"] else 1,
                "avg_execution_ms": exec_ms,
                "min_execution_ms": exec_ms,
                "max_execution_ms": exec_ms,
                "total_execution_ms": exec_ms,
                "is_deleted": 0,
                "created_at": now,
                "updated_at": now,
            }

            stmt = insert(NodeExecutionDailyStatsModel).values(row)
            tbl = NodeExecutionDailyStatsModel.__table__

            update_set = {
                "execution_count": tbl.c.execution_count + stmt.excluded.execution_count,
                "success_count": tbl.c.success_count + stmt.excluded.success_count,
                "failure_count": tbl.c.failure_count + stmt.excluded.failure_count,
                "is_deleted": stmt.excluded.is_deleted,
                "updated_at": stmt.excluded.updated_at,
            }

            if exec_ms is not None:
                update_set["total_execution_ms"] = (
                    func.coalesce(tbl.c.total_execution_ms, 0.0) + exec_ms
                )
                update_set["avg_execution_ms"] = (
                    (func.coalesce(tbl.c.total_execution_ms, 0.0) + exec_ms)
                    / (tbl.c.execution_count + 1)
                )
                update_set["min_execution_ms"] = func.least(
                    func.coalesce(tbl.c.min_execution_ms, exec_ms), exec_ms
                )
                update_set["max_execution_ms"] = func.greatest(
                    func.coalesce(tbl.c.max_execution_ms, exec_ms), exec_ms
                )

            stmt = stmt.on_conflict_do_update(
                constraint="uq_node_execution_daily_stats_agent_node_date",
                set_=update_set,
            )
            await self.db.execute(stmt)

    async def increment_conversation_counts(self, agent_id: UUID, event: str) -> None:
        """Increment conversation counters on agent_execution_daily_stats.

        event: "start"    → unique_conversations += 1, in_progress_conversations += 1
        event: "finalize" → finalized_conversations += 1, in_progress_conversations -= 1
        """
        now = datetime.now(timezone.utc)
        stat_date = now.date()

        row = {
            "id": generate_sequential_uuid(),
            "agent_id": agent_id,
            "stat_date": stat_date,
            "execution_count": 0,
            "success_count": 0,
            "error_count": 0,
            "total_nodes_executed": 0,
            "avg_success_rate": None,
            "rag_used_count": 0,
            "unique_conversations": 1 if event == "start" else 0,
            "finalized_conversations": 1 if event == "finalize" else 0,
            "in_progress_conversations": 1 if event == "start" else 0,
            "thumbs_up_count": 0,
            "thumbs_down_count": 0,
            "last_aggregated_at": now,
            "is_deleted": 0,
            "created_at": now,
            "updated_at": now,
        }

        stmt = insert(AgentExecutionDailyStatsModel).values(row)
        tbl = AgentExecutionDailyStatsModel.__table__

        if event == "start":
            update_set = {
                "unique_conversations": tbl.c.unique_conversations + 1,
                "in_progress_conversations": tbl.c.in_progress_conversations + 1,
                "is_deleted": stmt.excluded.is_deleted,
                "updated_at": stmt.excluded.updated_at,
            }
        else:  # finalize
            update_set = {
                "finalized_conversations": tbl.c.finalized_conversations + 1,
                "in_progress_conversations": func.greatest(
                    tbl.c.in_progress_conversations - 1, 0
                ),
                "is_deleted": stmt.excluded.is_deleted,
                "updated_at": stmt.excluded.updated_at,
            }

        stmt = stmt.on_conflict_do_update(
            constraint="uq_agent_execution_daily_stats_agent_date",
            set_=update_set,
        )
        await self.db.execute(stmt)

    async def get_agent_id_for_conversation(self, conversation_id: UUID) -> UUID | None:
        """Look up the agent_id for a conversation via its operator_id."""
        result = await self.db.execute(
            select(ConversationModel.operator_id).where(
                ConversationModel.id == conversation_id
            )
        )
        operator_id = result.scalar_one_or_none()
        if not operator_id:
            return None

        result = await self.db.execute(
            select(AgentModel.id).where(AgentModel.operator_id == operator_id)
        )
        return result.scalar_one_or_none()

    async def get_conversation_agent_map(self, stat_date: date) -> dict[UUID, UUID]:
        """Conversation → agent mapping for conversations with logs (rebuild fallback)."""
        start_of_day = datetime.combine(stat_date, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(stat_date, time.max, tzinfo=timezone.utc)
        stmt = (
            select(AgentResponseLogModel.conversation_id, AgentModel.id)
            .join(ConversationModel, ConversationModel.id == AgentResponseLogModel.conversation_id)
            .join(AgentModel, AgentModel.operator_id == ConversationModel.operator_id)
            .where(
                AgentResponseLogModel.logged_at >= start_of_day,
                AgentResponseLogModel.logged_at <= end_of_day,
                AgentResponseLogModel.is_deleted == 0,
            )
            .distinct()
            .execution_options(**_DISCOVERY_FLAGS)
        )
        result = await self.db.execute(stmt)
        return {conversation_id: agent_id for conversation_id, agent_id in result.all()}

    async def increment_thumbs(self, agent_id: UUID, is_thumbs_up: bool) -> None:
        """Increment thumbs_up_count or thumbs_down_count on agent_execution_daily_stats."""
        now = datetime.now(timezone.utc)
        stat_date = now.date()

        row = {
            "id": generate_sequential_uuid(),
            "agent_id": agent_id,
            "stat_date": stat_date,
            "execution_count": 0,
            "success_count": 0,
            "error_count": 0,
            "total_nodes_executed": 0,
            "avg_success_rate": None,
            "rag_used_count": 0,
            "unique_conversations": 0,
            "finalized_conversations": 0,
            "in_progress_conversations": 0,
            "thumbs_up_count": 1 if is_thumbs_up else 0,
            "thumbs_down_count": 0 if is_thumbs_up else 1,
            "last_aggregated_at": now,
            "is_deleted": 0,
            "created_at": now,
            "updated_at": now,
        }

        stmt = insert(AgentExecutionDailyStatsModel).values(row)
        tbl = AgentExecutionDailyStatsModel.__table__

        if is_thumbs_up:
            update_set = {
                "thumbs_up_count": tbl.c.thumbs_up_count + 1,
                "is_deleted": stmt.excluded.is_deleted,
                "updated_at": stmt.excluded.updated_at,
            }
        else:
            update_set = {
                "thumbs_down_count": tbl.c.thumbs_down_count + 1,
                "is_deleted": stmt.excluded.is_deleted,
                "updated_at": stmt.excluded.updated_at,
            }

        stmt = stmt.on_conflict_do_update(
            constraint="uq_agent_execution_daily_stats_agent_date",
            set_=update_set,
        )
        await self.db.execute(stmt)

    async def get_last_aggregation_timestamp(self) -> datetime | None:
        """Return the latest last_aggregated_at across all agent daily stats rows."""
        stmt = select(func.max(AgentExecutionDailyStatsModel.last_aggregated_at))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_earliest_log_timestamp(self) -> datetime | None:
        """Return the earliest logged_at across all agent response logs."""
        stmt = select(func.min(AgentResponseLogModel.logged_at))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_response_logs_since(
        self, since: datetime, until: datetime, *, limit: int = 1000, offset: int = 0
    ) -> list[AgentResponseLogModel]:
        """Fetch a batch of agent response logs within [since, until] that are not soft-deleted."""
        stmt = (
            select(AgentResponseLogModel)
            .where(
                AgentResponseLogModel.logged_at >= since,
                AgentResponseLogModel.logged_at <= until,
                AgentResponseLogModel.is_deleted == 0,
            )
            .order_by(AgentResponseLogModel.logged_at, AgentResponseLogModel.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_affected_dates_since(self, since: datetime, until: datetime) -> list[date]:
        """Return distinct UTC dates that have logs in the given time range."""
        log_day = _utc_date(AgentResponseLogModel.logged_at)
        stmt = (
            select(func.distinct(log_day))
            .where(
                AgentResponseLogModel.logged_at >= since,
                AgentResponseLogModel.logged_at <= until,
                AgentResponseLogModel.is_deleted == 0,
            )
            .order_by(log_day)
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_response_logs_for_date(
        self, stat_date: date, *, limit: int = 10000, offset: int = 0
    ) -> list[AgentResponseLogModel]:
        """Fetch ALL agent response logs for a specific date."""
        start_of_day = datetime.combine(stat_date, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(stat_date, time.max, tzinfo=timezone.utc)
        stmt = (
            select(AgentResponseLogModel)
            .where(
                AgentResponseLogModel.logged_at >= start_of_day,
                AgentResponseLogModel.logged_at <= end_of_day,
                AgentResponseLogModel.is_deleted == 0,
            )
            .order_by(AgentResponseLogModel.logged_at, AgentResponseLogModel.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_agent_daily_stats(self, stats_list: list[dict]) -> None:
        """
        Upsert agent daily stats rows.

        On conflict (agent_id, stat_date) the row is updated with the latest computed values.
        """
        if not stats_list:
            return

        now = utc_now()
        rows = []
        for s in stats_list:
            rows.append(
                {
                    "id": generate_sequential_uuid(),
                    "agent_id": s["agent_id"],
                    "stat_date": s["stat_date"],
                    "execution_count": s["execution_count"],
                    "success_count": s["success_count"],
                    "error_count": s["error_count"],
                    "avg_response_ms": s.get("avg_response_ms"),
                    "min_response_ms": s.get("min_response_ms"),
                    "max_response_ms": s.get("max_response_ms"),
                    "total_response_ms": s.get("total_response_ms"),
                    "total_nodes_executed": s["total_nodes_executed"],
                    "avg_success_rate": s.get("avg_success_rate"),
                    "total_success_rate_sum": s.get("total_success_rate_sum"),
                    "rag_used_count": s["rag_used_count"],
                    "unique_conversations": s["unique_conversations"],
                    "finalized_conversations": s.get("finalized_conversations", 0),
                    "in_progress_conversations": s.get("in_progress_conversations", 0),
                    "thumbs_up_count": s.get("thumbs_up_count", 0),
                    "thumbs_down_count": s.get("thumbs_down_count", 0),
                    "last_aggregated_at": now,
                    "is_deleted": 0,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        for start in range(0, len(rows), _UPSERT_BATCH_SIZE):
            chunk = rows[start : start + _UPSERT_BATCH_SIZE]
            stmt = insert(AgentExecutionDailyStatsModel).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_agent_execution_daily_stats_agent_date",
                set_={
                    "execution_count": stmt.excluded.execution_count,
                    "success_count": stmt.excluded.success_count,
                    "error_count": stmt.excluded.error_count,
                    "avg_response_ms": stmt.excluded.avg_response_ms,
                    "min_response_ms": stmt.excluded.min_response_ms,
                    "max_response_ms": stmt.excluded.max_response_ms,
                    "total_response_ms": stmt.excluded.total_response_ms,
                    "total_nodes_executed": stmt.excluded.total_nodes_executed,
                    "avg_success_rate": stmt.excluded.avg_success_rate,
                    "total_success_rate_sum": stmt.excluded.total_success_rate_sum,
                    "rag_used_count": stmt.excluded.rag_used_count,
                    "unique_conversations": stmt.excluded.unique_conversations,
                    "finalized_conversations": stmt.excluded.finalized_conversations,
                    "in_progress_conversations": stmt.excluded.in_progress_conversations,
                    "thumbs_up_count": stmt.excluded.thumbs_up_count,
                    "thumbs_down_count": stmt.excluded.thumbs_down_count,
                    "last_aggregated_at": stmt.excluded.last_aggregated_at,
                    "is_deleted": stmt.excluded.is_deleted,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await self.db.execute(stmt)
        await self.db.flush()

    async def upsert_node_daily_stats(self, stats_list: list[dict]) -> None:
        """
        Upsert node daily stats rows.

        On conflict (agent_id, node_type, stat_date) the row is updated.
        """
        if not stats_list:
            return

        now = utc_now()
        rows = []
        for s in stats_list:
            rows.append(
                {
                    "id": generate_sequential_uuid(),
                    "agent_id": s["agent_id"],
                    "node_type": s["node_type"],
                    "stat_date": s["stat_date"],
                    "execution_count": s["execution_count"],
                    "success_count": s["success_count"],
                    "failure_count": s["failure_count"],
                    "unique_conversations": s.get("unique_conversations", 0),
                    "thumbs_up_count": s.get("thumbs_up_count", 0),
                    "thumbs_down_count": s.get("thumbs_down_count", 0),
                    "avg_execution_ms": s.get("avg_execution_ms"),
                    "min_execution_ms": s.get("min_execution_ms"),
                    "max_execution_ms": s.get("max_execution_ms"),
                    "total_execution_ms": s.get("total_execution_ms"),
                    "is_deleted": 0,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        for start in range(0, len(rows), _UPSERT_BATCH_SIZE):
            chunk = rows[start : start + _UPSERT_BATCH_SIZE]
            stmt = insert(NodeExecutionDailyStatsModel).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_node_execution_daily_stats_agent_node_date",
                set_={
                    "execution_count": stmt.excluded.execution_count,
                    "success_count": stmt.excluded.success_count,
                    "failure_count": stmt.excluded.failure_count,
                    "unique_conversations": stmt.excluded.unique_conversations,
                    "thumbs_up_count": stmt.excluded.thumbs_up_count,
                    "thumbs_down_count": stmt.excluded.thumbs_down_count,
                    "avg_execution_ms": stmt.excluded.avg_execution_ms,
                    "min_execution_ms": stmt.excluded.min_execution_ms,
                    "max_execution_ms": stmt.excluded.max_execution_ms,
                    "total_execution_ms": stmt.excluded.total_execution_ms,
                    "is_deleted": stmt.excluded.is_deleted,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await self.db.execute(stmt)
        await self.db.flush()

    async def get_aggregation_state(self) -> AnalyticsAggregationStateModel | None:
        """Return the single-row discovery cursor, or None before first cutover."""
        result = await self.db.execute(select(AnalyticsAggregationStateModel))
        return result.scalars().first()

    async def get_db_now(self) -> datetime:
        """Shared cutoff all workers use (DB-sourced, not local clocks). App-written
        imestamps via Python callables. Overlap absorbs skew."""
        result = await self.db.execute(select(func.now()))
        return result.scalar_one()

    async def upsert_aggregation_state(self, cutoff: datetime) -> None:
        """Advance the cursor to cutoff. GREATEST keeps it monotonic under a stale write.
        Reset is_deleted: the unique constraint matches soft-deleted rows, which the
        global filter would then hide from every read.
        """
        now = utc_now()
        stmt = insert(AnalyticsAggregationStateModel).values(
            {
                "id": generate_sequential_uuid(),
                "state_key": 1,
                "last_incremental_run_at": cutoff,
                "is_deleted": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_analytics_aggregation_state_key",
            set_={
                "last_incremental_run_at": func.greatest(
                    AnalyticsAggregationStateModel.__table__.c.last_incremental_run_at,
                    stmt.excluded.last_incremental_run_at,
                ),
                "is_deleted": stmt.excluded.is_deleted,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def discover_affected_dates(self, since: datetime, until: datetime) -> list[date]:
        """Distinct UTC dates needing recompute: log activity and conversation
        mutations in [since, until], including the days a changed conversation's
        historical logs and phantom realtime increments landed on.
        """
        log_date = _utc_date(AgentResponseLogModel.logged_at)
        window = [ConversationModel.updated_at >= since, ConversationModel.updated_at <= until]
        stmt = union(
            # New logs.
            select(log_date).where(
                AgentResponseLogModel.logged_at >= since,
                AgentResponseLogModel.logged_at <= until,
                AgentResponseLogModel.is_deleted == 0,
            ),
            # Historical log dates of changed conversations.
            select(log_date)
            .join(ConversationModel, ConversationModel.id == AgentResponseLogModel.conversation_id)
            .where(*window, AgentResponseLogModel.is_deleted == 0),
            # The mutation day itself (wrong-day realtime increments book here).
            select(_utc_date(ConversationModel.updated_at)).where(*window),
            # Creation day of changed conversations that have no logs at all.
            select(_utc_date(func.coalesce(ConversationModel.conversation_date, ConversationModel.created_at))).where(
                *window,
                ~exists(
                    select(AgentResponseLogModel.id).where(
                        AgentResponseLogModel.conversation_id == ConversationModel.id,
                        AgentResponseLogModel.is_deleted == 0,
                    )
                ),
            ),
        ).execution_options(**_DISCOVERY_FLAGS)
        result = await self.db.execute(stmt)
        return sorted(d for (d,) in result.all() if d is not None)

    def get_calendar_sweep_dates(self, cursor_date: date | None, today: date) -> list[date]:
        """Every UTC date from cursor to today. Defaults to yesterday+today to avoid
        scanning years of empty data on first cutover."""
        if cursor_date is None:
            return [today - timedelta(days=1), today]
        start = min(cursor_date, today)
        return [start + timedelta(days=offset) for offset in range((today - start).days + 1)]

    async def get_stats_only_dates(self, from_date: date | None, to_date: date | None) -> list[date]:
        """Distinct stat dates present in either stats table, so a backfill also
        selects phantom dates that have stats rows but no logs. Each bound applies
        independently and only when provided.
        """
        dates: set[date] = set()
        for column in (AgentExecutionDailyStatsModel.stat_date, NodeExecutionDailyStatsModel.stat_date):
            stmt = select(column).distinct()
            if from_date is not None:
                stmt = stmt.where(column >= from_date)
            if to_date is not None:
                stmt = stmt.where(column <= to_date)
            result = await self.db.execute(stmt)
            dates.update(d for (d,) in result.all())
        return sorted(dates)

    async def reconcile_agent_daily_stats(
        self, stat_date: date, present_agent_ids: list[UUID], stamped_at: datetime
    ) -> tuple[int, int]:
        """Repair agent rows the rebuild no longer produces for the date: soft-delete the
        cost-free ones, zero the batch-owned columns of the cost-bearing rest so their
        realtime-owned token/cost data stays visible. A later upsert of the key revives
        a hidden row."""
        tbl = AgentExecutionDailyStatsModel
        absent = [tbl.stat_date == stat_date, tbl.is_deleted == 0]
        if present_agent_ids:
            absent.append(tbl.agent_id.not_in(present_agent_ids))

        soft_delete_stmt = (
            update(tbl)
            .where(
                *absent,
                func.coalesce(tbl.total_input_tokens, 0) == 0,
                func.coalesce(tbl.total_output_tokens, 0) == 0,
                func.coalesce(tbl.total_cost_usd, 0.0) == 0.0,
            )
            .values(is_deleted=1, updated_at=stamped_at)
            .execution_options(synchronize_session=False)
        )
        soft_deleted = await self.db.execute(soft_delete_stmt)

        zero_stmt = (
            update(tbl)
            .where(*absent)
            .values(
                execution_count=0,
                success_count=0,
                error_count=0,
                avg_response_ms=None,
                min_response_ms=None,
                max_response_ms=None,
                total_response_ms=None,
                total_nodes_executed=0,
                avg_success_rate=None,
                total_success_rate_sum=None,
                rag_used_count=0,
                unique_conversations=0,
                finalized_conversations=0,
                in_progress_conversations=0,
                thumbs_up_count=0,
                thumbs_down_count=0,
                last_aggregated_at=stamped_at,
                updated_at=stamped_at,
            )
            .execution_options(synchronize_session=False)
        )
        zeroed = await self.db.execute(zero_stmt)

        await self.db.flush()
        return soft_deleted.rowcount, zeroed.rowcount

    async def reconcile_node_daily_stats(
        self, stat_date: date, present_keys: list[tuple[UUID, str]], stamped_at: datetime
    ) -> int:
        """Soft-delete node rows not in the rebuild. Nothing on this table is
        realtime-owned, so no absent row has to stay visible."""
        tbl = NodeExecutionDailyStatsModel
        stmt = update(tbl).where(tbl.stat_date == stat_date, tbl.is_deleted == 0)
        if present_keys:
            stmt = stmt.where(tuple_(tbl.agent_id, tbl.node_type).not_in(present_keys))
        stmt = stmt.values(is_deleted=1, updated_at=stamped_at).execution_options(synchronize_session=False)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount
