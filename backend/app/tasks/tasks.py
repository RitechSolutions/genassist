import asyncio
import json
from celery import Task
from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.llm_analysts import LlmAnalystRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.repositories.operator_statistics import OperatorStatisticsRepository
from app.services.conversation_analysis import ConversationAnalysisService
from app.services.gpt_kpi_analyzer import GptKpiAnalyzer
from app.services.llm_analysts import LlmAnalystService
from app.services.operator_statistics import OperatorStatisticsService
from app.tasks import celery_app
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import select, and_
from app.db.models.conversation import ConversationModel
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.conversations import ConversationService
from app.db.seed.seed_data_config import seed_test_data

logger = logging.getLogger(__name__)

class BaseTaskWithLogging(Task):
    """Base task class that adds logging and error handling."""
    
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {task_id} completed successfully")
        return super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")
        return super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Task {task_id} is being retried: {exc}")
        return super().on_retry(exc, task_id, args, kwargs, einfo)

@celery_app.task(base=BaseTaskWithLogging)
def example_periodic_task():
    """Example periodic task that runs every hour."""
    logger.info(f"Running periodic task at {datetime.utcnow()}")
    # Add your task logic here
    return {"status": "completed", "timestamp": datetime.utcnow().isoformat()}

@celery_app.task(base=BaseTaskWithLogging)
def long_running_task(duration: int = 60):
    """Example of a long-running task."""
    logger.info(f"Starting long running task for {duration} seconds")
    # Simulate work
    import time
    time.sleep(duration)
    return {"status": "completed", "duration": duration}

@celery_app.task(base=BaseTaskWithLogging)
def cleanup_stale_conversations():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(cleanup_stale_conversations_async0())

async def cleanup_stale_conversations_async0():
    async for db in get_db():
        await cleanup_stale_conversations_async(db)

async def cleanup_stale_conversations_async(db: AsyncSession):
    """Clean up conversations that have been in 'in_progress' status for more than 5 minutes without updates."""
    logger.info("Starting cleanup of stale conversations")

    conversation_service = ConversationService(
        conversation_repo=ConversationRepository(db),
        gpt_kpi_analyzer_service=GptKpiAnalyzer(),
        conversation_analysis_service=ConversationAnalysisService(
            repository=ConversationAnalysisRepository(db)
        ),
        operator_statistics_service=OperatorStatisticsService(
            repository=OperatorStatisticsRepository(db)
        ),
        llm_analyst_service=LlmAnalystService(
            repository=LlmAnalystRepository(db),
            llm_provider_repository=LlmProviderRepository(db)
        )
    )

    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    stale_conversations = await conversation_service.get_stale_conversations(cutoff_time)
    print(f"Got {len(stale_conversations)} stale conversations for cutoff time {cutoff_time}")

    deleted_count = 0
    finalized_count = 0
    failed_count = 0

    for conversation in stale_conversations:
        try:
            # Parse the transcription to count messages
            transcription = json.loads(conversation.transcription)
            message_count = len(transcription)
            
            if message_count < 3:
                # Delete conversations with less than 3 messages
                await conversation_service.delete_conversation(conversation.id)
                deleted_count += 1
                logger.info(f"Deleted stale conversation {conversation.id} (last updated: {conversation.updated_at})")
            else:
                # Finalize conversations with 3 or more messages
                await conversation_service.finalize_in_progress_conversation(
                    llm_analyst_id=seed_test_data.llm_analyst_kpi_analyzer_id,
                    conversation_id=conversation.id
                )
                finalized_count += 1
                logger.info(f"Finalized conversation {conversation.id} (last updated: {conversation.updated_at})")
        except Exception as e:
            logger.error(f"Failed to process conversation {conversation.id}: {str(e)}")
            failed_count += 1

    result = {
        "status": "completed",
        "deleted_count": deleted_count,
        "finalized_count": finalized_count,
        "failed_count": failed_count
    }
    
    logger.info(f"Cleanup of stale conversations completed: {result}")
    return result
# Add more tasks as needed 