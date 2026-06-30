"""Celery tasks for asynchronous email delivery.

``send_email_task`` is a thin wrapper around :class:`EmailService`. It exists so
callers (HTTP handlers, services, other tasks) can fire-and-forget an email
without blocking on SMTP latency, and so transient SMTP failures (greylisting,
timeouts) are retried automatically.

Inline alternative: anywhere you already have an EmailService instance you can
``await email_service.send_template(...)`` directly. Use this task when you want
the request to return immediately and/or want retries.

Usage::

    from app.tasks.email_tasks import send_email_task

    send_email_task.delay(
        tenant_slug="acme",
        to="user@example.com",
        subject="Reset your password",
        template_name="generic_notification",
        context={"heading": "Reset your password", "cta_url": url, "cta_label": "Reset"},
    )
"""

import logging
from typing import Any, Dict, List, Optional, Union

from celery import shared_task

from app.tasks.base import run_async_in_celery

logger = logging.getLogger(__name__)


async def _send_for_tenant(
    tenant_slug: Optional[str],
    to: Union[str, List[str]],
    subject: str,
    template_name: str,
    context: Optional[Dict[str, Any]],
    cc: Optional[List[str]],
    bcc: Optional[List[str]],
) -> Dict[str, Any]:
    # Imported lazily so the Celery master process doesn't import the DI graph at fork time.
    from fastapi_injector import RequestScopeFactory

    from app.core.tenant_scope import clear_tenant_context, set_tenant_context
    from app.dependencies.injector import injector
    from app.services.email import EmailService

    # Tenant context must be set before the request scope is created so the
    # correct tenant DB session is resolved for AppSettings lookups.
    if tenant_slug:
        set_tenant_context(tenant_slug)
    else:
        clear_tenant_context()

    request_scope_factory = injector.get(RequestScopeFactory)
    try:
        async with request_scope_factory.create_scope():
            email_service = injector.get(EmailService)
            return await email_service.send_template(
                to=to,
                subject=subject,
                template_name=template_name,
                context=context,
                cc=cc,
                bcc=bcc,
            )
    finally:
        clear_tenant_context()


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_email_task(
    self,
    to: Union[str, List[str]],
    subject: str,
    template_name: str,
    context: Optional[Dict[str, Any]] = None,
    tenant_slug: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Render ``template_name`` and send it for the given tenant. Retries on failure."""
    try:
        return run_async_in_celery(
            _send_for_tenant(tenant_slug, to, subject, template_name, context, cc, bcc),
            timeout=60,
            task_name="send_email_task",
        )
    except Exception as exc:
        logger.warning(
            "send_email_task failed (attempt %s/%s): %s",
            self.request.retries + 1,
            self.max_retries + 1,
            type(exc).__name__,
        )
        raise self.retry(exc=exc)