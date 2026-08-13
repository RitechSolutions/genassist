"""
Real-time incremental analytics update.

Fired as a background asyncio.create_task after each agent_response_log is saved.
If this fails, the Celery worker's next run does a full recount — no data is lost.

Data access lives in AnalyticsAggregationRepository; this module handles parsing
of the raw agent_response payload and orchestration (tenant scope + commit).
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def parse_agent_response_for_stats(agent_response: dict) -> dict | None:
    """
    Extract fields needed for incremental update from the agent_response dict.

    Returns None if the response cannot be parsed (missing agent_id, etc.).
    Mirrors the parsing logic in analytics_aggregation.py but for a single log.
    """
    agent_id_raw = agent_response.get("agent_id")
    if not agent_id_raw:
        return None

    try:
        agent_id = UUID(str(agent_id_raw))
    except (ValueError, AttributeError):
        return None

    status = (agent_response.get("status") or "").lower()
    is_success = status in ("success", "completed")

    # Response timing
    row_response = agent_response.get("row_agent_response") or {}
    perf = (
        row_response.get("performance_metrics")
        or row_response.get("performanceMetrics")
        or {}
    )
    total_ms = perf.get("totalExecutionTime") or perf.get("total_execution_time_ms")
    response_ms = None
    if total_ms is not None:
        try:
            response_ms = float(total_ms)
        except (TypeError, ValueError):
            pass

    # RAG used
    rag_used = bool(agent_response.get("rag_used"))

    # Node-level stats
    state = row_response.get("state") or {}
    node_statuses_raw = (
        state.get("nodeExecutionStatus")
        or agent_response.get("nodeExecutionStatus")
        or {}
    )
    if isinstance(node_statuses_raw, dict):
        node_list = list(node_statuses_raw.values())
    else:
        node_list = node_statuses_raw if isinstance(node_statuses_raw, list) else []

    nodes = []
    for node in node_list:
        if not isinstance(node, dict):
            continue
        ntype = node.get("type") or node.get("node_type") or ""
        nstatus = (node.get("status") or "").lower()
        n_ms_raw = node.get("time_taken") or node.get("execution_time_ms")
        n_ms = None
        if n_ms_raw is not None:
            try:
                n_ms = float(n_ms_raw)
            except (TypeError, ValueError):
                pass
        nodes.append({
            "type": ntype,
            "is_success": nstatus in ("success", "completed"),
            "execution_ms": n_ms,
        })

    # Token usage and cost
    token_usage = agent_response.get("token_usage") or {}
    input_tokens = token_usage.get("input_tokens")
    output_tokens = token_usage.get("output_tokens")
    cost_usd = agent_response.get("cost_usd")

    return {
        "agent_id": agent_id,
        "stat_date": datetime.now(timezone.utc).date(),
        "is_success": is_success,
        "response_ms": response_ms,
        "rag_used": rag_used,
        "total_nodes_executed": len(nodes),
        "nodes": nodes,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }


# ---------------------------------------------------------------------------
# Public entry points (called via asyncio.create_task)
# ---------------------------------------------------------------------------


async def update_stats_incrementally(agent_response: dict) -> None:
    """
    Fired after each agent_response_log is saved.
    Increments execution counters and timing stats.
    """
    try:
        from app.core.utils.db_connection_utils import create_tenant_request_scope
        from app.dependencies.injector import injector
        from app.repositories.analytics_aggregation import AnalyticsAggregationRepository

        data = parse_agent_response_for_stats(agent_response)
        if data is None:
            return

        async with create_tenant_request_scope():
            session = injector.get(AsyncSession)
            try:
                repo = AnalyticsAggregationRepository(session)
                await repo.increment_agent_daily_stats(data)
                await repo.increment_node_daily_stats(data)
                await session.commit()
                logger.debug(
                    "Incremental analytics update for agent %s", data["agent_id"]
                )
            finally:
                await session.close()

    except Exception:
        logger.warning(
            "Incremental analytics update failed (Celery will reconcile)",
            exc_info=True,
        )


async def update_conversation_started(agent_id: UUID) -> None:
    """Fired when a new conversation starts. Increments unique + in_progress."""
    try:
        from app.core.utils.db_connection_utils import create_tenant_request_scope
        from app.dependencies.injector import injector
        from app.repositories.analytics_aggregation import AnalyticsAggregationRepository

        async with create_tenant_request_scope():
            session = injector.get(AsyncSession)
            try:
                repo = AnalyticsAggregationRepository(session)
                await repo.increment_conversation_counts(agent_id, "start")
                await session.commit()
                logger.debug("Conversation started for agent %s", agent_id)
            finally:
                await session.close()

    except Exception:
        logger.warning(
            "Conversation start analytics update failed (Celery will reconcile)",
            exc_info=True,
        )


async def update_conversation_finalized(conversation_id: UUID) -> None:
    """Fired when a conversation is finalized. Looks up agent_id, then increments."""
    try:
        from app.core.utils.db_connection_utils import create_tenant_request_scope
        from app.dependencies.injector import injector
        from app.repositories.analytics_aggregation import AnalyticsAggregationRepository

        async with create_tenant_request_scope():
            session = injector.get(AsyncSession)
            try:
                repo = AnalyticsAggregationRepository(session)
                agent_id = await repo.get_agent_id_for_conversation(conversation_id)
                if agent_id is None:
                    return
                await repo.increment_conversation_counts(agent_id, "finalize")
                await session.commit()
                logger.debug("Conversation finalized for agent %s", agent_id)
            finally:
                await session.close()

    except Exception:
        logger.warning(
            "Conversation finalize analytics update failed (Celery will reconcile)",
            exc_info=True,
        )


async def update_feedback_given(conversation_id: UUID, is_thumbs_up: bool) -> None:
    """Fired when feedback is given on a message. Increments thumbs counters."""
    try:
        from app.core.utils.db_connection_utils import create_tenant_request_scope
        from app.dependencies.injector import injector
        from app.repositories.analytics_aggregation import AnalyticsAggregationRepository

        async with create_tenant_request_scope():
            session = injector.get(AsyncSession)
            try:
                repo = AnalyticsAggregationRepository(session)
                agent_id = await repo.get_agent_id_for_conversation(conversation_id)
                if agent_id is None:
                    return
                await repo.increment_thumbs(agent_id, is_thumbs_up)
                await session.commit()
                logger.debug(
                    "Feedback (%s) recorded for agent %s",
                    "thumbs_up" if is_thumbs_up else "thumbs_down",
                    agent_id,
                )
            finally:
                await session.close()

    except Exception:
        logger.warning(
            "Feedback analytics update failed (Celery will reconcile)",
            exc_info=True,
        )
