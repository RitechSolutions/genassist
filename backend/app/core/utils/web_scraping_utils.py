import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from playwright.async_api import Route, async_playwright

_HTTPX_TIMEOUT = 10  # seconds
_PLAYWRIGHT_TIMEOUT = 10_000  # milliseconds
_WAIT_FOR_CAP = 30_000  # ms ceiling so a large waitFor can't hang the scrape
_SCROLL_MAX_STEPS = 50  # bounds the lazy-load scroll so infinite pages can't loop forever

_ALLOWED_SCHEMES = frozenset({"http", "https"})
# Playwright DocumentLoadState values accepted for goto's wait_until
_WAIT_UNTIL_STATES = frozenset({"load", "domcontentloaded", "networkidle", "commit"})

_FORWARDED_HEADER_ALLOWLIST = frozenset(
    {
        "accept",
        "accept-encoding",
        "accept-language",
        "cache-control",
        "content-type",
        "if-modified-since",
        "if-none-match",
    }
)


@dataclass
class FetchResult:
    """Result of a URL fetch, exposing the side-channels both callers need."""

    html: str
    url: str  # final URL after redirects
    ok: bool  # navigation returned a non-error status; the scraper fails the node when False
    content_type: str | None
    screenshot_bytes: bytes | None = None  # PNG bytes, only on the Playwright path


def _is_blocked_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        return not ip.is_global or ip.is_multicast
    except ValueError:
        return True


async def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Disallowed URL scheme: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, socket.getaddrinfo, hostname, port, 0, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"DNS resolution failed for {hostname!r}: {exc}") from exc
    if not results:
        raise ValueError(f"No DNS results for {hostname!r}")
    for _fam, _typ, _proto, _canon, sockaddr in results:
        ip = sockaddr[0]
        if _is_blocked_ip(ip):
            raise ValueError(f"Resolved address {ip!r} for host {hostname!r} is in a blocked range")


def _safe_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {k: v for k, v in headers.items() if k.lower() in _FORWARDED_HEADER_ALLOWLIST}


async def _auto_scroll(page) -> None:
    try:
        await page.evaluate(
            """async (maxSteps) => {
                await new Promise((resolve) => {
                    let steps = 0;
                    const timer = setInterval(() => {
                        const before = window.scrollY;
                        window.scrollBy(0, window.innerHeight);
                        steps += 1;
                        const atBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight;
                        if (atBottom || steps >= maxSteps || window.scrollY === before) {
                            clearInterval(timer);
                            resolve();
                        }
                    }, 50);
                });
            }""",
            _SCROLL_MAX_STEPS,
        )
    except Exception:
        pass


async def fetch_from_url(
    url: str,
    headers: dict[str, str] | None = None,
    use_http_request: bool = False,
    *,
    screenshot: str | None = None,
    wait_until: str = "domcontentloaded",
    wait_for_ms: int = 0,
    scroll_to_bottom: bool = False,
) -> FetchResult:
    await _validate_url(url)
    safe_headers = _safe_headers(headers)
    if wait_until not in _WAIT_UNTIL_STATES:
        wait_until = "domcontentloaded"

    if use_http_request:
        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
        }
        merged_headers = {**default_headers, **safe_headers}

        async with httpx.AsyncClient(
            follow_redirects=False,
            headers=merged_headers,
            timeout=_HTTPX_TIMEOUT,
        ) as client:
            response = await client.get(url)
            current_url = url
            hops_remaining = 5
            while response.is_redirect and hops_remaining > 0:
                location = response.headers.get("location", "")
                redirect_url = urljoin(current_url, location)
                if urlparse(redirect_url).scheme not in _ALLOWED_SCHEMES:
                    raise ValueError(f"Redirect to disallowed scheme: {urlparse(redirect_url).scheme!r}")
                await _validate_url(redirect_url)
                response = await client.get(redirect_url)
                current_url = redirect_url
                hops_remaining -= 1
            response.raise_for_status()
            return FetchResult(
                response.text,
                current_url,
                True,
                response.headers.get("content-type"),
            )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # try/finally so a goto/content error can't leak the browser process
        try:
            page = await browser.new_page()

            if safe_headers:
                await page.set_extra_http_headers(safe_headers)

            async def _block_private_routes(route: Route) -> None:
                try:
                    await _validate_url(route.request.url)
                    await route.continue_()
                except ValueError:
                    await route.abort("blockedbyclient")

            await page.route("**/*", _block_private_routes)
            response = await page.goto(url, wait_until=wait_until, timeout=_PLAYWRIGHT_TIMEOUT)
            # scroll then settle before snapshotting so lazy content is captured
            if scroll_to_bottom:
                await _auto_scroll(page)
            if wait_for_ms > 0:
                await page.wait_for_timeout(min(wait_for_ms, _WAIT_FOR_CAP))
            html = await page.content()
            final_url = page.url
            ok = response is None or response.status < 400
            content_type = response.headers.get("content-type") if response is not None else None
            shot = None
            if screenshot and screenshot != "off":
                shot = await page.screenshot(full_page=(screenshot == "fullPage"))
            return FetchResult(html, final_url, ok, content_type, shot)
        finally:
            await browser.close()
