"""
Real-time incremental analytics update.

Fired as a background asyncio.create_task after each agent_response_log is saved.
If this fails, the Celery worker's next run does a full recount — no data is lost.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import generate_sequential_uuid
from app.db.models.agent import AgentModel
from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.conversation import ConversationModel
from app.db.models.node_execution_daily_stats import NodeExecutionDailyStatsModel

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

    return {
        "agent_id": agent_id,
        "stat_date": datetime.now(timezone.utc).date(),
        "is_success": is_success,
        "response_ms": response_ms,
        "rag_used": rag_used,
        "total_nodes_executed": len(nodes),
        "nodes": nodes,
    }


async def _increment_agent_daily_stats(session: AsyncSession, data: dict) -> None:
    """
    Upsert a single execution's contribution into agent_execution_daily_stats
    using INSERT ... ON CONFLICT DO UPDATE with atomic += increments.
    """
    now = datetime.now(timezone.utc)
    response_ms = data["response_ms"]
    nodes = data["nodes"]

    # Compute per-execution node success rate
    node_success_rate = None
    if nodes:
        success_nodes = sum(1 for n in nodes if n["is_success"])
        node_success_rate = success_nodes / len(nodes)

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
        "last_aggregated_at": stmt.excluded.last_aggregated_at,
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
    await session.execute(stmt)


async def _increment_node_daily_stats(session: AsyncSession, data: dict) -> None:
    """
    Upsert each node's contribution into node_execution_daily_stats
    using INSERT ... ON CONFLICT DO UPDATE with atomic += increments.
    """
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
        await session.execute(stmt)


async def _increment_conversation_counts(
    session: AsyncSession, agent_id: UUID, event: str,
) -> None:
    """
    Increment conversation counters on agent_execution_daily_stats.

    event: "start" → unique_conversations += 1, in_progress_conversations += 1
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
            "updated_at": stmt.excluded.updated_at,
        }
    else:  # finalize
        update_set = {
            "finalized_conversations": tbl.c.finalized_conversations + 1,
            "in_progress_conversations": func.greatest(
                tbl.c.in_progress_conversations - 1, 0
            ),
            "updated_at": stmt.excluded.updated_at,
        }

    stmt = stmt.on_conflict_do_update(
        constraint="uq_agent_execution_daily_stats_agent_date",
        set_=update_set,
    )
    await session.execute(stmt)


async def _get_agent_id_for_conversation(
    session: AsyncSession, conversation_id: UUID,
) -> UUID | None:
    """Look up the agent_id for a conversation via its operator_id."""
    result = await session.execute(
        select(ConversationModel.operator_id).where(
            ConversationModel.id == conversation_id
        )
    )
    operator_id = result.scalar_one_or_none()
    if not operator_id:
        return None

    result = await session.execute(
        select(AgentModel.id).where(AgentModel.operator_id == operator_id)
    )
    return result.scalar_one_or_none()


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

        data = parse_agent_response_for_stats(agent_response)
        if data is None:
            return

        async with create_tenant_request_scope():
            session = injector.get(AsyncSession)
            try:
                await _increment_agent_daily_stats(session, data)
                await _increment_node_daily_stats(session, data)
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

        async with create_tenant_request_scope():
            session = injector.get(AsyncSession)
            try:
                await _increment_conversation_counts(session, agent_id, "start")
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

        async with create_tenant_request_scope():
            session = injector.get(AsyncSession)
            try:
                agent_id = await _get_agent_id_for_conversation(
                    session, conversation_id
                )
                if agent_id is None:
                    return
                await _increment_conversation_counts(session, agent_id, "finalize")
                await session.commit()
                logger.debug(
                    "Conversation finalized for agent %s", agent_id
                )
            finally:
                await session.close()

    except Exception:
        logger.warning(
            "Conversation finalize analytics update failed (Celery will reconcile)",
            exc_info=True,
        )


async def _increment_thumbs(
    session: AsyncSession, agent_id: UUID, is_thumbs_up: bool,
) -> None:
    """
    Increment thumbs_up_count or thumbs_down_count on agent_execution_daily_stats.
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
            "updated_at": stmt.excluded.updated_at,
        }
    else:
        update_set = {
            "thumbs_down_count": tbl.c.thumbs_down_count + 1,
            "updated_at": stmt.excluded.updated_at,
        }

    stmt = stmt.on_conflict_do_update(
        constraint="uq_agent_execution_daily_stats_agent_date",
        set_=update_set,
    )
    await session.execute(stmt)


async def update_feedback_given(
    conversation_id: UUID, is_thumbs_up: bool,
) -> None:
    """Fired when feedback is given on a message. Increments thumbs counters."""
    try:
        from app.core.utils.db_connection_utils import create_tenant_request_scope
        from app.dependencies.injector import injector

        async with create_tenant_request_scope():
            session = injector.get(AsyncSession)
            try:
                agent_id = await _get_agent_id_for_conversation(
                    session, conversation_id
                )
                if agent_id is None:
                    return
                await _increment_thumbs(session, agent_id, is_thumbs_up)
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
