"""Web scraper node: fetches a URL and returns clean scraped content."""

import logging
from typing import Any, Dict

import httpx

from app.core.utils.html_utils import html2markdown
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

        if not url:
            return self._error("", output_format, "URL is required")

        # fetch_from_url validates the scheme; default bare hosts to https
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            # renderJs off uses fast httpx; on uses Playwright for JS-heavy sites
            html = await fetch_from_url(url, headers=headers, use_http_request=not render_js)

            result: Dict[str, Any] = {
                "success": True,
                "url": url,
                "format": output_format,
                "status_code": 200,
                "error": "",
            }
            if output_format == "html":
                result["content"] = html
            elif output_format == "both":
                markdown = html2markdown(html, base_url=url)
                result["markdown"] = markdown
                result["html"] = html
                result["content"] = markdown  # content always holds the primary format
            else:
                result["content"] = html2markdown(html, base_url=url)
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
