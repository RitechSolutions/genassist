"""Process() tests for HtmlToImageNode.

Locks in the HTML-resolution precedence (upstream string/dict over config),
the render-arg forwarding, PNG hosting via FileManagerService and the
never-raise failure envelope.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.workflow.engine.nodes.html_to_image_node import HtmlToImageNode

_RENDER_PATH = "app.modules.workflow.engine.nodes.html_to_image_node.render_html_to_image"


def _make_node(source_output=None):
    node_config = {"type": "htmlToImageNode", "data": {"name": "HTML to Image"}}
    node = HtmlToImageNode("node-1", node_config, SimpleNamespace())
    # process() calls get_input_from_source(); stub it so no workflow state is needed
    node.get_input_from_source = lambda: source_output
    return node


def _fake_file_manager(url="http://localhost:8000/api/file-manager/files/f1/source", file_id="f1"):
    provider = SimpleNamespace(name="local", get_base_path=lambda: "/data")
    return SimpleNamespace(
        initialize=AsyncMock(return_value=provider),
        create_file_from_local_path=AsyncMock(return_value=SimpleNamespace(id=file_id)),
        get_file_url=AsyncMock(return_value=url),
    )


def _fake_injector(file_manager, app_settings):
    from app.services.app_settings import AppSettingsService
    from app.services.file_manager import FileManagerService

    def _get(cls):
        if cls is FileManagerService:
            return file_manager
        if cls is AppSettingsService:
            return app_settings
        raise KeyError(cls)

    return SimpleNamespace(get=_get)


def _patch_hosting(fm):
    app_settings = SimpleNamespace(get_by_type_and_name=AsyncMock(return_value=None))
    return patch("app.dependencies.injector.injector", _fake_injector(fm, app_settings))


@pytest.mark.asyncio
async def test_config_html_renders_and_hosts_png():
    node = _make_node(source_output=None)
    fm = _fake_file_manager()
    render = AsyncMock(return_value=b"pngbytes")
    with patch(_RENDER_PATH, new=render), _patch_hosting(fm):
        result = await node.process({"html": "<h1>Hi</h1>"})
    assert result["success"] is True
    assert result["image"] == "http://localhost:8000/api/file-manager/files/f1/source"
    assert result["image_file_id"] == "f1"
    assert result["error"] == ""
    render.assert_awaited_once()
    fm.create_file_from_local_path.assert_awaited_once()


@pytest.mark.asyncio
async def test_render_called_with_expected_capture_and_viewport_args():
    node = _make_node(source_output=None)
    fm = _fake_file_manager()
    render = AsyncMock(return_value=b"pngbytes")
    with patch(_RENDER_PATH, new=render), _patch_hosting(fm):
        await node.process(
            {
                "html": "<h1>Hi</h1>",
                "captureMode": "viewport",
                "viewportWidth": "800",  # float-string coerces via _as_int
                "viewportHeight": 600,
                "waitFor": "250",
            }
        )
    kwargs = render.call_args.kwargs
    assert kwargs["full_page"] is False
    assert kwargs["viewport_width"] == 800
    assert kwargs["viewport_height"] == 600
    assert kwargs["wait_for_ms"] == 250


@pytest.mark.asyncio
async def test_full_page_is_default_capture_mode():
    node = _make_node(source_output=None)
    fm = _fake_file_manager()
    render = AsyncMock(return_value=b"pngbytes")
    with patch(_RENDER_PATH, new=render), _patch_hosting(fm):
        await node.process({"html": "<h1>Hi</h1>"})
    assert render.call_args.kwargs["full_page"] is True
    assert render.call_args.kwargs["viewport_width"] == 1280
    assert render.call_args.kwargs["viewport_height"] == 720


@pytest.mark.asyncio
async def test_upstream_string_overrides_config_html():
    node = _make_node(source_output="<p>from upstream</p>")
    fm = _fake_file_manager()
    render = AsyncMock(return_value=b"pngbytes")
    with patch(_RENDER_PATH, new=render), _patch_hosting(fm):
        result = await node.process({"html": "<h1>config</h1>"})
    assert result["success"] is True
    assert render.call_args.args[0] == "<p>from upstream</p>"


@pytest.mark.asyncio
async def test_upstream_dict_html_key_is_unwrapped():
    node = _make_node(source_output={"html": "<p>dict html</p>", "content": "ignored"})
    fm = _fake_file_manager()
    render = AsyncMock(return_value=b"pngbytes")
    with patch(_RENDER_PATH, new=render), _patch_hosting(fm):
        await node.process({"html": "<h1>config</h1>"})
    assert render.call_args.args[0] == "<p>dict html</p>"


@pytest.mark.asyncio
async def test_upstream_dict_falls_back_to_content_key():
    node = _make_node(source_output={"content": "<p>from content</p>"})
    fm = _fake_file_manager()
    render = AsyncMock(return_value=b"pngbytes")
    with patch(_RENDER_PATH, new=render), _patch_hosting(fm):
        await node.process({"html": "<h1>config</h1>"})
    assert render.call_args.args[0] == "<p>from content</p>"


@pytest.mark.asyncio
async def test_empty_html_returns_failure_without_rendering():
    node = _make_node(source_output=None)
    render = AsyncMock(return_value=b"pngbytes")
    with patch(_RENDER_PATH, new=render):
        result = await node.process({"html": "   "})
    assert result["success"] is False
    assert result["image"] == ""
    assert result["image_file_id"] == ""
    assert result["error"] == "HTML content is required"
    render.assert_not_awaited()


@pytest.mark.asyncio
async def test_render_value_error_returns_failure_envelope():
    node = _make_node(source_output=None)
    render = AsyncMock(side_effect=ValueError("HTML content is required"))
    with patch(_RENDER_PATH, new=render):
        result = await node.process({"html": "<h1>Hi</h1>"})
    assert result["success"] is False
    assert result["error"] == "HTML content is required"


@pytest.mark.asyncio
async def test_render_unexpected_error_is_swallowed_to_failure():
    node = _make_node(source_output=None)
    render = AsyncMock(side_effect=RuntimeError("chromium crashed"))
    with patch(_RENDER_PATH, new=render):
        result = await node.process({"html": "<h1>Hi</h1>"})
    assert result["success"] is False
    assert "chromium crashed" in result["error"]
