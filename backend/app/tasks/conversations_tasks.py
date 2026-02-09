import asyncio
from celery import shared_task
from app.dependencies.injector import injector
from datetime import datetime, timedelta, timezone
import logging
from app.services.conversations import ConversationService

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
    conversation_srv = injector.get(ConversationService)


    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    cleanup_result = await conversation_srv.cleanup_stale_conversations(cutoff_time)

    result = {
        "status": "completed",
        "deleted_count": cleanup_result["deleted_count"],
        "finalized_count": cleanup_result["finalized_count"],
        "failed_count": cleanup_result["failed_count"],
    }

    logger.debug(f"Cleanup of stale conversations completed: {result}")
    return result