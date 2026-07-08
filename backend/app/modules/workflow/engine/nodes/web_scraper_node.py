"""Web scraper node: fetches a URL and returns clean scraped content."""

import logging
from typing import Any, Dict

import httpx

from app.core.utils.html_utils import html2markdown
from app.core.utils.web_content_utils import extract_links, extract_main_content, extract_metadata
from app.core.utils.web_scraping_utils import fetch_from_url
from app.modules.workflow.engine import BaseNode

logger = logging.getLogger(__name__)


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
