from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from injector import inject

from app.core.config.help_center_ado import (
    get_help_center_ado_connector,
    get_help_center_default_area_path,
    get_help_center_public_base_url,
)
from app.db.models.support_ticket import SupportTicketModel, TicketSyncOutboxModel
from app.modules.integration.azure_devops import AzureDevOpsConnector
from app.repositories.support_ticket import SupportTicketRepository

logger = logging.getLogger(__name__)


def _build_description_html(ticket: SupportTicketModel, app_base_url: str = "") -> str:
    env = ticket.environment or {}
    lines = [
        f"<p>{html.escape(ticket.description or '')}</p>",
        "<hr/>",
        f"<p><strong>GenAssist ticket:</strong> {html.escape(str(ticket.id))}</p>",
    ]
    if app_base_url:
        lines.append(
            f'<p><a href="{html.escape(app_base_url)}/help-center/{ticket.id}">Open in Help Center</a></p>'
        )
    if env:
        lines.append("<p><strong>Environment</strong></p><ul>")
        for key, value in env.items():
            if value:
                lines.append(f"<li>{html.escape(str(key))}: {html.escape(str(value))}</li>")
        lines.append("</ul>")
    return "\n".join(lines)


@inject
class SupportTicketSyncService:
    def __init__(self, ticket_repo: SupportTicketRepository):
        self.ticket_repo = ticket_repo

    async def process_outbox_entry(self, entry: TicketSyncOutboxModel) -> None:
        entry.status = "processing"
        entry.attempts = (entry.attempts or 0) + 1
        await self.ticket_repo.db.commit()

        ticket = await self.ticket_repo.get_by_id(entry.ticket_id)
        if not ticket:
            entry.status = "failed"
            entry.last_error = "Ticket not found"
            await self.ticket_repo.db.commit()
            return

        try:
            if entry.operation == "create_work_item":
                await self._create_work_item(ticket, entry.payload or {})
            elif entry.operation == "add_comment":
                await self._add_comment(ticket, entry.payload or {})
            else:
                raise RuntimeError(f"Unknown outbox operation: {entry.operation}")

            entry.status = "completed"
            entry.last_error = None
            await self.ticket_repo.db.commit()
        except Exception as exc:
            logger.exception("Support ticket sync failed for %s", entry.id)
            entry.status = "failed"
            entry.last_error = str(exc)[:2000]
            ticket.sync_error = str(exc)[:2000]
            await self.ticket_repo.db.commit()

    async def _create_work_item(
        self, ticket: SupportTicketModel, payload: dict[str, Any]
    ) -> None:
        if ticket.duplicate_of_id or ticket.azure_work_item_id:
            return

        connector = get_help_center_ado_connector()
        base_url = payload.get("app_base_url") or get_help_center_public_base_url()
        description_html = _build_description_html(ticket, app_base_url=base_url)
        result = await connector.create_work_item(
            title=ticket.title,
            description_html=description_html,
            tags=ticket.tags,
            priority=ticket.priority,
            area_path=payload.get("area_path") or get_help_center_default_area_path(),
        )
        work_item_id = result.get("id")
        if not work_item_id:
            raise RuntimeError("Azure DevOps did not return a work item id")

        ticket.azure_work_item_id = int(work_item_id)
        ticket.azure_project = connector.project
        ticket.azure_url = result.get("url") or connector.build_work_item_url(int(work_item_id))
        ticket.app_settings_id = None
        ticket.status = "open"
        ticket.sync_error = None
        ticket.synced_at = datetime.now(timezone.utc)

        await self.ticket_repo.add_event(
            ticket.id,
            "ado_work_item_created",
            payload={"azure_work_item_id": work_item_id},
        )
        await self.ticket_repo.save(ticket)

    async def _add_comment(self, ticket: SupportTicketModel, payload: dict[str, Any]) -> None:
        if not ticket.azure_work_item_id:
            raise RuntimeError("Ticket is not linked to Azure DevOps")
        connector = get_help_center_ado_connector()
        await connector.add_comment(ticket.azure_work_item_id, payload.get("text", ""))

    async def process_pending_outbox(self, limit: int = 20) -> int:
        entries = await self.ticket_repo.get_pending_outbox(limit=limit)
        for entry in entries:
            await self.process_outbox_entry(entry)
        return len(entries)

    async def apply_ado_webhook_update(
        self, work_item_id: int, fields: dict[str, Any]
    ) -> Optional[SupportTicketModel]:
        ticket = await self.ticket_repo.find_by_azure_work_item_id(work_item_id)
        if not ticket:
            return None

        state = fields.get("System.State")
        if state:
            ticket.status = AzureDevOpsConnector.extract_fields({"fields": fields})[
                "local_status"
            ]
        priority = fields.get("Microsoft.VSTS.Common.Priority")
        if priority is not None:
            try:
                ticket.priority = int(priority)
            except (TypeError, ValueError):
                pass
        tags_raw = fields.get("System.Tags")
        if tags_raw is not None:
            ticket.tags = [t.strip() for t in str(tags_raw).split(";") if t.strip()]

        ticket.synced_at = datetime.now(timezone.utc)
        await self.ticket_repo.add_event(
            ticket.id,
            "ado_webhook_updated",
            payload={"fields": {k: fields[k] for k in list(fields)[:20]}},
        )
        return await self.ticket_repo.save(ticket)
