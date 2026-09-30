from celery import shared_task
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies.injector import injector
from datetime import datetime, timedelta, timezone
import logging
from app.services.conversations import ConversationService
from app.core.config.settings import settings
from app.tasks.base import run_async_in_celery

logger = logging.getLogger(__name__)


@shared_task
def backfill_missing_conversation_analyses():
    return run_async_in_celery(
        backfill_missing_conversation_analyses_with_scope(),
        timeout=9 * 60,
        task_name="backfill_missing_conversation_analyses",
    )


async def backfill_missing_conversation_analyses_with_scope():
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        backfill_missing_conversation_analyses_async,
        "backfill missing conversation analyses",
    )


@asynccontextmanager
async def _conversation_scope():
    from app.core.utils.db_connection_utils import create_tenant_request_scope

    async with create_tenant_request_scope():
        session = injector.get(AsyncSession)
        try:
            yield
            await session.commit()
        finally:
            await session.close()


async def backfill_missing_conversation_analyses_async():
    """Re-run analysis for finalized conversations that have no analysis entry."""
    from app.core.utils.db_connection_utils import release_idle_connection
    from app.repositories.conversations import ConversationRepository

    max_attempts = settings.CONVERSATION_ANALYSIS_BACKFILL_MAX_ATTEMPTS
    conversation_repo = injector.get(ConversationRepository)
    conversations = await conversation_repo.get_finalized_without_analysis(
        max_attempts=max_attempts,
        max_age_days=settings.CONVERSATION_ANALYSIS_BACKFILL_MAX_AGE_DAYS,
        retry_delay_minutes=settings.CONVERSATION_ANALYSIS_BACKFILL_RETRY_DELAY_MINUTES,
    )
    if not conversations:
        return None

    candidates = [(conv.id, conv.analysis_attempts) for conv in conversations]
    await release_idle_connection(context="backfill missing conversation analyses")

    success_count = 0
    failed_count = 0
    capped_count = 0
    for conv_id, attempts_before in candidates:
        # Committed before the LLM work, so a run cancelled by the task timeout still counts
        async with _conversation_scope():
            await injector.get(ConversationRepository).mark_analysis_attempt(conv_id)
        try:
            async with _conversation_scope():
                await injector.get(ConversationService).re_analyze_conversation(conv_id)
                await injector.get(ConversationRepository).set_analysis_last_error(conv_id, None)
            success_count += 1
            logger.debug(f"Backfilled analysis for conversation {conv_id}")
        except Exception as e:
            failed_count += 1
            error = f"{type(e).__name__}: {e}"
            logger.error(f"Failed to backfill analysis for conversation {conv_id}: {e}")
            if attempts_before + 1 >= max_attempts:
                capped_count += 1
                logger.warning(
                    f"Analysis backfill gave up on conversation {str(conv_id)[:8]} "
                    f"after {max_attempts} attempts: {error}"
                )
            async with _conversation_scope():
                await injector.get(ConversationRepository).set_analysis_last_error(conv_id, error)

    return {"backfilled": success_count, "failed": failed_count, "capped": capped_count}


@shared_task
def cleanup_stale_conversations():
    return run_async_in_celery(
        cleanup_stale_conversations_async_with_scope(),
        timeout=9 * 60,
        task_name="cleanup_stale_conversations",
    )


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