import asyncio
import json
import logging

from celery import shared_task

from app.core.utils.custom_attributes import extract_custom_attributes_from_state

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


@shared_task
def backfill_custom_attributes(force: bool = False):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(backfill_custom_attributes_async_with_scope(force=force))


async def backfill_custom_attributes_async_with_scope(force: bool = False):
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        backfill_custom_attributes_async,
        "backfill custom attributes",
        force=force,
    )


async def backfill_custom_attributes_async(force: bool = False):
    """Backfill custom_attributes on conversations from agent_response_logs.

    Args:
        force: If True, re-process all conversations (even those with existing attributes).
               If False (default), only process conversations where custom_attributes IS NULL.
    """
    from sqlalchemy import select, update, func
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.agent_response_log import AgentResponseLogModel
    from app.db.models.conversation import ConversationModel
    from app.dependencies.injector import injector

    db: AsyncSession = injector.get(AsyncSession)

    total_updated = 0
    offset = 0
    mode = "force (re-process all)" if force else "incremental (NULL only)"
    logger.info(f"Backfill mode: {mode}")

    while True:
        stmt = (
            select(ConversationModel.id)
            .order_by(ConversationModel.id)
            .offset(offset)
            .limit(BATCH_SIZE)
        )
        if not force:
            stmt = stmt.where(ConversationModel.custom_attributes.is_(None))
        result = await db.execute(stmt)
        conversation_ids = [row[0] for row in result.all()]

        if not conversation_ids:
            break

        # Batch-fetch the latest log per conversation (avoids N+1)
        latest_log_subq = (
            select(
                AgentResponseLogModel.conversation_id,
                func.max(AgentResponseLogModel.logged_at).label("max_logged_at"),
            )
            .where(AgentResponseLogModel.conversation_id.in_(conversation_ids))
            .group_by(AgentResponseLogModel.conversation_id)
            .subquery()
        )
        logs_stmt = (
            select(AgentResponseLogModel.conversation_id, AgentResponseLogModel.raw_response)
            .join(
                latest_log_subq,
                (AgentResponseLogModel.conversation_id == latest_log_subq.c.conversation_id)
                & (AgentResponseLogModel.logged_at == latest_log_subq.c.max_logged_at),
            )
        )
        logs_result = await db.execute(logs_stmt)
        logs_by_conv = {row[0]: row[1] for row in logs_result.all()}

        batch_updated = 0

        for conv_id in conversation_ids:
            log_row = logs_by_conv.get(conv_id)
            if not log_row:
                if force:
                    await db.execute(
                        update(ConversationModel)
                        .where(ConversationModel.id == conv_id)
                        .values(custom_attributes=None)
                    )
                continue

            try:
                payload = json.loads(log_row) if isinstance(log_row, str) else log_row
                node_statuses = (
                    payload.get("row_agent_response", {})
                    .get("state", {})
                    .get("nodeExecutionStatus", {})
                )
                attrs = extract_custom_attributes_from_state(node_statuses)

                if attrs:
                    await db.execute(
                        update(ConversationModel)
                        .where(ConversationModel.id == conv_id)
                        .values(custom_attributes=attrs)
                    )
                    batch_updated += 1
                elif force:
                    await db.execute(
                        update(ConversationModel)
                        .where(ConversationModel.id == conv_id)
                        .values(custom_attributes=None)
                    )

            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logger.debug(f"Skipping conversation {conv_id}: {e}")
                continue

        await db.commit()
        total_updated += batch_updated
        offset += BATCH_SIZE
        logger.info(
            f"Backfill progress: processed {offset} conversations, "
            f"updated {total_updated} so far"
        )

    logger.info(f"Backfill complete: updated {total_updated} conversations")
    return {"status": "completed", "updated": total_updated}
