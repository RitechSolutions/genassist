"""
Tests for MCPConnectionManager._resolve_auth_header

Verifies that the correct Authorization header is produced
for each auth_type (api_key, oauth2, none, default).

Run with:
    pytest backend/tests/mcp/test_mcp_client_auth.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.modules.workflow.mcp.mcp_client import MCPConnectionManager


def _manager(config: dict) -> MCPConnectionManager:
    return MCPConnectionManager(connection_type="http", connection_config=config)


# ---------------------------------------------------------------------------
# auth_type = "api_key" (explicit)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_key_explicit_returns_bearer():
    mgr = _manager({"url": "https://mcp.example.com", "auth_type": "api_key", "api_key": "sk-123"})
    header = await mgr._resolve_auth_header()
    assert header == "Bearer sk-123"


@pytest.mark.asyncio
async def test_api_key_strips_redundant_bearer_prefix():
    mgr = _manager(
        {
            "url": "https://mcp.example.com",
            "auth_type": "api_key",
            "api_key": "Bearer  sk-abc",
        }
    )
    header = await mgr._resolve_auth_header()
    assert header == "Bearer sk-abc"


@pytest.mark.asyncio
async def test_api_key_missing_returns_none():
    """auth_type=api_key but no key → no header (don't crash)."""
    mgr = _manager({"url": "https://mcp.example.com", "auth_type": "api_key"})
    header = await mgr._resolve_auth_header()
    assert header is None


# ---------------------------------------------------------------------------
# auth_type absent (backward-compat default)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_default_falls_back_to_api_key():
    mgr = _manager({"url": "https://mcp.example.com", "api_key": "legacy-key"})
    header = await mgr._resolve_auth_header()
    assert header == "Bearer legacy-key"


@pytest.mark.asyncio
async def test_default_no_key_returns_none():
    mgr = _manager({"url": "https://mcp.example.com"})
    header = await mgr._resolve_auth_header()
    assert header is None


# ---------------------------------------------------------------------------
# auth_type = "none"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_none_auth_returns_none():
    mgr = _manager({"url": "https://mcp.example.com", "auth_type": "none"})
    header = await mgr._resolve_auth_header()
    assert header is None


# ---------------------------------------------------------------------------
# auth_type = "oauth2"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oauth2_uses_token_from_manager():
    config = {
        "url": "https://mcp.example.com",
        "auth_type": "oauth2",
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "cid",
        "oauth2_client_secret": "cs",
        "oauth2_token_url": "https://auth.example.com/token",
    }
    mgr = _manager(config)

    with patch(
        "app.modules.workflow.mcp.mcp_client.get_oauth2_token",
        new=AsyncMock(return_value="oauth2_access_token"),
    ) as mock_get_token:
        header = await mgr._resolve_auth_header()

    assert header == "Bearer oauth2_access_token"
    mock_get_token.assert_awaited_once_with(config)


@pytest.mark.asyncio
async def test_oauth2_propagates_error():
    config = {
        "url": "https://mcp.example.com",
        "auth_type": "oauth2",
    }
    mgr = _manager(config)

    with patch(
        "app.modules.workflow.mcp.mcp_client.get_oauth2_token",
        new=AsyncMock(side_effect=ValueError("bad config")),
    ):
        with pytest.raises(ValueError, match="bad config"):
            await mgr._resolve_auth_header()
