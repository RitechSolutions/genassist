import logging

from celery import shared_task

from app.tasks.base import run_async_in_celery

logger = logging.getLogger(__name__)


@shared_task
def backfill_llm_usage_ledger(tenant_id: str, force: bool = False):
    """One-time backfill of the LLM usage ledger from chat history (run manually,
    never on the beat schedule)"""
    return run_async_in_celery(
        backfill_llm_usage_ledger_with_scope(tenant_id=tenant_id, force=force),
        timeout=110 * 60,
        task_name="backfill_llm_usage_ledger",
    )


async def backfill_llm_usage_ledger_with_scope(tenant_id: str, force: bool = False):
    """Run the ledger backfill for the caller's tenant only"""
    from app.tasks.base import run_task_for_tenant

    return await run_task_for_tenant(
        backfill_llm_usage_ledger_async,
        "llm usage ledger backfill",
        tenant_id,
        force=force,
    )


async def backfill_llm_usage_ledger_async(force: bool = False):
    from app.dependencies.injector import injector
    from app.services.llm_usage_backfill import LlmUsageBackfillService

    logger.info("Starting LLM usage ledger backfill (force=%s)", force)
    service = injector.get(LlmUsageBackfillService)
    result = await service.run(force=force)
    logger.info("LLM usage ledger backfill finished: %s", result)
    return result
