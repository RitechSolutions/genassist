import asyncio
from celery import shared_task
from app.dependencies.injector import injector
from datetime import datetime, timedelta, timezone
import logging
from app.services.conversations import ConversationService
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


@shared_task
def backfill_missing_conversation_analyses():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(backfill_missing_conversation_analyses_with_scope())


async def backfill_missing_conversation_analyses_with_scope():
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        backfill_missing_conversation_analyses_async,
        "backfill missing conversation analyses",
    )


async def backfill_missing_conversation_analyses_async():
    """Re-run analysis for finalized conversations that have no analysis entry."""
    from app.repositories.conversations import ConversationRepository

    conversation_repo = injector.get(ConversationRepository)
    conversations = await conversation_repo.get_finalized_without_analysis()
    if not conversations:
        return None

    conversation_srv = injector.get(ConversationService)
    success_count = 0
    failed_count = 0
    for conv in conversations:
        try:
            await conversation_srv.re_analyze_conversation(conv.id)
            success_count += 1
            logger.info(f"Backfilled analysis for conversation {conv.id}")
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to backfill analysis for conversation {conv.id}: {e}")

    return {"backfilled": success_count, "failed": failed_count}


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

    # get the time cutoff from the settings
    time_cutoff = settings.CONVERSATION_CLEANUP_STALE_MINUTES or 30

    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_cutoff)
    cleanup_result = await conversation_srv.cleanup_stale_conversations(cutoff_time)

    result = {
        "status": "completed",
        "deleted_count": cleanup_result["deleted_count"],
        "finalized_count": cleanup_result["finalized_count"],
        "failed_count": cleanup_result["failed_count"],
    }

    logger.debug(f"Cleanup of stale conversations completed: {result}")
    return result