import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import UUID

from injector import inject

from app.core.utils.date_time_utils import utc_now
from app.db.models.agent_response_log import AgentResponseLogModel
from app.repositories.analytics_aggregation import AnalyticsAggregationRepository

logger = logging.getLogger(__name__)


class AnalyticsAggregationService:
    @inject
    def __init__(self, repo: AnalyticsAggregationRepository):
        self.repo = repo

    async def aggregate_daily_stats(self) -> dict:
        """
        Main entry point for the Celery task.

        Strategy: Date-based re-aggregation
        1. Find dates with new logs since last aggregation
        2. For each affected date, fetch ALL logs and recompute complete stats
        3. Upsert complete stats (safe to replace since we have full data)
        """
        now = utc_now()
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
            agent_stats, node_stats = await self._aggregate_single_date(stat_date)
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

    async def _aggregate_single_date(self, stat_date: date) -> tuple[list[dict], list[dict]]:
        """
        Aggregate ALL logs for a single date.

        Returns tuple of (agent_stats_list, node_stats_list).
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
            return [], []

        # Build buckets from all logs for this date
        agent_buckets, node_buckets = self._build_buckets_from_logs(all_logs, stat_date)

        # Convert buckets to stats dicts
        agent_stats = self._build_agent_stats_from_buckets(agent_buckets)
        node_stats = self._build_node_stats_from_buckets(node_buckets)

        return agent_stats, node_stats

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
        self, logs: list[AgentResponseLogModel], stat_date: date
    ) -> tuple[dict[tuple, dict], dict[tuple, dict]]:
        """
        Process logs and build accumulator buckets.

        Returns (agent_buckets, node_buckets) where:
        - agent_buckets: keyed by (agent_id, stat_date)
        - node_buckets: keyed by (agent_id, node_type, stat_date)
        """
        agent_buckets: dict[tuple, dict] = defaultdict(self._create_agent_bucket)
        node_buckets: dict[tuple, dict] = defaultdict(self._create_node_bucket)

        for log in logs:
            try:
                payload = json.loads(log.raw_response)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse raw_response for log id={log.id}")
                continue

            agent_id_raw = payload.get("agent_id")
            if not agent_id_raw:
                continue

            try:
                agent_id = UUID(str(agent_id_raw))
            except (ValueError, AttributeError):
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
                if conv_status == "finalized":
                    ab["finalized_conversation_ids"].add(conv_id_str)
                else:
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

                if conv_id_str:
                    nb["conversation_ids"].add(conv_id_str)
                    if conv_id_str not in nb["thumbs_data"] and log.conversation is not None:
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

        return dict(agent_buckets), dict(node_buckets)

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
