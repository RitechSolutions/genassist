from __future__ import annotations

import base64
import html
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from injector import inject

from app.core.config.azure_devops_defaults import (
    FIELD_ACCEPTANCE_CRITERIA,
    FIELD_REPRO_STEPS,
    FIELD_SYSTEM_INFO,
)
from app.core.config.help_center_ado import (
    get_help_center_ado_connector,
    get_help_center_default_area_path,
    get_help_center_public_base_url,
    help_center_ado_configured,
    resolve_work_item_type,
)
from app.db.models.support_ticket import SupportTicketModel, TicketSyncOutboxModel
from app.modules.integration.azure_devops import AzureDevOpsConnector
from app.repositories.support_ticket import SupportTicketRepository

logger = logging.getLogger(__name__)

_DATA_URI_IMG_RE = re.compile(
    r"data:image/(?P<subtype>[A-Za-z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=]+)"
)
_EXT_BY_SUBTYPE = {"jpeg": "jpg", "svg+xml": "svg"}


def _footer_html(ticket: SupportTicketModel, app_base_url: str = "") -> str:
    """Traceability footer appended to the work item's primary field."""
    env = ticket.environment or {}
    reporter_email = env.get("reporter_email")
    tenant = env.get("tenant")
    lines = [
        "<hr/>",
        f"<p><strong>GenAssist ticket:</strong> {html.escape(str(ticket.id))}</p>",
    ]
    if reporter_email:
        reporter = f"<strong>Reported by:</strong> {html.escape(str(reporter_email))}"
        if tenant:
            reporter += f" (tenant: {html.escape(str(tenant))})"
        lines.append(f"<p>{reporter}</p>")
    elif tenant:
        lines.append(f"<p><strong>Tenant:</strong> {html.escape(str(tenant))}</p>")
    if app_base_url:
        lines.append(
            f'<p><a href="{html.escape(app_base_url)}/help-center/{ticket.id}">Open in Help Center</a></p>'
        )
    return "".join(lines)


def _reporter_tags(ticket: SupportTicketModel) -> list[str]:
    """Filterable Azure Boards tags identifying the reporter and tenant."""
    env = ticket.environment or {}
    tags: list[str] = []
    if env.get("reporter_email"):
        tags.append(f"reporter:{env['reporter_email']}")
    if env.get("tenant"):
        tags.append(f"tenant:{env['tenant']}")
    return tags


async def _upload_inline_images(connector: AzureDevOpsConnector, html_value: str) -> str:
    """Upload inline base64 images to ADO and rewrite to attachment URLs.

    Azure DevOps HTML fields do not render base64 data URIs, so each embedded
    image is uploaded as a work item attachment and the ``src`` is swapped for
    the returned attachment URL (which ADO renders inline).
    """
    if not html_value or "data:image/" not in html_value:
        return html_value

    replacements: dict[str, str] = {}
    for index, match in enumerate(_DATA_URI_IMG_RE.finditer(html_value)):
        data_uri = match.group(0)
        if data_uri in replacements:
            continue
        subtype = match.group("subtype").lower()
        try:
            content = base64.b64decode(match.group("data"))
        except Exception:
            logger.warning("Skipping malformed inline image in Help Center field")
            continue
        ext = _EXT_BY_SUBTYPE.get(subtype, subtype)
        try:
            uploaded = await connector.upload_attachment(
                f"helpcenter-image-{index + 1}.{ext}",
                content,
                content_type=f"image/{subtype}",
            )
        except Exception:
            logger.exception("Failed to upload inline image to Azure DevOps")
            continue
        attachment_url = uploaded.get("url")
        if attachment_url:
            replacements[data_uri] = attachment_url

    result = html_value
    for data_uri, attachment_url in replacements.items():
        result = result.replace(data_uri, attachment_url)
    return result


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
        footer = _footer_html(ticket, app_base_url=base_url)

        async def prep(value: Optional[str]) -> str:
            return await _upload_inline_images(connector, value or "")

        # Map the per-type rich-text fields onto the Azure DevOps work item form.
        # Bug -> Repro Steps / System Info / Acceptance Criteria,
        # Feature -> Description / Acceptance Criteria, Task -> Description.
        ticket_type = (ticket.ticket_type or "bug").strip().lower()
        description_html = ""
        extra_fields: dict[str, str] = {}

        if ticket_type == "bug":
            repro = await prep(ticket.repro_steps)
            extra_fields[FIELD_REPRO_STEPS] = f"{repro}{footer}" if repro else footer
            system_info = await prep(ticket.system_info)
            if system_info:
                extra_fields[FIELD_SYSTEM_INFO] = system_info
            acceptance = await prep(ticket.acceptance_criteria)
            if acceptance:
                extra_fields[FIELD_ACCEPTANCE_CRITERIA] = acceptance
        elif ticket_type == "feature":
            description_html = f"{await prep(ticket.description)}{footer}"
            acceptance = await prep(ticket.acceptance_criteria)
            if acceptance:
                extra_fields[FIELD_ACCEPTANCE_CRITERIA] = acceptance
        else:  # task
            description_html = f"{await prep(ticket.description)}{footer}"

        tags = list(ticket.tags or [])
        for tag in ("genassist", f"help-center-{ticket.ticket_type}", *_reporter_tags(ticket)):
            if tag not in tags:
                tags.append(tag)
        result = await connector.create_work_item(
            title=ticket.title,
            description_html=description_html,
            tags=tags,
            priority=ticket.priority,
            area_path=payload.get("area_path") or get_help_center_default_area_path(),
            work_item_type=resolve_work_item_type(ticket.ticket_type),
            extra_fields=extra_fields,
        )
        work_item_id = result.get("id")
        if not work_item_id:
            raise RuntimeError("Azure DevOps did not return a work item id")

        ticket.azure_work_item_id = int(work_item_id)
        ticket.azure_project = connector.project
        ticket.azure_url = result.get("url") or connector.build_work_item_url(int(work_item_id))
        ticket.app_settings_id = None
        # Mirror the work item's actual starting state (varies by type/process,
        # e.g. Bug -> "To Do", Feature -> "New") instead of a hardcoded value.
        ticket.status = AzureDevOpsConnector.extract_fields(result).get("state") or "new"
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

    async def refresh_status(self, ticket: SupportTicketModel) -> SupportTicketModel:
        """Best-effort pull of the current Azure DevOps state for a ticket.

        Keeps the local status in sync with the live work item state even when no
        Service Hook webhook is configured (e.g. local dev). Failures are swallowed
        so viewing a ticket never breaks.
        """
        if not ticket.azure_work_item_id or not help_center_ado_configured():
            return ticket
        try:
            connector = get_help_center_ado_connector()
            work_item = await connector.get_work_item(ticket.azure_work_item_id)
            state = AzureDevOpsConnector.extract_fields(work_item).get("state")
            if state and state != ticket.status:
                ticket.status = str(state)
                ticket.synced_at = datetime.now(timezone.utc)
                ticket.sync_error = None
                await self.ticket_repo.save(ticket)
        except Exception:
            logger.warning(
                "Could not refresh Azure DevOps state for ticket %s",
                ticket.id,
                exc_info=True,
            )
        return ticket

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
            ticket.status = str(state)
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
