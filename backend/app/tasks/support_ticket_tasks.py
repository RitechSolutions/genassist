import asyncio
import logging

from celery import shared_task

from app.dependencies.injector import injector
from app.services.support_ticket_sync import SupportTicketSyncService

logger = logging.getLogger(__name__)


async def _process_outbox_for_tenant() -> dict:
    sync_service = injector.get(SupportTicketSyncService)
    processed = await sync_service.process_pending_outbox(limit=25)
    return {"processed": processed}


async def process_support_ticket_sync_outbox_async_with_scope():
    from app.tasks.base import run_task_with_tenant_support

    return await run_task_with_tenant_support(
        _process_outbox_for_tenant, "Support ticket ADO sync outbox"
    )


@shared_task
def process_support_ticket_sync_outbox_task():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(process_support_ticket_sync_outbox_async_with_scope())
