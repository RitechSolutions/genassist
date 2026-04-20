"""
Simulate OAuth2 + OIDC from a workflow MCP node perspective.

The node stores connectionConfig (HTTP/SSE) with auth_type oauth2; MCPConnectionManager
calls get_oauth2_token(), which performs OIDC discovery then client_credentials POST.

These tests mock httpx only — no real network or MCP server.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.mcp.mcp_client import MCPConnectionManager
from app.modules.workflow.mcp.oauth2_client import _cache


def _discovery_response(token_endpoint: str):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json.return_value = {"token_endpoint": token_endpoint}
    return r


def _token_response(access_token: str = "simulated_access_token", expires_in: int = 3600):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json.return_value = {"access_token": access_token, "expires_in": expires_in}
    return r


def _node_style_oauth2_config():
    """Same shape as frontend MCPDialog saves for OAuth2 / OIDC."""
    return {
        "url": "https://remote-mcp.example.com/mcp",
        "auth_type": "oauth2",
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "workflow-mcp-client",
        "oauth2_client_secret": "workflow-mcp-secret",
        "oauth2_issuer_url": "https://issuer.example.com/.well-known/openid-configuration",
        "oauth2_scopes": ["mcp.read"],
        "oauth2_audience": "https://remote-mcp.example.com",
    }


@pytest.mark.asyncio
async def test_simulate_node_http_oauth2_oidc_bearer_header():
    """HTTP MCP node: OIDC discovery + token POST → Authorization: Bearer …"""
    _cache._store.clear()

    discovery = _discovery_response("https://issuer.example.com/oauth/token")
    token_resp = _token_response("node_sim_token")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=discovery)
    mock_client.post = AsyncMock(return_value=token_resp)

    cfg = _node_style_oauth2_config()
    mgr = MCPConnectionManager("http", cfg)

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        header = await mgr._resolve_auth_header()

    assert header == "Bearer node_sim_token"

    mock_client.get.assert_called_once_with(
        "https://issuer.example.com/.well-known/openid-configuration"
    )
    post_url = mock_client.post.call_args[0][0]
    assert post_url == "https://issuer.example.com/oauth/token"
    payload = mock_client.post.call_args[1]["data"]
    assert payload["grant_type"] == "client_credentials"
    assert payload["client_id"] == "workflow-mcp-client"
    assert payload["client_secret"] == "workflow-mcp-secret"
    assert payload["scope"] == "mcp.read"
    assert payload["audience"] == "https://remote-mcp.example.com"


@pytest.mark.asyncio
async def test_simulate_node_sse_oauth2_same_as_http():
    """SSE MCP node uses the same _resolve_auth_header path as HTTP."""
    _cache._store.clear()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=_discovery_response("https://issuer.example.com/token"))
    mock_client.post = AsyncMock(return_value=_token_response("sse_tok"))

    cfg = _node_style_oauth2_config()
    mgr = MCPConnectionManager("sse", cfg)

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        header = await mgr._resolve_auth_header()

    assert header == "Bearer sse_tok"


@pytest.mark.asyncio
async def test_simulate_node_direct_token_url_skips_discovery():
    """Node with oauth2_token_url only: single POST, no openid-configuration GET."""
    _cache._store.clear()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_token_response("direct_tok"))

    cfg = {
        "url": "https://mcp.example.com/",
        "auth_type": "oauth2",
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "cid",
        "oauth2_client_secret": "sec",
        "oauth2_token_url": "https://auth.example.com/oauth2/token",
    }
    mgr = MCPConnectionManager("http", cfg)

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        header = await mgr._resolve_auth_header()

    assert header == "Bearer direct_tok"
    mock_client.get.assert_not_called()
    mock_client.post.assert_called_once_with(
        "https://auth.example.com/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "cid",
            "client_secret": "sec",
        },
    )
