import logging

from celery import shared_task

from app.core.utils.date_time_utils import utc_now
from app.dependencies.injector import injector
from app.services.bedrock_fine_tuning import BedrockFineTuningService
from app.tasks.base import run_async_in_celery

logger = logging.getLogger(__name__)


@shared_task
def sync_active_bedrock_fine_tuning_jobs():
    """Celery task entry point for syncing active Bedrock fine-tuning jobs."""
    return run_async_in_celery(
        sync_active_bedrock_fine_tuning_jobs_async_with_scope(),
        timeout=300,
        task_name="sync_active_bedrock_fine_tuning_jobs",
    )


async def sync_active_bedrock_fine_tuning_jobs_async_with_scope():
    """Wrapper to run sync for all tenants."""
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        sync_active_bedrock_fine_tuning_jobs_async,
        "sync of active Bedrock fine-tuning jobs",
    )


async def sync_active_bedrock_fine_tuning_jobs_async():
    """
    Sync active Bedrock customization jobs and in-progress deployments.

    Reuses the same logic as the UI Sync button: ``get_jobs(sync=True)`` refreshes
    every IN_PROGRESS/STOPPING customization job and any deployment still in the
    CREATING state (deployments are created after a job completes, so they must be
    covered here too — not just active jobs).
    """
    logger.info("Starting sync of active Bedrock fine-tuning jobs")

    service = injector.get(BedrockFineTuningService)
    jobs = await service.get_jobs(sync=True)

    result = {
        "status": "completed",
        "total_jobs": len(jobs),
        "timestamp": utc_now().isoformat(),
    }
    logger.info(f"Sync of active Bedrock fine-tuning jobs completed: {result}")
    return result
