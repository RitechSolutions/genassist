import json
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.tenant_scope import get_tenant_context
from app.core.utils.date_time_utils import utc_now
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.db.models.agent_response_log import AgentResponseLogModel
from app.repositories.analytics_aggregation import AnalyticsAggregationRepository

logger = logging.getLogger(__name__)


class AnalyticsAggregationService:
    @inject
    def __init__(self, repo: AnalyticsAggregationRepository, db: AsyncSession):
        self.repo = repo
        self.db = db

    async def aggregate_daily_stats(
        self,
        force_full: bool = False,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        """
        Main entry point for the Celery task.

        ``ANALYTICS_AGG_V2`` off: watermark path, upsert-only (the backfill included). On:
        cursor-based discovery with per-date rebuild, soft-delete reconciliation, and phantom
        date selection. Turning the flag off again stops reconciling but does not revive rows
        it already hid; the next upsert of the same key does.
        """
        if not settings.ANALYTICS_AGG_V2:
            if not force_full and settings.ANALYTICS_AGG_PREVIEW_ENABLED:
                await self._log_discovery_preview()
            return await self._aggregate_daily_stats_legacy(force_full, from_date, to_date)
        if force_full:
            return await self._backfill_authoritative(from_date, to_date)
        return await self._aggregate_incremental()

    async def _aggregate_daily_stats_legacy(
        self,
        force_full: bool = False,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        """
        Strategy: Date-based re-aggregation
        1. Find dates with new logs since last aggregation
        2. For each affected date, fetch ALL logs and recompute complete stats
        3. Upsert complete stats (safe to replace since we have full data)

        Incremental (default): only dates with new logs since the last run are
        recomputed.

        Backfill (``force_full=True``): the "since last aggregation" short-circuit
        is bypassed and every date with logs is recomputed from scratch, optionally
        restricted to the inclusive ``[from_date, to_date]`` window. This repopulates
        columns added after rows were first aggregated (e.g. ``unique_conversations``).
        To stay safe at scale, the backfill flushes each date independently rather
        than buffering the whole history in memory. Idempotent (upserts overwrite),
        so re-running or running in slices is safe.
        """
        now = utc_now()

        if force_full:
            since = (
                datetime.combine(from_date, time.min, tzinfo=timezone.utc)
                if from_date is not None
                else await self.repo.get_earliest_log_timestamp()
            )
            if since is None:
                logger.info("No logs found for backfill")
                return {"agent_stats_upserted": 0, "node_stats_upserted": 0}
            until = datetime.combine(to_date, time.max, tzinfo=timezone.utc) if to_date is not None else now
            affected_dates = await self.repo.get_affected_dates_since(since, until)
            logger.info(
                f"Backfill: recomputing {len(affected_dates)} dates ({from_date or 'earliest'} -> {to_date or 'now'})"
            )
            return await self._aggregate_dates_streaming(affected_dates)

        last_ts = await self.repo.get_last_aggregation_timestamp()

        if last_ts is not None:
            # Find which dates have new activity since last aggregation
            affected_dates = await self.repo.get_affected_dates_since(last_ts, now)
            if not affected_dates:
                logger.info("No new logs since last aggregation")
                return {"agent_stats_upserted": 0, "node_stats_upserted": 0}
        else:
            # First run: get all unique dates from all logs
            earliest = await self.repo.get_earliest_log_timestamp()
            if earliest is None:
                logger.info("No logs found for aggregation")
                return {"agent_stats_upserted": 0, "node_stats_upserted": 0}
            affected_dates = await self.repo.get_affected_dates_since(earliest, now)

        logger.info(f"Aggregating {len(affected_dates)} affected dates: {affected_dates}")

        # Process each date independently with complete data
        all_agent_stats = []
        all_node_stats = []

        for stat_date in affected_dates:
            agent_stats, node_stats, _ = await self._aggregate_single_date(stat_date)
            all_agent_stats.extend(agent_stats)
            all_node_stats.extend(node_stats)

        await self.repo.upsert_agent_daily_stats(all_agent_stats)
        await self.repo.upsert_node_daily_stats(all_node_stats)

        logger.info(
            f"Analytics aggregation complete: {len(all_agent_stats)} agent rows, {len(all_node_stats)} node rows"
        )
        return {
            "agent_stats_upserted": len(all_agent_stats),
            "node_stats_upserted": len(all_node_stats),
        }

    async def _resolve_incremental_window(self) -> tuple[datetime, datetime, date | None]:
        cutoff = await self.repo.get_db_now()
        overlap = timedelta(minutes=settings.ANALYTICS_AGG_SCAN_OVERLAP_MINUTES)
        lookback = timedelta(hours=settings.ANALYTICS_AGG_HEAL_LOOKBACK_HOURS)
        state = await self.repo.get_aggregation_state()
        if state is not None:
            cursor = state.last_incremental_run_at
            return cursor - overlap, cutoff, cursor.astimezone(timezone.utc).date()
        watermark = await self.repo.get_last_aggregation_timestamp()
        if watermark is not None:
            return watermark - lookback - overlap, cutoff, None
        # First run: seed bounded window, not earliest log, to avoid scanning whole
        # history. Changed conversations still included. Backfill rebuilds existing.
        return cutoff - lookback - overlap, cutoff, None

    async def _select_dates(
        self, since: datetime, cutoff: datetime, cursor_date: date | None
    ) -> tuple[list[date], date]:
        """Discovery union plus the calendar sweep, capped at today. Shared so the
        flag-off preview predicts exactly what the V2 run would select."""
        discovered = await self.repo.discover_affected_dates(since, cutoff)
        today = cutoff.astimezone(timezone.utc).date()
        sweep = self.repo.get_calendar_sweep_dates(cursor_date, today)
        return sorted(d for d in {*discovered, *sweep} if d <= today), today

    async def _log_discovery_preview(self) -> None:
        """Preview what V2 would select, read-only. Errors swallowed to not affect
        the run, except timeouts."""
        try:
            since, cutoff, cursor_date = await self._resolve_incremental_window()
            selected, _ = await self._select_dates(since, cutoff, cursor_date)
            logger.info(
                f"[analytics-agg] dry-run tenant={get_tenant_context()}: V2 would select {len(selected)} date(s)"
            )
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            # Roll back so a failed preview statement can't leave the shared
            # scope session in an aborted transaction for the run.
            await self.db.rollback()
            logger.warning("[analytics-agg] dry-run discovery preview failed", exc_info=True)

    async def _aggregate_incremental(self) -> dict:
        tenant = get_tenant_context()
        since, cutoff, cursor_date = await self._resolve_incremental_window()
        logger.info(
            f"[analytics-agg] tenant={tenant}: cursor={'set' if cursor_date is not None else 'absent'}, "
            f"discovering window=[{since} .. {cutoff}]"
        )
        selected, today = await self._select_dates(since, cutoff, cursor_date)
        past_dates = [d for d in selected if d < today]
        logger.info(f"[analytics-agg] tenant={tenant}: selected={len(selected)} date(s)")

        agent_rows = 0
        node_rows = 0
        unreconciled = 0
        for stat_date in past_dates:
            logger.info(f"[analytics-agg] tenant={tenant}: processing {stat_date}")
            try:
                added_agents, added_nodes, skipped = await self._process_past_date(stat_date)
            except Exception:
                await self.db.rollback()
                logger.error(
                    f"[analytics-agg] tenant={tenant}: date {stat_date} failed and was rolled back; "
                    "cursor not advanced",
                    exc_info=True,
                )
                raise
            agent_rows += added_agents
            node_rows += added_nodes
            unreconciled += skipped
            logger.info(f"[analytics-agg] tenant={tenant}: date {stat_date} committed")

        logger.info(f"[analytics-agg] tenant={tenant}: processing today ({today})")
        today_rebuild_failed = False
        try:
            agent_stats, node_stats, unattributed = await self._rebuild_and_upsert(today)
            await self.db.commit()
            agent_rows += len(agent_stats)
            node_rows += len(node_stats)
            if unattributed:
                today_rebuild_failed = True
                logger.error(
                    f"[analytics-agg] tenant={tenant}: today ({today}) has {unattributed} unreadable "
                    "log(s); rebuilt from the readable ones only"
                )
        except SoftTimeLimitExceeded:
            await self.db.rollback()
            raise
        except Exception:
            # Today is non-authoritative and retried next run, so it must not block the
            # cursor. Surfaced in the result so a green task can still be alerted on.
            await self.db.rollback()
            today_rebuild_failed = True
            logger.error(f"[analytics-agg] tenant={tenant}: today ({today}) rebuild failed", exc_info=True)

        await self.repo.upsert_aggregation_state(cutoff)
        await self.db.commit()
        cursor_age = (utc_now() - cutoff.astimezone(timezone.utc)).total_seconds()
        logger.info(
            f"[analytics-agg] tenant={tenant}: cursor advanced to {cutoff} (age {cursor_age:.0f}s); "
            f"{len(past_dates)} past date(s), agent_rows={agent_rows}, node_rows={node_rows}, "
            f"unreconciled={unreconciled}"
        )
        return {
            "agent_stats_upserted": agent_rows,
            "node_stats_upserted": node_rows,
            "dates_selected": len(selected),
            "dates_not_reconciled": unreconciled,
            "today_rebuild_failed": today_rebuild_failed,
        }

    async def _backfill_authoritative(self, from_date: date | None, to_date: date | None) -> dict:
        """Backfill: log dates + stats-only dates, rebuild and reconcile per date."""
        tenant = get_tenant_context()
        cutoff = await self.repo.get_db_now()
        today = cutoff.astimezone(timezone.utc).date()
        logger.info(
            f"[analytics-agg] tenant={tenant}: backfill discovering ({from_date or 'open'} -> {to_date or 'today'})"
        )

        log_since = (
            datetime.combine(from_date, time.min, tzinfo=timezone.utc)
            if from_date is not None
            else await self.repo.get_earliest_log_timestamp()
        )
        log_until = datetime.combine(to_date, time.max, tzinfo=timezone.utc) if to_date is not None else cutoff
        log_dates = await self.repo.get_affected_dates_since(log_since, log_until) if log_since is not None else []
        stats_dates = await self.repo.get_stats_only_dates(from_date, to_date if to_date is not None else today)

        selected = sorted(d for d in {*log_dates, *stats_dates} if d <= today)
        past_dates = [d for d in selected if d < today]
        logger.info(
            f"[analytics-agg] tenant={tenant}: backfill selected={len(selected)} date(s) "
            f"({from_date or 'open'} -> {to_date or 'today'})"
        )

        agent_rows = 0
        node_rows = 0
        unreconciled = 0
        for stat_date in past_dates:
            logger.info(f"[analytics-agg] tenant={tenant}: backfill processing {stat_date}")
            try:
                added_agents, added_nodes, skipped = await self._process_past_date(stat_date)
            except Exception:
                await self.db.rollback()
                logger.error(
                    f"[analytics-agg] tenant={tenant}: backfill date {stat_date} failed and was rolled back",
                    exc_info=True,
                )
                raise
            agent_rows += added_agents
            node_rows += added_nodes
            unreconciled += skipped

        today_rebuild_failed = False
        if today in selected:
            logger.info(f"[analytics-agg] tenant={tenant}: backfill processing today ({today})")
            try:
                agent_stats, node_stats, unattributed = await self._rebuild_and_upsert(today)
                await self.db.commit()
            except Exception:
                # A manual backfill surfaces the failure instead of swallowing it
                # roll back so the session stays usable.
                await self.db.rollback()
                logger.error(
                    f"[analytics-agg] tenant={tenant}: backfill today ({today}) failed and was rolled back",
                    exc_info=True,
                )
                raise
            agent_rows += len(agent_stats)
            node_rows += len(node_stats)
            if unattributed:
                today_rebuild_failed = True
                logger.error(
                    f"[analytics-agg] tenant={tenant}: backfill today ({today}) has {unattributed} "
                    "unreadable log(s); rebuilt from the readable ones only"
                )

        logger.info(
            f"[analytics-agg] tenant={tenant}: backfill complete; "
            f"agent_rows={agent_rows}, node_rows={node_rows} across {len(selected)} date(s), "
            f"unreconciled={unreconciled}"
        )
        return {
            "agent_stats_upserted": agent_rows,
            "node_stats_upserted": node_rows,
            "dates_selected": len(selected),
            "dates_not_reconciled": unreconciled,
            "today_rebuild_failed": today_rebuild_failed,
        }

    async def _rebuild_and_upsert(self, stat_date: date) -> tuple[list[dict], list[dict], int]:
        """Rebuild one date from every log it can read and upsert the result."""
        agent_stats, node_stats, unattributed = await self._aggregate_single_date(stat_date)
        await self.repo.upsert_agent_daily_stats(agent_stats)
        await self.repo.upsert_node_daily_stats(node_stats)
        return agent_stats, node_stats, unattributed

    async def _process_past_date(self, stat_date: date) -> tuple[int, int, bool]:
        """Rebuild + upsert + reconcile one past date; the whole date commits atomically.
        Reconciliation soft-deletes and zeroes whatever the rebuild did not produce, and an
        unreadable log's agent is exactly what it did not produce, so it is skipped
        whenever any log stayed unattributed.
        """
        agent_stats, node_stats, unattributed = await self._rebuild_and_upsert(stat_date)
        if unattributed:
            await self.db.commit()
            logger.error(
                f"[analytics-agg] tenant={get_tenant_context()}: {stat_date} has {unattributed} "
                "unreadable log(s); rebuilt from the readable ones, NOT reconciled. Repair the "
                "log payloads, then backfill the date — a backfill over the same logs skips "
                "reconciliation again"
            )
            return len(agent_stats), len(node_stats), True

        stamped_at = utc_now()
        soft_deleted, zeroed = await self.repo.reconcile_agent_daily_stats(
            stat_date, [s["agent_id"] for s in agent_stats], stamped_at
        )
        nodes_soft_deleted = await self.repo.reconcile_node_daily_stats(
            stat_date, [(s["agent_id"], s["node_type"]) for s in node_stats], stamped_at
        )
        await self.db.commit()
        if soft_deleted or zeroed or nodes_soft_deleted:
            logger.info(
                f"[analytics-agg] tenant={get_tenant_context()}: reconciled {stat_date}: "
                f"agent soft_deleted={soft_deleted} zeroed={zeroed}, node soft_deleted={nodes_soft_deleted}"
            )
        return len(agent_stats), len(node_stats), False

    async def _aggregate_dates_streaming(self, affected_dates: list[date]) -> dict:
        """Aggregate and upsert one date at a time to keep memory bounded.

        Each date is fetched, recomputed and upserted independently, so peak
        memory is one day's logs (not the whole history) and an interrupted
        backfill can simply be re-run (upserts are idempotent).
        """
        agent_rows = 0
        node_rows = 0
        for stat_date in affected_dates:
            agent_stats, node_stats, _ = await self._aggregate_single_date(stat_date)
            await self.repo.upsert_agent_daily_stats(agent_stats)
            await self.repo.upsert_node_daily_stats(node_stats)
            agent_rows += len(agent_stats)
            node_rows += len(node_stats)
        logger.info(
            f"Backfill complete: {agent_rows} agent rows, {node_rows} node rows across {len(affected_dates)} dates"
        )
        return {"agent_stats_upserted": agent_rows, "node_stats_upserted": node_rows}

    async def _aggregate_single_date(self, stat_date: date) -> tuple[list[dict], list[dict], int]:
        """
        Aggregate ALL logs for a single date.

        Returns tuple of (agent_stats_list, node_stats_list, unattributed_log_count).
        """
        # Fetch ALL logs for this date (paginated to avoid memory issues)
        BATCH_SIZE = 10000
        offset = 0
        all_logs: list[AgentResponseLogModel] = []

        while True:
            logs = await self.repo.get_response_logs_for_date(stat_date, limit=BATCH_SIZE, offset=offset)
            if not logs:
                break
            all_logs.extend(logs)
            if len(logs) < BATCH_SIZE:
                break
            offset += BATCH_SIZE

        if not all_logs:
            return [], [], 0

        # Hidden-value masking can rewrite the payload's agent_id before it is logged;
        # the conversation's operator still identifies the agent unambiguously.
        agent_by_conversation = await self.repo.get_conversation_agent_map(stat_date)

        # Build buckets from all logs for this date
        agent_buckets, node_buckets, unattributed = self._build_buckets_from_logs(
            all_logs, stat_date, agent_by_conversation
        )

        # Convert buckets to stats dicts
        agent_stats = self._build_agent_stats_from_buckets(agent_buckets)
        node_stats = self._build_node_stats_from_buckets(node_buckets)

        return agent_stats, node_stats, unattributed

    def _create_agent_bucket(self) -> dict:
        """Factory for agent bucket accumulator."""
        return {
            "execution_count": 0,
            "success_count": 0,
            "error_count": 0,
            "response_ms_values": [],
            "total_nodes_executed": 0,
            "node_success_rates": [],
            "rag_used_count": 0,
            "conversation_ids": set(),
            "finalized_conversation_ids": set(),
            "in_progress_conversation_ids": set(),
            "thumbs_data": {},  # maps conversation_id -> (thumbs_up, thumbs_down)
        }

    def _create_node_bucket(self) -> dict:
        """Factory for node bucket accumulator."""
        return {
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "execution_ms_values": [],
            "conversation_ids": set(),
            "thumbs_data": {},
        }

    def _build_buckets_from_logs(
        self,
        logs: list[AgentResponseLogModel],
        stat_date: date,
        agent_by_conversation: dict[UUID, UUID] | None = None,
    ) -> tuple[dict[tuple, dict], dict[tuple, dict], int]:
        """
        Process logs and build accumulator buckets.

        Returns (agent_buckets, node_buckets, unattributed) where:
        - agent_buckets: keyed by (agent_id, stat_date)
        - node_buckets: keyed by (agent_id, node_type, stat_date)
        - unattributed: logs skipped because no agent could be resolved from them,
          neither from the payload nor via ``agent_by_conversation``
        """
        agent_buckets: dict[tuple, dict] = defaultdict(self._create_agent_bucket)
        node_buckets: dict[tuple, dict] = defaultdict(self._create_node_bucket)
        unattributed = 0

        for log in logs:
            try:
                payload = json.loads(log.raw_response)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse raw_response for log id={log.id}")
                unattributed += 1
                continue
            if not isinstance(payload, dict):
                logger.warning(f"raw_response is not a JSON object for log id={log.id}")
                unattributed += 1
                continue

            try:
                agent_id = UUID(str(payload.get("agent_id") or ""))
            except ValueError:
                agent_id = agent_by_conversation.get(log.conversation_id) if agent_by_conversation else None
            if agent_id is None:
                logger.warning(f"Could not resolve an agent for log id={log.id} conversation_id={log.conversation_id}")
                unattributed += 1
                continue

            agent_key = (agent_id, stat_date)
            ab = agent_buckets[agent_key]

            # Execution status
            status = (payload.get("status") or "").lower()
            ab["execution_count"] += 1
            if status in ("success", "completed"):
                ab["success_count"] += 1
            else:
                ab["error_count"] += 1

            # Conversation tracking + thumbs (deduplicated by conversation_id)
            conv_id = log.conversation_id
            conv_id_str = str(conv_id) if conv_id else None
            if conv_id_str and log.conversation is not None:
                ab["conversation_ids"].add(conv_id_str)
                conv_status = (log.conversation.status or "").lower()
                if conv_status == ConversationStatus.FINALIZED.value:
                    ab["finalized_conversation_ids"].add(conv_id_str)
                elif conv_status in (
                    ConversationStatus.IN_PROGRESS.value,
                    ConversationStatus.TAKE_OVER.value,
                ):
                    ab["in_progress_conversation_ids"].add(conv_id_str)
                if conv_id_str not in ab["thumbs_data"]:
                    ab["thumbs_data"][conv_id_str] = (
                        log.conversation.thumbs_up_count or 0,
                        log.conversation.thumbs_down_count or 0,
                    )

            # Response timing — camelCase keys from row_agent_response.performance_metrics
            row_response = payload.get("row_agent_response") or {}
            perf = row_response.get("performance_metrics") or row_response.get("performanceMetrics") or {}
            total_ms = perf.get("totalExecutionTime") or perf.get("total_execution_time_ms")
            if total_ms is not None:
                try:
                    ab["response_ms_values"].append(float(total_ms))
                except (TypeError, ValueError):
                    pass

            # RAG used — top-level boolean field
            if payload.get("rag_used"):
                ab["rag_used_count"] += 1

            # Node-level stats — nodeExecutionStatus is a dict keyed by node UUID
            state = row_response.get("state") or {}
            node_statuses_raw = state.get("nodeExecutionStatus") or payload.get("nodeExecutionStatus") or {}

            # Support both dict (keyed by UUID) and list formats
            if isinstance(node_statuses_raw, dict):
                node_list = list(node_statuses_raw.values())
            else:
                node_list = node_statuses_raw

            for node in node_list:
                if not isinstance(node, dict):
                    continue

                ntype = node.get("type") or node.get("node_type") or ""
                nstatus = (node.get("status") or "").lower()
                n_ms = node.get("time_taken") or node.get("execution_time_ms")

                ab["total_nodes_executed"] += 1

                node_key = (agent_id, ntype, stat_date)
                nb = node_buckets[node_key]
                nb["execution_count"] += 1

                # Count the conversation only when its row is present (joins
                # exclude soft-deleted conversations), matching the agent-level
                # rule above and the summary's total_unique_conversations. Without
                # this guard, node unique_conversations counts soft-deleted
                # conversations the denominator omits, so escalation/containment
                # (node_uc / total_uc) can exceed 1 / go negative.
                if conv_id_str and log.conversation is not None:
                    nb["conversation_ids"].add(conv_id_str)
                    if conv_id_str not in nb["thumbs_data"]:
                        nb["thumbs_data"][conv_id_str] = (
                            log.conversation.thumbs_up_count or 0,
                            log.conversation.thumbs_down_count or 0,
                        )

                if nstatus in ("success", "completed"):
                    nb["success_count"] += 1
                else:
                    nb["failure_count"] += 1

                if n_ms is not None:
                    try:
                        nb["execution_ms_values"].append(float(n_ms))
                    except (TypeError, ValueError):
                        pass

            # Node success rate for this log
            if node_list:
                total_nodes = len(node_list)
                success_nodes = sum(
                    1
                    for n in node_list
                    if isinstance(n, dict) and (n.get("status") or "").lower() in ("success", "completed")
                )
                ab["node_success_rates"].append(success_nodes / total_nodes)

        return dict(agent_buckets), dict(node_buckets), unattributed

    def _build_agent_stats_from_buckets(self, agent_buckets: dict[tuple, dict]) -> list[dict]:
        """Convert agent buckets to stats dictionaries for upsert."""
        agent_stats = []
        for (agent_id, stat_date), ab in agent_buckets.items():
            ms_vals = ab["response_ms_values"]
            success_rates = ab["node_success_rates"]
            thumbs_values = list(ab["thumbs_data"].values())
            agent_stats.append(
                {
                    "agent_id": agent_id,
                    "stat_date": stat_date,
                    "execution_count": ab["execution_count"],
                    "success_count": ab["success_count"],
                    "error_count": ab["error_count"],
                    "avg_response_ms": (sum(ms_vals) / len(ms_vals)) if ms_vals else None,
                    "min_response_ms": min(ms_vals) if ms_vals else None,
                    "max_response_ms": max(ms_vals) if ms_vals else None,
                    "total_response_ms": sum(ms_vals) if ms_vals else None,
                    "total_nodes_executed": ab["total_nodes_executed"],
                    "avg_success_rate": (sum(success_rates) / len(success_rates)) if success_rates else None,
                    "total_success_rate_sum": sum(success_rates) if success_rates else None,
                    "rag_used_count": ab["rag_used_count"],
                    "unique_conversations": len(ab["conversation_ids"]),
                    "finalized_conversations": len(ab["finalized_conversation_ids"]),
                    "in_progress_conversations": len(ab["in_progress_conversation_ids"]),
                    "thumbs_up_count": sum(t[0] for t in thumbs_values),
                    "thumbs_down_count": sum(t[1] for t in thumbs_values),
                }
            )
        return agent_stats

    def _build_node_stats_from_buckets(self, node_buckets: dict[tuple, dict]) -> list[dict]:
        """Convert node buckets to stats dictionaries for upsert."""
        node_stats = []
        for (agent_id, node_type, stat_date), nb in node_buckets.items():
            ms_vals = nb["execution_ms_values"]
            node_thumbs = list(nb["thumbs_data"].values())
            node_stats.append(
                {
                    "agent_id": agent_id,
                    "node_type": node_type,
                    "stat_date": stat_date,
                    "execution_count": nb["execution_count"],
                    "success_count": nb["success_count"],
                    "failure_count": nb["failure_count"],
                    "avg_execution_ms": (sum(ms_vals) / len(ms_vals)) if ms_vals else None,
                    "min_execution_ms": min(ms_vals) if ms_vals else None,
                    "max_execution_ms": max(ms_vals) if ms_vals else None,
                    "total_execution_ms": sum(ms_vals) if ms_vals else None,
                    "unique_conversations": len(nb["conversation_ids"]),
                    "thumbs_up_count": sum(t[0] for t in node_thumbs),
                    "thumbs_down_count": sum(t[1] for t in node_thumbs),
                }
            )
        return node_stats
