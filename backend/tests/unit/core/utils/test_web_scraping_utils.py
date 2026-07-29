"""Unit tests for web_scraping_utils: render_html_to_image + the SSRF route guard.

Playwright is mocked so the render path can run without a real browser; the route
guard is exercised directly against a fake Route to confirm data: URIs pass and a
private http URL is aborted.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.utils import web_scraping_utils
from app.core.utils.web_scraping_utils import _block_private_routes, render_html_to_image


class _FakeAsyncPlaywright:
    """Async context manager returning a stub ``p`` with a chromium launcher."""

    def __init__(self, page):
        self._page = page

    async def __aenter__(self):
        browser = SimpleNamespace(
            new_page=AsyncMock(return_value=self._page),
            close=AsyncMock(),
        )
        return SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))

    async def __aexit__(self, *exc):
        return False


def _fake_page(shot=b"pngbytes"):
    return SimpleNamespace(
        route=AsyncMock(),
        set_content=AsyncMock(),
        wait_for_timeout=AsyncMock(),
        screenshot=AsyncMock(return_value=shot),
    )


@pytest.mark.asyncio
async def test_render_raises_on_empty_html():
    with pytest.raises(ValueError, match="HTML content is required"):
        await render_html_to_image("   ")


@pytest.mark.asyncio
async def test_render_returns_png_bytes_and_installs_route_guard():
    page = _fake_page()
    with patch.object(web_scraping_utils, "async_playwright", return_value=_FakeAsyncPlaywright(page)):
        result = await render_html_to_image("<h1>Hi</h1>", full_page=True)
    assert result == b"pngbytes"
    # SSRF guard installed on all sub-resource requests
    page.route.assert_awaited_once()
    assert page.route.call_args.args[0] == "**/*"
    assert page.route.call_args.args[1] is _block_private_routes
    page.set_content.assert_awaited_once()
    page.screenshot.assert_awaited_once_with(full_page=True)


@pytest.mark.asyncio
async def test_render_wait_for_ms_triggers_timeout_wait():
    page = _fake_page()
    with patch.object(web_scraping_utils, "async_playwright", return_value=_FakeAsyncPlaywright(page)):
        await render_html_to_image("<h1>Hi</h1>", wait_for_ms=100)
    page.wait_for_timeout.assert_awaited_once_with(100)


def _fake_route(url):
    return SimpleNamespace(
        request=SimpleNamespace(url=url),
        continue_=AsyncMock(),
        abort=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_route_guard_allows_data_uri():
    route = _fake_route("data:image/png;base64,iVBORw0KGgo=")
    await _block_private_routes(route)
    route.continue_.assert_awaited_once()
    route.abort.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_guard_blocks_private_http_url():
    route = _fake_route("http://127.0.0.1/internal")
    await _block_private_routes(route)
    route.abort.assert_awaited_once()
    route.continue_.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_guard_allows_public_http_url():
    route = _fake_route("https://example.com/asset.css")
    with patch.object(web_scraping_utils, "_validate_url", new=AsyncMock()):
        await _block_private_routes(route)
    route.continue_.assert_awaited_once()
    route.abort.assert_not_awaited()
