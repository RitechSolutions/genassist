"""Registration tests for WebScraperNode ("Web Scraper").

Asserts the node type is wired end-to-end: resolvable in the engine registry,
present in the dialog / handler / label schema maps, and reported as needing DB
access. Plus focused process() tests (fetch_from_url mocked, the real html2markdown left to run) that lock in the output contract,
screenshot hosting and error handling.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.utils.web_scraping_utils import FetchResult
from app.modules.workflow.engine.nodes.web_scraper_node import WebScraperNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

_NODE_TYPE = "webScraperNode"

_FETCH_PATH = "app.modules.workflow.engine.nodes.web_scraper_node.fetch_from_url"


def _make_node():
    node_config = {"type": _NODE_TYPE, "data": {"name": "Web Scraper"}}
    return WebScraperNode("node-1", node_config, SimpleNamespace())


def _fr(html, url="https://example.com", ok=True, content_type="text/html", shot=None):
    """Build a FetchResult stand-in for the fetch_from_url mock."""
    return FetchResult(
        html=html,
        url=url,
        ok=ok,
        content_type=content_type,
        screenshot_bytes=shot,
    )


def _fake_file_manager(url="http://localhost:8000/api/file-manager/files/f1/source", file_id="f1"):
    """Mock FileManagerService whose hosting calls resolve to a local-style source URL."""
    provider = SimpleNamespace(name="local", get_base_path=lambda: "/data")
    return SimpleNamespace(
        initialize=AsyncMock(return_value=provider),
        create_file_from_local_path=AsyncMock(return_value=SimpleNamespace(id=file_id)),
        get_file_url=AsyncMock(return_value=url),
    )


def _fake_injector(file_manager, app_settings):
    """Stand-in injector resolving the two services the hosting path pulls."""
    from app.services.app_settings import AppSettingsService
    from app.services.file_manager import FileManagerService

    def _get(cls):
        if cls is FileManagerService:
            return file_manager
        if cls is AppSettingsService:
            return app_settings
        raise KeyError(cls)

    return SimpleNamespace(get=_get)


# registration


def test_node_type_resolves_to_class_in_engine_registry():
    """Engine registry maps the type to WebScraperNode after init."""
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is WebScraperNode


def test_node_type_present_in_dialog_schema():
    """Dialog schema is registered (builder can render the config dialog)."""
    assert _NODE_TYPE in NODE_DIALOG_SCHEMAS


def test_dialog_schema_contains_required_scraper_fields():
    """Dialog exposes the scraper fields and keeps the config surfaces in sync; only url is required."""
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS[_NODE_TYPE]}
    assert {
        "url",
        "format",
        "onlyMainContent",
        "screenshot",
        "headers",
        "waitFor",
        "waitUntil",
        "scrollToBottom",
        "maxAge",
    } <= set(schema)

    assert {"renderJs", "includeLinks", "includeMetadata"}.isdisjoint(schema)
    assert schema["url"].required is True
    assert schema["screenshot"].default == "off"


def test_node_type_present_in_handlers_with_input_and_output():
    """Handler schema declares both an input (target) and output (source) handler."""
    assert _NODE_TYPE in NODE_HANDLERS_SCHEMAS
    types = {h["type"] for h in NODE_HANDLERS_SCHEMAS[_NODE_TYPE]}
    assert "target" in types
    assert "source" in types


def test_node_type_label_registered():
    """Human label is registered for the node-type endpoint / log enrichment."""
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "Web Scraper"


def test_node_reported_as_needing_db_access():
    engine = WorkflowEngine.__new__(WorkflowEngine)
    assert engine._node_needs_db_access(_NODE_TYPE) is True


# process()


@pytest.mark.asyncio
async def test_markdown_success_returns_clean_envelope():
    node = _make_node()
    with patch(_FETCH_PATH, new=AsyncMock(return_value=_fr("<h1>Hi</h1>"))):
        result = await node.process({"url": "https://example.com", "format": "markdown"})
    assert result["success"] is True
    assert "status_code" not in result
    assert result["format"] == "markdown"
    assert "Hi" in result["content"]  # thin doc: chrome-strip stays primary, readability isn't richer
    assert result["error"] == ""


@pytest.mark.asyncio
async def test_both_format_includes_markdown_and_html_keys():
    node = _make_node()
    html = "<h1>Hi</h1>"
    with patch(_FETCH_PATH, new=AsyncMock(return_value=_fr(html))):
        # onlyMainContent off keeps the assertion on a deterministic full-DOM conversion
        result = await node.process({"url": "https://example.com", "format": "both", "onlyMainContent": False})
    assert "<h1>Hi</h1>" in result["html"]
    assert "Hi" in result["markdown"]
    assert result["content"] == result["markdown"]


@pytest.mark.asyncio
async def test_html_field_is_cleaned_of_scripts_and_head():
    node = _make_node()
    raw = (
        "<html><head><title>T</title><style>.x{}</style></head>"
        "<body><script>window.__DATA__=1</script>"
        "<h1>Real</h1><p>Body text</p></body></html>"
    )
    with patch(_FETCH_PATH, new=AsyncMock(return_value=_fr(raw))):
        result = await node.process({"url": "https://example.com", "format": "html"})
    assert "<h1>Real</h1>" in result["html"]
    assert "__DATA__" not in result["html"]
    assert "<script" not in result["html"]
    assert "<style" not in result["html"]
    assert result["content"] == result["html"]


@pytest.mark.asyncio
async def test_html_format_honors_only_main_content():
    node = _make_node()
    raw = "<html><body><nav><a href='/menu'>Menu</a></nav><main><h1>Real</h1><p>Body text</p></main></body></html>"
    with patch(_FETCH_PATH, new=AsyncMock(return_value=_fr(raw))):
        result = await node.process({"url": "https://example.com", "format": "html", "onlyMainContent": True})
    assert "<h1>Real</h1>" in result["html"]
    assert "Menu" not in result["html"]


@pytest.mark.asyncio
async def test_both_format_main_content_scopes_markdown_and_html():
    node = _make_node()
    raw = (
        "<html><body><nav>NavMenu</nav>"
        "<article><h1>Title</h1><p>Article body paragraph.</p></article>"
        "<footer>FooterText</footer></body></html>"
    )
    with patch(_FETCH_PATH, new=AsyncMock(return_value=_fr(raw))):
        result = await node.process({"url": "https://example.com", "format": "both", "onlyMainContent": True})
    for scope in (result["markdown"], result["html"]):
        assert "Title" in scope
        assert "NavMenu" not in scope
        assert "FooterText" not in scope
    assert result["content"] == result["markdown"]


@pytest.mark.asyncio
async def test_links_follow_only_main_content_scope():
    node = _make_node()
    raw = (
        "<html><body><main><a href='/post'>Post</a></main><footer><a href='/privacy'>Privacy</a></footer></body></html>"
    )
    with patch(_FETCH_PATH, new=AsyncMock(return_value=_fr(raw))):
        scoped = await node.process({"url": "https://example.com", "onlyMainContent": True})
        full = await node.process({"url": "https://example.com", "onlyMainContent": False})
    assert "https://example.com/post" in scoped["links"]
    assert "https://example.com/privacy" not in scoped["links"]  # footer dropped with the chrome
    assert "https://example.com/privacy" in full["links"]


@pytest.mark.asyncio
async def test_render_controls_forward_to_browser():
    node = _make_node()
    fetch = AsyncMock(return_value=_fr("<p>ok</p>"))
    with patch(_FETCH_PATH, new=fetch):
        await node.process(
            {
                "url": "https://example.com",
                "waitFor": "1500",  # float-string coerces via _as_int
                "waitUntil": "networkidle",
                "scrollToBottom": True,
            }
        )
    kwargs = fetch.call_args.kwargs
    assert kwargs["wait_for_ms"] == 1500
    assert kwargs["wait_until"] == "networkidle"
    assert kwargs["scroll_to_bottom"] is True


_GET_CACHED = "app.modules.workflow.engine.nodes.web_scraper_node.get_cached"
_STORE = "app.modules.workflow.engine.nodes.web_scraper_node.store"


@pytest.mark.asyncio
async def test_max_age_zero_never_touches_cache():
    node = _make_node()
    fetch = AsyncMock(return_value=_fr("<h1>Hi</h1>"))
    with (
        patch(_FETCH_PATH, new=fetch),
        patch(_GET_CACHED, new=AsyncMock()) as get_cached,
        patch(_STORE, new=AsyncMock()) as store,
    ):
        result = await node.process({"url": "https://example.com"})
    get_cached.assert_not_awaited()
    store.assert_not_awaited()
    assert "cacheState" not in result  # default output shape stays unchanged


@pytest.mark.asyncio
async def test_cache_hit_short_circuits_fetch():
    node = _make_node()
    fetch = AsyncMock(return_value=_fr("<h1>Hi</h1>"))
    hit = {"success": True, "content": "cached", "cacheState": "hit"}
    with (
        patch(_FETCH_PATH, new=fetch),
        patch(_GET_CACHED, new=AsyncMock(return_value=hit)),
        patch(_STORE, new=AsyncMock()) as store,
    ):
        result = await node.process({"url": "https://example.com", "maxAge": 120})
    assert result is hit
    fetch.assert_not_awaited()
    store.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_miss_stores_and_marks_state():
    node = _make_node()
    fetch = AsyncMock(return_value=_fr("<h1>Hi</h1>"))
    with (
        patch(_FETCH_PATH, new=fetch),
        patch(_GET_CACHED, new=AsyncMock(return_value=None)),
        patch(_STORE, new=AsyncMock()) as store,
    ):
        result = await node.process({"url": "https://example.com", "maxAge": 120})
    fetch.assert_awaited_once()
    store.assert_awaited_once()
    assert result["cacheState"] == "miss"


@pytest.mark.asyncio
async def test_scheme_is_prepended_for_bare_host():
    node = _make_node()
    fetch = AsyncMock(return_value=_fr("<p>ok</p>", url="https://example.com"))
    with patch(_FETCH_PATH, new=fetch):
        result = await node.process({"url": "example.com"})
    assert fetch.call_args.args[0] == "https://example.com"
    assert result["url"] == "https://example.com"  # from FetchResult.url


@pytest.mark.asyncio
async def test_empty_url_returns_error_without_fetching():
    node = _make_node()
    fetch = AsyncMock(return_value=_fr("<p>ok</p>"))
    with patch(_FETCH_PATH, new=fetch):
        result = await node.process({"url": "  "})
    assert result["success"] is False
    assert result["error"] == "URL is required"
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_default_output_carries_links_metadata_and_empty_screenshot():
    node = _make_node()
    html = (
        "<html lang='en'><head><title>Example</title>"
        "<meta name='description' content='A demo page'></head>"
        "<body><a href='/about'>About</a></body></html>"
    )
    fetched = _fr(html, url="https://example.com/")
    with patch(_FETCH_PATH, new=AsyncMock(return_value=fetched)):
        result = await node.process({"url": "https://example.com"})
    assert "status_code" not in result
    assert "https://example.com/about" in result["links"]
    assert result["metadata"]["title"] == "Example"
    assert result["metadata"]["sourceURL"] == "https://example.com/"
    assert "statusCode" not in result["metadata"]
    assert result["screenshot"] == ""
    assert result["screenshot_file_id"] == ""


@pytest.mark.asyncio
async def test_ssrf_value_error_is_returned_as_failure():
    node = _make_node()
    blocked = ValueError("Resolved address '127.0.0.1' ... is in a blocked range")
    with patch(_FETCH_PATH, new=AsyncMock(side_effect=blocked)):
        result = await node.process({"url": "http://localhost"})
    assert result["success"] is False
    assert result["content"] == ""
    assert "blocked range" in result["error"]


@pytest.mark.asyncio
async def test_error_status_returns_failure_envelope():
    node = _make_node()
    with patch(_FETCH_PATH, new=AsyncMock(return_value=_fr("<h1>err</h1>", ok=False))):
        result = await node.process({"url": "https://example.com/missing"})
    assert result["success"] is False
    assert result["content"] == ""
    assert result["error"] == "Failed to fetch page"
    assert "status_code" not in result


@pytest.mark.asyncio
async def test_node_always_uses_browser_path():
    node = _make_node()
    fetch = AsyncMock(return_value=_fr("<p>ok</p>"))
    with patch(_FETCH_PATH, new=fetch):
        await node.process({"url": "https://example.com"})
    assert "use_http_request" not in fetch.call_args.kwargs


@pytest.mark.asyncio
async def test_links_and_metadata_always_included():
    node = _make_node()
    # stale opt-out keys are ignored; links + metadata always build (backward-compat guarantee)
    with patch(_FETCH_PATH, new=AsyncMock(return_value=_fr("<a href='/x'>X</a>"))):
        result = await node.process({"url": "https://example.com", "includeLinks": False, "includeMetadata": False})
    assert "links" in result
    assert "metadata" in result


# screenshot hosting


@pytest.mark.asyncio
async def test_screenshot_forwarded_to_fetch():
    """A screenshot request is forwarded to the (always-browser) fetch path."""
    node = _make_node()
    fetch = AsyncMock(return_value=_fr("<p>ok</p>"))
    with patch(_FETCH_PATH, new=fetch):
        await node.process({"url": "https://example.com", "screenshot": "viewport"})
    assert fetch.call_args.kwargs["screenshot"] == "viewport"


@pytest.mark.asyncio
async def test_screenshot_hosted_via_file_manager_returns_source_url():
    node = _make_node()
    fetched = _fr("<p>ok</p>", shot=b"pngbytes")
    fm = _fake_file_manager()
    app_settings = SimpleNamespace(get_by_type_and_name=AsyncMock(return_value=None))
    with (
        patch(_FETCH_PATH, new=AsyncMock(return_value=fetched)),
        patch("app.core.config.settings.file_storage_settings.FILE_MANAGER_ENABLED", False),
        patch("app.dependencies.injector.injector", _fake_injector(fm, app_settings)),
    ):
        result = await node.process({"url": "https://example.com", "screenshot": "viewport"})
    assert result["success"] is True
    assert result["screenshot"] == "http://localhost:8000/api/file-manager/files/f1/source"
    assert result["screenshot_file_id"] == "f1"
    fm.create_file_from_local_path.assert_awaited_once()


@pytest.mark.asyncio
async def test_screenshot_hosting_error_leaves_fields_empty_and_keeps_success():
    """A hosting failure degrades to empty screenshot fields while the scrape still succeeds."""
    node = _make_node()
    fetched = _fr("<p>ok</p>", shot=b"tiny-png-bytes")
    fm = SimpleNamespace(initialize=AsyncMock(side_effect=RuntimeError("hosting down")))
    app_settings = SimpleNamespace(get_by_type_and_name=AsyncMock(return_value=None))
    with (
        patch(_FETCH_PATH, new=AsyncMock(return_value=fetched)),
        patch("app.dependencies.injector.injector", _fake_injector(fm, app_settings)),
    ):
        result = await node.process({"url": "https://example.com", "screenshot": "viewport"})
    assert result["success"] is True
    assert result["screenshot"] == ""
    assert result["screenshot_file_id"] == ""
