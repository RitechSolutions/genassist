"""
Real-time incremental analytics update.

Each event merges its delta into a per-process bucket keyed by (tenant, agent_id,
stat_date), and one flusher per key writes the merged delta in one transaction.
A delta lost to a crash or to two failed flushes is not retried; the batch rebuild
restores every column except the token/cost totals.

Data access lives in AnalyticsAggregationRepository; this module handles parsing
of the raw agent_response payload and orchestration (tenant scope + commit).
"""

import asyncio
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_scope import get_tenant_context, set_tenant_context
from app.core.utils.background_tasks import spawn
from app.repositories.analytics_aggregation import AnalyticsAggregationRepository, ExecutionDelta, StatsDelta

logger = logging.getLogger(__name__)

_pending: dict[tuple[str, UUID, date], StatsDelta] = {}
_flushers: dict[tuple[str, UUID, date], asyncio.Task] = {}


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
    # "partial" answered although a node failed - see analytics_aggregation
    is_success = status in ("success", "completed", "partial")

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


async def _fail_fast_on_row_lock(session: AsyncSession, timeout_ms: int = 2000) -> None:
    """
    Bounds each lock attempt, not the statement: a flush stuck behind one long
    holder (another process's flush or the batch rebuild) fails after 2 s and is
    retried once, instead of holding its connection until statement_timeout.
    """
    await session.execute(text(f"SET LOCAL lock_timeout = '{timeout_ms}ms'"))


def _turn_delta(data: dict) -> StatsDelta:
    nodes = data["nodes"]
    delta = StatsDelta(
        events=1,
        nodes_executed=data["total_nodes_executed"],
        rag_used=int(data["rag_used"]),
        input_tokens=int(data.get("input_tokens") or 0),
        output_tokens=int(data.get("output_tokens") or 0),
        cost_usd=float(data.get("cost_usd") or 0.0),
    )
    delta.add(data["is_success"], data["response_ms"])
    if nodes:
        delta.rated = 1
        delta.success_rate_sum = sum(1 for n in nodes if n["is_success"]) / len(nodes)
    for node in nodes:
        delta.nodes.setdefault(node["type"], ExecutionDelta()).add(node["is_success"], node["execution_ms"])
    return delta


def _merge(agent_id: UUID, stat_date: date, delta: StatsDelta) -> None:
    key = (get_tenant_context(), agent_id, stat_date)
    if (pending := _pending.get(key)) is None:
        _pending[key] = delta
    else:
        pending.merge(delta)
    flusher = _flushers.get(key)
    if flusher is None or flusher.done():
        _flushers[key] = spawn(_flush(key), name=f"analytics:flush:{agent_id}:{stat_date}")


async def _flush(key: tuple[str, UUID, date]) -> None:
    tenant, agent_id, stat_date = key
    set_tenant_context(tenant)
    retrying = False
    try:
        while (delta := _pending.pop(key, None)) is not None:
            try:
                await _write(agent_id, stat_date, delta)
                retrying = False
            except Exception as exc:
                if retrying:
                    logger.warning(
                        "Analytics flush failed twice (%s), dropped %d event(s)",
                        type(exc).__name__,
                        delta.events,
                        exc_info=True,
                    )
                    retrying = False
                    continue
                logger.info("Analytics flush failed (%s), retrying once", type(exc).__name__)
                retrying = True
                if (newer := _pending.pop(key, None)) is not None:
                    delta.merge(newer)
                _pending[key] = delta
    finally:
        _flushers.pop(key, None)


async def _write(agent_id: UUID, stat_date: date, delta: StatsDelta) -> None:
    from app.core.utils.db_connection_utils import create_tenant_request_scope
    from app.dependencies.injector import injector

    async with create_tenant_request_scope():
        session = injector.get(AsyncSession)
        try:
            await _fail_fast_on_row_lock(session)
            repo = AnalyticsAggregationRepository(session)
            await repo.increment_agent_daily_stats(agent_id, stat_date, delta)
            await repo.increment_node_daily_stats(agent_id, stat_date, delta.nodes)
            await session.commit()
            logger.debug("Flushed %d analytics event(s) for agent %s", delta.events, agent_id)
        finally:
            await session.close()


async def _agent_id_for(conversation_id: UUID) -> UUID | None:
    from app.core.utils.db_connection_utils import create_tenant_request_scope
    from app.dependencies.injector import injector

    async with create_tenant_request_scope():
        session = injector.get(AsyncSession)
        try:
            return await AnalyticsAggregationRepository(session).get_agent_id_for_conversation(conversation_id)
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Public entry points (called via asyncio.create_task)
# ---------------------------------------------------------------------------


async def update_stats_incrementally(agent_response: dict) -> None:
    """
    Fired after each agent_response_log is saved.
    Increments execution counters and timing stats.
    """
    try:
        data = parse_agent_response_for_stats(agent_response)
        if data is None:
            return
        _merge(data["agent_id"], data["stat_date"], _turn_delta(data))

    except Exception:
        logger.warning(
            "Incremental analytics update failed (Celery will reconcile)",
            exc_info=True,
        )


async def update_conversation_started(agent_id: UUID) -> None:
    """Fired when a new conversation starts. Increments unique + in_progress."""
    try:
        _merge(agent_id, datetime.now(timezone.utc).date(), StatsDelta(events=1, starts=1))

    except Exception:
        logger.warning(
            "Conversation start analytics update failed (Celery will reconcile)",
            exc_info=True,
        )


async def update_conversation_finalized(conversation_id: UUID) -> None:
    """Fired when a conversation is finalized. Looks up agent_id, then increments."""
    try:
        stat_date = datetime.now(timezone.utc).date()
        agent_id = await _agent_id_for(conversation_id)
        if agent_id is None:
            return
        _merge(agent_id, stat_date, StatsDelta(events=1, finalizes=1))

    except Exception:
        logger.warning(
            "Conversation finalize analytics update failed (Celery will reconcile)",
            exc_info=True,
        )


async def update_feedback_given(conversation_id: UUID, is_thumbs_up: bool) -> None:
    """Fired when feedback is given on a message. Increments thumbs counters."""
    try:
        stat_date = datetime.now(timezone.utc).date()
        agent_id = await _agent_id_for(conversation_id)
        if agent_id is None:
            return
        thumbs = StatsDelta(events=1, thumbs_up=int(is_thumbs_up), thumbs_down=int(not is_thumbs_up))
        _merge(agent_id, stat_date, thumbs)

    except Exception:
        logger.warning(
            "Feedback analytics update failed (Celery will reconcile)",
            exc_info=True,
        )
