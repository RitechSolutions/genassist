# app/api/v1/routes/webhooks_execute_router.py

from fastapi import APIRouter, Request, Query, Header, status
from uuid import UUID
from app.services.webhook import WebhookService
from app.core.tenant_scope import get_tenant_context
from fastapi_injector import Injected
from typing import Optional

router = APIRouter()

@router.post(
    "/{webhook_id}",
    name="webhook_handler_post",
    status_code=status.HTTP_200_OK,
)
async def webhook_handler_post(
    webhook_id: UUID,
    request: Request,
    service: WebhookService = Injected(WebhookService),
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    x_slack_signature: Optional[str] = Header(None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: Optional[str] = Header(None, alias="X-Slack-Request-Timestamp"),
):
    body = await request.body()
    body_str = body.decode("utf-8") or "{}"
    tenant_id = get_tenant_context()
    return await service.validate_webhook_request_and_execute(
        webhook_id,
        request,
        body_str,
        tenant_id=tenant_id,
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge,
        x_slack_signature=x_slack_signature,
        x_slack_request_timestamp=x_slack_request_timestamp
    )

@router.get(
    "/{webhook_id}",
    name="webhook_handler_get",
    status_code=status.HTTP_200_OK,
)
async def webhook_handler_get(
    webhook_id: UUID,
    request: Request,
    service: WebhookService = Injected(WebhookService),
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    body = await request.body()
    body_str = body.decode("utf-8") or "{}"
    tenant_id = get_tenant_context()
    return await service.validate_webhook_request_and_execute(
        webhook_id,
        request,
        body_str,
        tenant_id=tenant_id,
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge
    )
