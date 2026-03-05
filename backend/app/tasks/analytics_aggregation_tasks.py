import asyncio
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def aggregate_agent_analytics():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(aggregate_agent_analytics_async_with_scope())


async def aggregate_agent_analytics_async_with_scope():
    """Wrapper to run analytics aggregation for all tenants."""
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        aggregate_agent_analytics_async,
        "agent analytics aggregation",
    )


async def aggregate_agent_analytics_async():
    """Aggregate agent and node daily stats from agent_response_logs."""
    from app.dependencies.injector import injector
    from app.services.analytics_aggregation import AnalyticsAggregationService

    logger.info("Starting agent analytics aggregation")
    svc = injector.get(AnalyticsAggregationService)
    result = await svc.aggregate_daily_stats()
    logger.info(f"Agent analytics aggregation completed: {result}")
    return {"status": "completed", **result}
