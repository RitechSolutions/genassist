"""Web scraper node: fetches a URL and returns clean scraped content."""

import logging
import os
import tempfile
import uuid
from typing import Any, Dict

from app.core.utils.html_utils import html2markdown
from app.core.utils.web_content_utils import clean_html, extract_links, extract_main_content, extract_metadata
from app.core.utils.web_scrape_cache import get_cached, store
from app.core.utils.web_scraping_utils import fetch_from_url
from app.modules.workflow.engine import BaseNode

logger = logging.getLogger(__name__)


def _as_int(value: Any, default: int) -> int:
    # config values may arrive as None/""/str/float after template resolution
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class WebScraperNode(BaseNode):
    """Fetch a URL and return clean scraped content as markdown and/or HTML.

    Always returns a result dict and never raises: BaseNode.execute swallows
    exceptions to None, which would leave downstream nodes with nothing to
    branch on, so fetch/convert failures come back as {"success": False, ...}.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        url = (config.get("url") or "").strip()
        output_format = (config.get("format") or "markdown").lower()
        headers = config.get("headers") or {}
        only_main_content = bool(config.get("onlyMainContent", True))
        screenshot_opt = config.get("screenshot") or "off"
        wait_until = config.get("waitUntil") or "domcontentloaded"
        wait_for_ms = _as_int(config.get("waitFor"), 0)
        scroll_to_bottom = bool(config.get("scrollToBottom", False))
        max_age = _as_int(config.get("maxAge"), 0)

        if not url:
            return self._error("", output_format, "URL is required")

        # fetch_from_url validates the scheme; default bare hosts to https
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # every scrape-affecting option keys the cache; headers isolate auth
        cache_options = {
            "format": output_format,
            "onlyMainContent": only_main_content,
            "screenshot": screenshot_opt,
            "headers": headers,
            "waitFor": wait_for_ms,
            "waitUntil": wait_until,
            "scrollToBottom": scroll_to_bottom,
        }
        if max_age > 0:
            # key on the normalized input url so the same request hits the same entry
            cached = await get_cached(url, cache_options, max_age)
            if cached is not None:
                return cached

        try:
            fetched = await fetch_from_url(
                url,
                headers=headers,
                screenshot=screenshot_opt,
                wait_until=wait_until,
                wait_for_ms=wait_for_ms,
                scroll_to_bottom=scroll_to_bottom,
            )
            if not fetched.ok:
                return self._error(url, output_format, "Failed to fetch page")
            raw_html = fetched.html
            final_url = fetched.url or url  # post-redirect URL; input url as a safety net

            result: Dict[str, Any] = {
                "success": True,
                "url": final_url,
                "format": output_format,
                "error": "",
                "screenshot": "",
                "screenshot_file_id": "",
            }

            # resolve the content scope once so markdown, html and links all agree
            if only_main_content:
                main_md, main_html = extract_main_content(raw_html, final_url)
            else:
                main_md = html2markdown(raw_html, base_url=final_url)
                main_html = clean_html(raw_html, final_url)

            if output_format == "html":
                result["html"] = main_html
                result["content"] = main_html
            else:
                result["markdown"] = main_md
                result["content"] = main_md
                if output_format == "both":
                    result["html"] = main_html

            # links follow the same scope; metadata always reads raw html
            result["links"] = extract_links(main_html if only_main_content else raw_html, final_url)
            result["metadata"] = extract_metadata(raw_html, final_url, fetched.content_type)

            # host the screenshot after the browser has closed; never blocks a successful scrape
            if fetched.screenshot_bytes:
                result["screenshot"], result["screenshot_file_id"] = await self._host_screenshot(
                    fetched.screenshot_bytes, final_url
                )

            # cacheState only appears when caching is on, so the default output shape is unchanged
            if max_age > 0:
                await store(url, cache_options, max_age, result)
                result = {**result, "cacheState": "miss"}

            return result

        except ValueError as exc:
            # SSRF, disallowed scheme and DNS failures surface as ValueError
            return self._error(url, output_format, str(exc))
        except Exception as exc:  # timeouts, Playwright and other unexpected failures
            logger.error("Web scraper node failed for %s: %s", url, exc)
            return self._error(url, output_format, str(exc))

    async def _host_screenshot(self, image_bytes: bytes, source_url: str) -> tuple[str, str]:
        """Return ``(screenshot_url, screenshot_file_id)`` for the captured PNG; never raises.

        Hosts the PNG via FileManagerService so the output carries a short source URL.
        The public ``/source`` route works regardless of the file-manager flag;
        on any failure the fields stay empty.
        """
        try:
            return await self._host_via_file_manager(image_bytes)
        except Exception as exc:
            logger.warning("Screenshot hosting failed for %s: %s", source_url, exc)
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
    def _error(url: str, output_format: str, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "url": url,
            "content": "",
            "format": output_format,
            "error": message,
        }
