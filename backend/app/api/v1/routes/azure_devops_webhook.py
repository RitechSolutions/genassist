from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi_injector import Injected

from app.core.config.help_center_ado import get_help_center_webhook_secret
from app.schemas.support_ticket import AdoWebhookPayload
from app.services.support_ticket_sync import SupportTicketSyncService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Azure DevOps"])


def _extract_work_item_from_resource(resource: dict[str, Any]) -> tuple[Optional[int], dict[str, Any]]:
    work_item_id = resource.get("id") or resource.get("workItemId")
    revision = resource.get("revision") or {}
    fields = revision.get("fields") if isinstance(revision, dict) else None
    if not fields:
        fields = resource.get("fields") or {}
    if work_item_id is None and isinstance(resource.get("workItemId"), int):
        work_item_id = resource["workItemId"]
    try:
        wid = int(work_item_id) if work_item_id is not None else None
    except (TypeError, ValueError):
        wid = None
    return wid, fields if isinstance(fields, dict) else {}


@router.post("/webhook")
async def azure_devops_workitem_webhook(
    payload: AdoWebhookPayload,
    x_ado_webhook_secret: Optional[str] = Header(default=None, alias="X-ADO-Webhook-Secret"),
    sync_service: SupportTicketSyncService = Injected(SupportTicketSyncService),
):
    """Receive Azure DevOps Service Hook events (workitem.updated)."""
    expected_secret = get_help_center_webhook_secret()
    if expected_secret:
        if not x_ado_webhook_secret or x_ado_webhook_secret != expected_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    resource = payload.resource or {}
    work_item_id, fields = _extract_work_item_from_resource(resource)

    if not work_item_id:
        logger.warning("ADO webhook missing work item id: %s", payload.model_dump())
        return {"status": "ignored", "reason": "no work item id"}

    updated = await sync_service.apply_ado_webhook_update(work_item_id, fields)
    if not updated:
        return {"status": "ignored", "reason": "ticket not found"}
    return {"status": "ok", "ticket_id": str(updated.id)}
