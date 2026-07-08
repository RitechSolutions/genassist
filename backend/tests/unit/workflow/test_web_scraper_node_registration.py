"""Registration tests for WebScraperNode ("Web Scraper").

Asserts the node type is wired end-to-end: resolvable in the engine registry,
present in the dialog / handler / label schema maps, and excluded from the
no-DB deny-list. Plus focused process() tests (fetch_from_url mocked, the real
html2markdown left to run) that lock in the output contract and error handling.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

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


# registration


def test_node_type_resolves_to_class_in_engine_registry():
    """Engine registry maps the type to WebScraperNode after init."""
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is WebScraperNode


def test_node_type_present_in_dialog_schema():
    """Dialog schema is registered (builder can render the config dialog)."""
    assert _NODE_TYPE in NODE_DIALOG_SCHEMAS


def test_dialog_schema_contains_required_scraper_fields():
    """Dialog exposes url, format and renderJs; only url is required."""
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS[_NODE_TYPE]}
    assert {"url", "format", "renderJs"} <= set(schema)
    assert schema["url"].required is True


def test_node_type_present_in_handlers_with_input_and_output():
    """Handler schema declares both an input (target) and output (source) handler."""
    assert _NODE_TYPE in NODE_HANDLERS_SCHEMAS
    types = {h["type"] for h in NODE_HANDLERS_SCHEMAS[_NODE_TYPE]}
    assert "target" in types
    assert "source" in types


def test_node_type_label_registered():
    """Human label is registered for the node-type endpoint / log enrichment."""
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "Web Scraper"


def test_node_in_no_db_deny_list():
    """The node needs no DB access, so it must be in the engine's no-DB deny-list."""
    engine = WorkflowEngine.__new__(WorkflowEngine)
    assert engine._node_needs_db_access(_NODE_TYPE) is False


# process()


@pytest.mark.asyncio
async def test_markdown_success_returns_clean_envelope():
    node = _make_node()
    with patch(_FETCH_PATH, new=AsyncMock(return_value="<h1>Hi</h1>")):
        result = await node.process({"url": "https://example.com", "format": "markdown"})
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["format"] == "markdown"
    assert "Hi" in result["content"]
    assert result["error"] == ""


@pytest.mark.asyncio
async def test_both_format_includes_markdown_and_html_keys():
    node = _make_node()
    html = "<h1>Hi</h1>"
    with patch(_FETCH_PATH, new=AsyncMock(return_value=html)):
        result = await node.process({"url": "https://example.com", "format": "both"})
    assert result["html"] == html
    assert "Hi" in result["markdown"]
    assert result["content"] == result["markdown"]  # content holds the primary format


@pytest.mark.asyncio
async def test_render_js_off_uses_fast_httpx_path():
    node = _make_node()
    fetch = AsyncMock(return_value="<p>ok</p>")
    with patch(_FETCH_PATH, new=fetch):
        await node.process({"url": "https://example.com", "renderJs": False})
    assert fetch.call_args.kwargs["use_http_request"] is True


@pytest.mark.asyncio
async def test_render_js_on_uses_playwright_path():
    node = _make_node()
    fetch = AsyncMock(return_value="<p>ok</p>")
    with patch(_FETCH_PATH, new=fetch):
        await node.process({"url": "https://example.com", "renderJs": True})
    assert fetch.call_args.kwargs["use_http_request"] is False


@pytest.mark.asyncio
async def test_scheme_is_prepended_for_bare_host():
    node = _make_node()
    fetch = AsyncMock(return_value="<p>ok</p>")
    with patch(_FETCH_PATH, new=fetch):
        result = await node.process({"url": "example.com"})
    assert fetch.call_args.args[0] == "https://example.com"
    assert result["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_empty_url_returns_error_without_fetching():
    node = _make_node()
    fetch = AsyncMock(return_value="<p>ok</p>")
    with patch(_FETCH_PATH, new=fetch):
        result = await node.process({"url": "  "})
    assert result["success"] is False
    assert result["error"] == "URL is required"
    fetch.assert_not_awaited()


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
async def test_http_status_error_reports_real_status_code():
    node = _make_node()
    request = httpx.Request("GET", "https://example.com/missing")
    response = httpx.Response(404, request=request)
    error = httpx.HTTPStatusError("404", request=request, response=response)
    with patch(_FETCH_PATH, new=AsyncMock(side_effect=error)):
        result = await node.process({"url": "https://example.com/missing"})
    assert result["success"] is False
    assert result["status_code"] == 404
