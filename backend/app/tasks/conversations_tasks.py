import asyncio
import json
from celery import Task, shared_task
from app.dependencies.injector import injector
from datetime import datetime, timedelta, timezone
import logging
from app.services.conversations import ConversationService
from app.db.seed.seed_data_config import seed_test_data
from app.tasks.base import BaseTaskWithLogging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_stale_conversations():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(cleanup_stale_conversations_async_with_scope())


async def cleanup_stale_conversations_async_with_scope():
    """Wrapper to run cleanup for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        cleanup_stale_conversations_async,
        "cleanup of stale conversations"
    )


async def cleanup_stale_conversations_async():
    """Clean up conversations that have been in 'in_progress' status for more than 5 minutes without updates."""
    logger.info("Starting cleanup of stale conversations")

    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    stale_conversations = await injector.get(
        ConversationService
    ).get_stale_conversations(cutoff_time)
    print(
        f"Got {len(stale_conversations)} stale conversations for cutoff time {cutoff_time}"
    )

    deleted_count = 0
    finalized_count = 0
    failed_count = 0

    for conversation in stale_conversations:
        try:
            message_count = len(conversation.messages)

            if message_count < 3:
                # Delete conversations with less than 3 messages
                await injector.get(ConversationService).delete_conversation(
                    conversation.id
                )
                deleted_count += 1
                logger.info(
                    f"Deleted stale conversation {conversation.id} (last updated: {conversation.updated_at})"
                )
            else:
                # Finalize conversations with 3 or more messages
                await injector.get(
                    ConversationService
                ).finalize_in_progress_conversation(
                    llm_analyst_id=seed_test_data.llm_analyst_kpi_analyzer_id,
                    conversation_id=conversation.id,
                )
                finalized_count += 1
                logger.info(
                    f"Finalized conversation {conversation.id} (last updated: {conversation.updated_at})"
                )
        except Exception as e:
            logger.error(f"Failed to process conversation {conversation.id}: {str(e)}")
            failed_count += 1

    result = {
        "status": "completed",
        "deleted_count": deleted_count,
        "finalized_count": finalized_count,
        "failed_count": failed_count,
    }

    logger.info(f"Cleanup of stale conversations completed: {result}")
    return result


# Add more tasks as needed
