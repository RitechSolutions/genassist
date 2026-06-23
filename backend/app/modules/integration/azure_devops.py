from __future__ import annotations

import base64
import logging
import os
from typing import Any, Optional
from urllib.parse import quote, urlparse

import aiohttp

from app.core.config.azure_devops_defaults import (
    API_VERSION,
    DEFAULT_WORK_ITEM_TYPE,
    FIELD_AREA_PATH,
    FIELD_DESCRIPTION,
    FIELD_PRIORITY,
    FIELD_TAGS,
    FIELD_TITLE,
)

logger = logging.getLogger(__name__)


def _normalize_org_url(organization_url: str) -> str:
    url = organization_url.rstrip("/")
    if not url.startswith("http"):
        url = f"https://{url}"
    return url


def _auth_header(pat: str) -> dict[str, str]:
    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


def _map_ado_state_to_local(state: str | None) -> str:
    if not state:
        return "unknown"
    normalized = state.strip().lower().replace(" ", "_")
    mapping = {
        "new": "new",
        "active": "active",
        "resolved": "resolved",
        "closed": "closed",
        "done": "closed",
        "removed": "closed",
        "proposed": "new",
    }
    return mapping.get(normalized, "unknown")


class AzureDevOpsConnector:
    """Azure DevOps Boards Work Item Tracking API client."""

    def __init__(
        self,
        organization_url: str,
        project: str,
        pat: str,
        work_item_type: str = DEFAULT_WORK_ITEM_TYPE,
    ):
        self.org_url = _normalize_org_url(organization_url)
        self.project = project
        self.pat = pat
        self.work_item_type = work_item_type or DEFAULT_WORK_ITEM_TYPE
        parsed = urlparse(self.org_url)
        self._org_name = parsed.path.strip("/").split("/")[-1] if parsed.netloc else ""

    def _project_base(self) -> str:
        return f"{self.org_url}/{quote(self.project, safe='')}"

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Any = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        headers = {
            **_auth_header(self.pat),
            "Content-Type": content_type,
        }
        ssl = os.getenv("USE_SSL", "false").lower() == "true"
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl)
        ) as session:
            async with session.request(method, url, headers=headers, json=json_body) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    logger.error("ADO API %s %s failed: %s %s", method, url, resp.status, text[:500])
                    raise RuntimeError(f"Azure DevOps API error {resp.status}: {text[:300]}")
                if not text:
                    return {}
                try:
                    return await resp.json()
                except Exception:
                    return {"raw": text}

    def build_work_item_url(self, work_item_id: int) -> str:
        if self._org_name:
            return (
                f"https://dev.azure.com/{self._org_name}/"
                f"{quote(self.project, safe='')}/_workitems/edit/{work_item_id}"
            )
        return f"{self._project_base()}/_workitems/edit/{work_item_id}"

    async def create_work_item(
        self,
        title: str,
        description_html: str = "",
        *,
        tags: list[str] | None = None,
        priority: int | None = None,
        area_path: str | None = None,
        work_item_type: str | None = None,
        extra_fields: dict[str, str] | None = None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        wit = (work_item_type or self.work_item_type or DEFAULT_WORK_ITEM_TYPE).strip()
        url = (
            f"{self._project_base()}/_apis/wit/workitems/"
            f"${quote(wit, safe='')}?api-version={API_VERSION}"
        )
        patch: list[dict[str, Any]] = [
            {"op": "add", "path": f"/fields/{FIELD_TITLE}", "value": title},
        ]
        if description_html:
            patch.append(
                {"op": "add", "path": f"/fields/{FIELD_DESCRIPTION}", "value": description_html}
            )
        if extra_fields:
            for field_ref, field_value in extra_fields.items():
                if field_value:
                    patch.append(
                        {"op": "add", "path": f"/fields/{field_ref}", "value": field_value}
                    )
        if tags:
            patch.append(
                {
                    "op": "add",
                    "path": f"/fields/{FIELD_TAGS}",
                    "value": "; ".join(tags),
                }
            )
        if priority is not None:
            patch.append(
                {
                    "op": "add",
                    "path": f"/fields/{FIELD_PRIORITY}",
                    "value": priority,
                }
            )
        if area_path:
            patch.append(
                {
                    "op": "add",
                    "path": f"/fields/{FIELD_AREA_PATH}",
                    "value": area_path,
                }
            )
        if attachments:
            # Link uploaded attachments to the work item. Without this association
            # Azure DevOps strips inline <img> tags that reference them, so the
            # images never render in the work item's HTML fields.
            for attachment_url in attachments:
                patch.append(
                    {
                        "op": "add",
                        "path": "/relations/-",
                        "value": {
                            "rel": "AttachedFile",
                            "url": attachment_url,
                            "attributes": {"comment": "Inline image from Help Center"},
                        },
                    }
                )
        return await self._request(
            "POST",
            url,
            json_body=patch,
            content_type="application/json-patch+json",
        )

    async def get_work_item(self, work_item_id: int) -> dict[str, Any]:
        url = f"{self._project_base()}/_apis/wit/workitems/{work_item_id}?api-version={API_VERSION}"
        return await self._request("GET", url)

    async def upload_attachment(
        self,
        file_name: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        """Upload binary content as a work item attachment.

        Returns the ADO attachment reference ``{"id": ..., "url": ...}``. The
        returned ``url`` can be embedded in an HTML field (e.g. ``<img src=...>``)
        so the attachment renders inline on the work item.
        """
        url = (
            f"{self._project_base()}/_apis/wit/attachments"
            f"?fileName={quote(file_name, safe='')}&api-version={API_VERSION}"
        )
        headers = {
            **_auth_header(self.pat),
            "Content-Type": content_type,
        }
        ssl = os.getenv("USE_SSL", "false").lower() == "true"
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl)
        ) as session:
            async with session.post(url, headers=headers, data=content) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    logger.error(
                        "ADO attachment upload failed: %s %s", resp.status, text[:500]
                    )
                    raise RuntimeError(
                        f"Azure DevOps attachment upload error {resp.status}: {text[:300]}"
                    )
                try:
                    return await resp.json()
                except Exception:
                    return {"raw": text}

    async def add_comment(self, work_item_id: int, text: str) -> dict[str, Any]:
        url = (
            f"{self._project_base()}/_apis/wit/workitems/{work_item_id}/comments"
            f"?api-version={API_VERSION}-preview.3"
        )
        return await self._request("POST", url, json_body={"text": text})

    async def search_work_items_by_title(
        self, title_fragment: str, *, top: int = 5
    ) -> list[dict[str, Any]]:
        safe_title = title_fragment.replace("'", "''")
        safe_project = self.project.replace("'", "''")
        wiql = {
            "query": (
                f"SELECT [System.Id], [System.Title], [System.State] "
                f"FROM WorkItems WHERE [System.TeamProject] = '{safe_project}' "
                f"AND [System.Title] CONTAINS '{safe_title}' "
                f"AND [System.State] <> 'Closed' "
                f"ORDER BY [System.ChangedDate] DESC"
            )
        }
        url = f"{self._project_base()}/_apis/wit/wiql?api-version={API_VERSION}"
        result = await self._request("POST", url, json_body=wiql)
        refs = (result.get("workItems") or [])[:top]
        items = []
        for ref in refs:
            wid = ref.get("id")
            if wid:
                try:
                    items.append(await self.get_work_item(wid))
                except Exception:
                    logger.warning("Failed to fetch work item %s", wid)
        return items

    @staticmethod
    def extract_fields(work_item: dict[str, Any]) -> dict[str, Any]:
        fields = work_item.get("fields") or {}
        tags_raw = fields.get(FIELD_TAGS) or ""
        tags = [t.strip() for t in str(tags_raw).split(";") if t.strip()]
        return {
            "state": fields.get("System.State"),
            "local_status": _map_ado_state_to_local(fields.get("System.State")),
            "priority": fields.get(FIELD_PRIORITY),
            "tags": tags,
            "title": fields.get(FIELD_TITLE),
        }
