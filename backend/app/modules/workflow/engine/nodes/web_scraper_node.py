"""Web scraper node: fetches a URL and returns clean scraped content."""

import base64
import logging
import os
import tempfile
import uuid
from typing import Any, Dict

import httpx

from app.core.utils.html_utils import html2markdown
from app.core.utils.web_content_utils import extract_links, extract_main_content, extract_metadata
from app.core.utils.web_scraping_utils import fetch_from_url
from app.modules.workflow.engine import BaseNode

logger = logging.getLogger(__name__)

_MAX_INLINE_SCREENSHOT_B64 = 1_500_000  # ~1.5 MB cap on the base64 data-URI fallback


class WebScraperNode(BaseNode):
    """Fetch a URL and return clean scraped content as markdown and/or HTML.

    Always returns a result dict and never raises: BaseNode.execute swallows
    exceptions to None, which would leave downstream nodes with nothing to
    branch on, so fetch/convert failures come back as {"success": False, ...}.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        url = (config.get("url") or "").strip()
        output_format = (config.get("format") or "markdown").lower()
        render_js = bool(config.get("renderJs", False))
        headers = config.get("headers") or {}
        only_main_content = bool(config.get("onlyMainContent", True))
        include_links = bool(config.get("includeLinks", True))
        include_metadata = bool(config.get("includeMetadata", True))
        screenshot_opt = config.get("screenshot") or "off"

        if not url:
            return self._error("", output_format, "URL is required")

        # fetch_from_url validates the scheme; default bare hosts to https
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        render_browser = render_js or screenshot_opt != "off"

        try:
            fetched = await fetch_from_url(
                url,
                headers=headers,
                use_http_request=not render_browser,
                screenshot=screenshot_opt,
            )
            raw_html = fetched.html
            final_url = fetched.url or url  # post-redirect URL; input url as a safety net

            result: Dict[str, Any] = {
                "success": True,
                "url": final_url,
                "format": output_format,
                "status_code": fetched.status_code,
                "error": "",
                "screenshot": "",
                "screenshot_file_id": "",
            }

            if output_format == "html":
                result["html"] = raw_html  
                result["content"] = raw_html
            else:
                markdown = (
                    extract_main_content(raw_html, final_url)[0]
                    if only_main_content
                    else html2markdown(raw_html, base_url=final_url)
                )
                result["markdown"] = markdown
                result["content"] = markdown  
                if output_format == "both":
                    result["html"] = raw_html

            if include_links:
                result["links"] = extract_links(raw_html, final_url)
            if include_metadata:
                result["metadata"] = extract_metadata(raw_html, final_url, fetched.status_code, fetched.content_type)

            # host the screenshot after the browser has closed; never blocks a successful scrape
            if fetched.screenshot_bytes:
                result["screenshot"], result["screenshot_file_id"] = await self._host_screenshot(
                    fetched.screenshot_bytes, final_url
                )

            return result

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            return self._error(url, output_format, f"HTTP error {status}", status_code=status)
        except ValueError as exc:
            # SSRF, disallowed scheme and DNS failures surface as ValueError
            return self._error(url, output_format, str(exc))
        except Exception as exc:  # timeouts, Playwright and other unexpected failures
            logger.error("Web scraper node failed for %s: %s", url, exc)
            return self._error(url, output_format, str(exc))

    async def _host_screenshot(self, image_bytes: bytes, source_url: str) -> tuple[str, str]:
        """Return ``(screenshot, screenshot_file_id)`` for the captured PNG; never raises.

        A hosted FileManager URL when hosting is enabled and reachable,
        otherwise a size-guarded base64 data-URI, otherwise empty strings so an
        oversized image can't bloat node_outputs / downstream LLM prompts.
        """
        from app.core.config.settings import file_storage_settings

        if file_storage_settings.FILE_MANAGER_ENABLED:
            try:
                return await self._host_via_file_manager(image_bytes)
            except Exception as exc:
                logger.warning("Screenshot hosting failed for %s: %s", source_url, exc)

        b64 = base64.b64encode(image_bytes).decode("ascii")
        if len(b64) <= _MAX_INLINE_SCREENSHOT_B64:
            return f"data:image/png;base64,{b64}", ""
        return "", ""

    async def _host_via_file_manager(self, image_bytes: bytes) -> tuple[str, str]:
        """Upload the PNG through FileManagerService, returning ``(url, file_id)``.

        Fetch the "File Manager Settings" row so
        the configured provider (local in dev, S3 in prod) is used; a missing row leaves
        ``app_settings=None`` and initialize falls back to env provider config.
        """
        from app.core.config.settings import file_storage_settings
        from app.core.project_path import DATA_VOLUME
        from app.dependencies.injector import injector
        from app.schemas.file import FileBase
        from app.services.app_settings import AppSettingsService
        from app.services.file_manager import FileManagerService

        fm = injector.get(FileManagerService)
        app_cfg = await injector.get(AppSettingsService).get_by_type_and_name(
            "FileManagerSettings", "File Manager Settings"
        )
        # base_url is mandatory for the local provider's source URL; nodes have no request
        provider = await fm.initialize(
            base_url=(file_storage_settings.APP_URL or "http://localhost:8000").rstrip("/"),
            base_path=str(DATA_VOLUME),
            app_settings=app_cfg,
        )

        name = f"{uuid.uuid4()}.png"
        tmp = os.path.join(tempfile.gettempdir(), name)
        with open(tmp, "wb") as handle:
            handle.write(image_bytes)

        file_base = FileBase(
            name=name,
            storage_path=provider.get_base_path(),
            path="web_scraper_screenshots",
            storage_provider=provider.name,
            file_extension="png",
        )
        created = await fm.create_file_from_local_path(
            tmp,
            file_base=file_base,
            original_filename=name,
            mime_type="image/png",
            delete_source=True,
        )
        # local -> /api/file-manager/.../source ; s3 -> presigned URL
        return await fm.get_file_url(created), str(created.id)

    @staticmethod
    def _error(url: str, output_format: str, message: str, status_code: int | None = None) -> Dict[str, Any]:
        return {
            "success": False,
            "url": url,
            "content": "",
            "format": output_format,
            "status_code": status_code,
            "error": message,
        }
