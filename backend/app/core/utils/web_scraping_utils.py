import asyncio
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Route, async_playwright

_HTTPX_TIMEOUT = 10  # seconds
_PLAYWRIGHT_TIMEOUT = 10_000  # milliseconds

_ALLOWED_SCHEMES = frozenset({"http", "https"})

_FORWARDED_HEADER_ALLOWLIST = frozenset({
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "content-type",
    "if-modified-since",
    "if-none-match",
})

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
        results = await loop.run_in_executor(
            None, socket.getaddrinfo, hostname, port, 0, socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise ValueError(f"DNS resolution failed for {hostname!r}: {exc}") from exc
    if not results:
        raise ValueError(f"No DNS results for {hostname!r}")
    for _fam, _typ, _proto, _canon, sockaddr in results:
        ip = sockaddr[0]
        if _is_blocked_ip(ip):
            raise ValueError(
                f"Resolved address {ip!r} for host {hostname!r} is in a blocked range"
            )


def _safe_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {k: v for k, v in headers.items() if k.lower() in _FORWARDED_HEADER_ALLOWLIST}


async def fetch_from_url(
    url: str,
    headers: dict[str, str] | None = None,
    use_http_request: bool = False,
) -> str:
    """Fetch URL content using Playwright by default, or httpx when requested."""
    await _validate_url(url)
    safe_headers = _safe_headers(headers)

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
                    raise ValueError(
                        f"Redirect to disallowed scheme: {urlparse(redirect_url).scheme!r}"
                    )
                await _validate_url(redirect_url)
                response = await client.get(redirect_url)
                current_url = redirect_url
                hops_remaining -= 1
            response.raise_for_status()
            return response.text

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
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
        await page.goto(url, wait_until="domcontentloaded", timeout=_PLAYWRIGHT_TIMEOUT)
        html = await page.content()
        await browser.close()
        return html


def html2text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for bad in soup(["script", "style", "noscript"]):
        bad.extract()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()
