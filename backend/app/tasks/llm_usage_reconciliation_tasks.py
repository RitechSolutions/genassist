import logging

from celery import shared_task

from app.tasks.base import run_async_in_celery

logger = logging.getLogger(__name__)


@shared_task
def reconcile_llm_usage_shadow():
    """Daily shadow reconciliation for every tenant. Inert until a tenant starts shadow.

    Monitoring continues after a tenant passes — only the pass stamp is once-only —
    so the job keeps re-evaluating missing, failed and re-gated days."""
    return run_async_in_celery(
        reconcile_llm_usage_shadow_with_scope(),
        timeout=110 * 60,
        task_name="reconcile_llm_usage_shadow",
    )


async def reconcile_llm_usage_shadow_with_scope():
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        reconcile_llm_usage_shadow_async,
        "llm usage shadow reconciliation",
    )


@shared_task
def reconcile_llm_usage_shadow_for_tenant(tenant_id: str):
    """Manual reconciliation for a single tenant (the caller's)."""
    return run_async_in_celery(
        reconcile_llm_usage_shadow_for_tenant_with_scope(tenant_id=tenant_id),
        timeout=110 * 60,
        task_name="reconcile_llm_usage_shadow_for_tenant",
    )


async def reconcile_llm_usage_shadow_for_tenant_with_scope(tenant_id: str):
    from app.tasks.base import run_task_for_tenant

    return await run_task_for_tenant(
        reconcile_llm_usage_shadow_async,
        "llm usage shadow reconciliation",
        tenant_id,
    )


async def reconcile_llm_usage_shadow_async():
    from app.dependencies.injector import injector
    from app.services.llm_usage_reconciliation import LlmUsageReconciliationService

    service = injector.get(LlmUsageReconciliationService)
    result = await service.reconcile()
    logger.info("Shadow reconciliation result: %s", result)
    return result
