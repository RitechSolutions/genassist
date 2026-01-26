import asyncio
import logging
from datetime import datetime
from celery import shared_task

from app.core.utils.date_time_utils import utc_now
from app.dependencies.injector import injector
from app.services.open_ai_fine_tuning import OpenAIFineTuningService
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus


logger = logging.getLogger(__name__)


@shared_task
def sync_active_fine_tuning_jobs():
    """Celery task entry point for syncing active fine-tuning jobs"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(sync_active_fine_tuning_jobs_async_with_scope())


async def sync_active_fine_tuning_jobs_async_with_scope():
    """Wrapper to run sync for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        sync_active_fine_tuning_jobs_async,
        "sync of active fine-tuning jobs"
    )


async def sync_active_fine_tuning_jobs_async():
    """
    Sync all active fine-tuning jobs with OpenAI API.
    Active jobs are those with status: validating_files, queued, or running.
    """
    logger.info("Starting sync of active fine-tuning jobs")

    service = injector.get(OpenAIFineTuningService)

    # Get all active jobs from database
    active_jobs = await service.repository.get_active_jobs()

    logger.info(f"Found {len(active_jobs)} active fine-tuning jobs to sync")

    synced_count = 0
    completed_count = 0
    failed_count = 0
    error_count = 0

    for job in active_jobs:
        try:
            logger.info(f"Syncing job {job.openai_job_id} (current status: {job.status})")

            # Fetch fresh data from OpenAI
            response = await service.client.fine_tuning.jobs.retrieve(job.openai_job_id)

            # Update database with fresh data
            await service.repository.update_job_status(
                    id=job.id,
                    status=JobStatus(response.status),
                    fine_tuned_model=response.fine_tuned_model,
                    finished_at=datetime.fromtimestamp(response.finished_at) if response.finished_at else None,
                    trained_tokens=response.trained_tokens,
                    error_message=response.error.message if response.error else None,
                    error_code=response.error.code if response.error else None
                    )
            await service.sync_events_for_active_jobs()

            synced_count += 1

            # Track completed jobs
            if response.status in ["succeeded", "failed", "cancelled"]:
                completed_count += 1
                logger.info(
                        f"Job {job.openai_job_id} reached terminal state: {response.status}"
                        )

            # Track failed jobs
            if response.status == "failed":
                error_count += 1
                error_msg = response.error.message if response.error else "Unknown error"
                logger.warning(
                        f"Job {job.openai_job_id} failed with error: {error_msg}"
                        )

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"Failed to sync job {job.openai_job_id}: {str(e)}")
            failed_count += 1

    result = {
        "status": "completed",
        "total_jobs": len(active_jobs),
        "synced_count": synced_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "error_count": error_count,
        "timestamp": utc_now().isoformat()
        }

    logger.info(f"Sync of active fine-tuning jobs completed: {result}")
    return result


@shared_task
def sync_all_fine_tuning_jobs():
    """Celery task to sync ALL fine-tuning jobs (not just active ones)"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(sync_all_fine_tuning_jobs_async_with_scope())


async def sync_all_fine_tuning_jobs_async_with_scope():
    """Wrapper to run full sync for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        sync_all_fine_tuning_jobs_async,
        "full sync of all fine-tuning jobs"
    )


async def sync_all_fine_tuning_jobs_async():
    """
    Sync ALL fine-tuning jobs with OpenAI API (including completed ones).
    Use this for periodic full reconciliation.
    """
    logger.info("Starting full sync of all fine-tuning jobs")

    service = injector.get(OpenAIFineTuningService)

    # Get all jobs from database (no status filter)
    all_jobs = await service.repository.list_jobs(status=None)

    logger.info(f"Found {len(all_jobs)} total fine-tuning jobs to sync")

    synced_count = 0
    failed_count = 0

    for job in all_jobs:
        try:
            logger.debug(f"Syncing job {job.openai_job_id}")

            await service.get_fine_tuning_job(job.id, sync=True)

            synced_count += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"Failed to sync job {job.openai_job_id}: {str(e)}")
            failed_count += 1

    result = {
        "status": "completed",
        "total_jobs": len(all_jobs),
        "synced_count": synced_count,
        "failed_count": failed_count,
        "timestamp": utc_now().isoformat()
        }

    logger.info(f"Full sync of fine-tuning jobs completed: {result}")
    return result