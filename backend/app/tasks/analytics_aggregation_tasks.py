import logging

from celery import shared_task

from app.tasks.base import run_async_in_celery

logger = logging.getLogger(__name__)


@shared_task
def aggregate_agent_analytics():
    return run_async_in_celery(
        aggregate_agent_analytics_async_with_scope(),
        timeout=110 * 60,
        task_name="aggregate_agent_analytics",
    )


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


@shared_task
def backfill_agent_analytics(
    tenant_id: str, from_date: str | None = None, to_date: str | None = None
):
    """One-time backfill task (run manually, not on the beat schedule).

    Recomputes agent and node daily stats from scratch so that columns added to
    the stats tables after rows were first aggregated — e.g. ``unique_conversations``
    / thumbs counts on ``node_execution_daily_stats`` (migration 00050) — get
    populated instead of staying at their ``0`` default. The recurring
    ``aggregate_agent_analytics`` task only reprocesses dates with new logs, so
    historical rows are never otherwise revisited.

    Runs for a SINGLE tenant only — ``tenant_id`` is the caller's tenant slug
    (from the request's tenant context). ``from_date`` / ``to_date`` are inclusive
    ISO date strings (``YYYY-MM-DD``) bounding the window to recompute; omit either
    to run open-ended. At large scale, run it in slices (e.g. one month per call).
    Idempotent — upserts overwrite, so it is safe to re-run or re-slice.
    """
    return run_async_in_celery(
        backfill_agent_analytics_async_with_scope(
            tenant_id=tenant_id, from_date=from_date, to_date=to_date
        ),
        timeout=110 * 60,
        task_name="backfill_agent_analytics",
    )


async def backfill_agent_analytics_async_with_scope(
    tenant_id: str, from_date: str | None = None, to_date: str | None = None
):
    """Wrapper to run the analytics backfill for the caller's tenant only."""
    from app.tasks.base import run_task_for_tenant

    return await run_task_for_tenant(
        backfill_agent_analytics_async,
        "agent analytics backfill",
        tenant_id,
        from_date=from_date,
        to_date=to_date,
    )


async def backfill_agent_analytics_async(
    from_date: str | None = None, to_date: str | None = None
):
    """Full re-aggregation of agent and node daily stats from agent_response_logs."""
    from datetime import date

    from app.dependencies.injector import injector
    from app.services.analytics_aggregation import AnalyticsAggregationService

    fd = date.fromisoformat(from_date) if from_date else None
    td = date.fromisoformat(to_date) if to_date else None

    logger.info(f"Starting agent analytics backfill (from={fd}, to={td})")
    svc = injector.get(AnalyticsAggregationService)
    result = await svc.aggregate_daily_stats(force_full=True, from_date=fd, to_date=td)
    logger.info(f"Agent analytics backfill completed: {result}")
    return {"status": "completed", **result}
