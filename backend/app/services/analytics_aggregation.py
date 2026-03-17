import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import UUID

from injector import inject

from app.core.utils.date_time_utils import utc_now
from app.repositories.analytics_aggregation import AnalyticsAggregationRepository

logger = logging.getLogger(__name__)


class AnalyticsAggregationService:
    @inject
    def __init__(self, repo: AnalyticsAggregationRepository):
        self.repo = repo

    async def aggregate_daily_stats(self) -> dict:
        """
        Main entry point for the Celery task.

        1. Determines the time window since last aggregation (default: 30 days ago).
        2. Fetches agent_response_logs in that window.
        3. Parses raw_response JSON to extract agent + node metrics.
        4. Groups metrics by (agent_id, date) and (agent_id, node_type, date).
        5. Upserts both summary tables.
        """
        now = utc_now()
        last_ts = await self.repo.get_last_aggregation_timestamp()
        if last_ts is not None:
            # Incremental: only process logs since the last aggregation
            since = last_ts
        else:
            # First run: process all historical logs
            earliest = await self.repo.get_earliest_log_timestamp()
            since = earliest if earliest is not None else now

        logger.info(f"Aggregating analytics: since={since.isoformat()} until={now.isoformat()}")

        BATCH_SIZE = 1000
        offset = 0
        total_processed = 0

        # Accumulators keyed by (agent_id, stat_date)
        agent_buckets: dict[tuple, dict] = defaultdict(
            lambda: {
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
                # maps conversation_id -> (thumbs_up, thumbs_down) — deduplicates per conversation
                "thumbs_data": {},
            }
        )

        # Accumulators keyed by (agent_id, node_type, stat_date)
        node_buckets: dict[tuple, dict] = defaultdict(
            lambda: {
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "execution_ms_values": [],
                "conversation_ids": set(),
                "thumbs_data": {},
            }
        )

        while True:
            logs = await self.repo.get_response_logs_since(since, now, limit=BATCH_SIZE, offset=offset)
            if not logs:
                break

            logger.info(f"Processing batch of {len(logs)} logs (offset={offset})")

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

                stat_date = log.logged_at.date()
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
                if conv_id:
                    conv_id_str = str(conv_id)
                    ab["conversation_ids"].add(conv_id_str)
                    if log.conversation is not None:
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

                    if conv_id:
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

            total_processed += len(logs)
            if len(logs) < BATCH_SIZE:
                break
            offset += BATCH_SIZE

        logger.info(f"Processed {total_processed} total agent response logs")

        if total_processed == 0:
            return {"agent_stats_upserted": 0, "node_stats_upserted": 0}

        # Build agent stats rows
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

        # Build node stats rows
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

        await self.repo.upsert_agent_daily_stats(agent_stats)
        await self.repo.upsert_node_daily_stats(node_stats)

        logger.info(
            f"Analytics aggregation complete: {len(agent_stats)} agent rows, {len(node_stats)} node rows"
        )
        return {
            "agent_stats_upserted": len(agent_stats),
            "node_stats_upserted": len(node_stats),
        }
