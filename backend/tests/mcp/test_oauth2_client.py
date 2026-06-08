"""
Unit tests for the OAuth2 / OIDC token manager.

Run with:
    pytest backend/tests/mcp/test_oauth2_client.py -v
"""

import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Module under test
from app.modules.workflow.mcp.oauth2_client import (
    _TokenCache,
    _cache,
    get_oauth2_token,
)


# ---------------------------------------------------------------------------
# _TokenCache
# ---------------------------------------------------------------------------

class TestTokenCache:
    def test_miss_on_empty(self):
        cache = _TokenCache()
        assert cache.get("key") is None

    def test_hit_before_expiry(self):
        cache = _TokenCache()
        cache.set("key", "tok123", expires_in=3600)
        assert cache.get("key") == "tok123"

    def test_miss_after_expiry(self):
        cache = _TokenCache()
        cache.set("key", "tok123", expires_in=3600)
        # Manually push expiry into the past
        cache._store["key"] = ("tok123", time.monotonic() - 1)
        assert cache.get("key") is None

    def test_miss_within_safety_buffer(self):
        """Tokens expiring within 30 s should be considered stale."""
        cache = _TokenCache()
        cache.set("key", "tok123", expires_in=3600)
        # Expiry is 20 s from now — inside the 30 s buffer
        cache._store["key"] = ("tok123", time.monotonic() + 20)
        assert cache.get("key") is None

    def test_overwrite(self):
        cache = _TokenCache()
        cache.set("key", "first", expires_in=3600)
        cache.set("key", "second", expires_in=3600)
        assert cache.get("key") == "second"


# ---------------------------------------------------------------------------
# get_oauth2_token — unsupported flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unsupported_flow_raises():
    with pytest.raises(ValueError, match="Unsupported OAuth2 flow"):
        await get_oauth2_token({"oauth2_flow": "authorization_code"})


# ---------------------------------------------------------------------------
# Client Credentials — validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_client_credentials_missing_credentials():
    with pytest.raises(ValueError, match="oauth2_client_id and oauth2_client_secret"):
        await get_oauth2_token({
            "oauth2_flow": "client_credentials",
            "oauth2_token_url": "https://auth.example.com/token",
        })


@pytest.mark.asyncio
async def test_client_credentials_missing_token_url():
    with pytest.raises(ValueError, match="oauth2_token_url or oauth2_issuer_url"):
        await get_oauth2_token({
            "oauth2_flow": "client_credentials",
            "oauth2_client_id": "cid",
            "oauth2_client_secret": "csecret",
        })


# ---------------------------------------------------------------------------
# Client Credentials — successful token fetch
# ---------------------------------------------------------------------------

def _mock_token_response(token: str = "access_tok", expires_in: int = 3600):
    """Return an httpx.Response-like mock for a successful token endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": token, "expires_in": expires_in}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@pytest.mark.asyncio
async def test_client_credentials_direct_token_url(monkeypatch):
    """Token fetched from explicit token_url without OIDC discovery."""
    # Clear cache between tests
    _cache._store.clear()

    config = {
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "my-client",
        "oauth2_client_secret": "my-secret",
        "oauth2_token_url": "https://auth.example.com/token",
        "oauth2_scopes": ["read", "write"],
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_token_response("tok_abc"))

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        token = await get_oauth2_token(config)

    assert token == "tok_abc"
    # Verify payload sent to token endpoint
    call_kwargs = mock_client.post.call_args
    payload = call_kwargs[1]["data"] if "data" in call_kwargs[1] else call_kwargs[0][1]
    assert payload["grant_type"] == "client_credentials"
    assert payload["client_id"] == "my-client"
    assert payload["scope"] == "read write"


@pytest.mark.asyncio
async def test_client_credentials_cached_on_second_call(monkeypatch):
    """Second call with same config returns cached token without HTTP request."""
    _cache._store.clear()

    config = {
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "cached-client",
        "oauth2_client_secret": "cached-secret",
        "oauth2_token_url": "https://auth.example.com/token",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_token_response("tok_cached"))

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        token1 = await get_oauth2_token(config)
        token2 = await get_oauth2_token(config)

    assert token1 == token2 == "tok_cached"
    # HTTP call should only happen once
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_client_credentials_with_audience(monkeypatch):
    """audience param is forwarded when provided."""
    _cache._store.clear()

    config = {
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "cid",
        "oauth2_client_secret": "cs",
        "oauth2_token_url": "https://auth.example.com/token",
        "oauth2_audience": "https://api.example.com",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_token_response("tok_aud"))

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        await get_oauth2_token(config)

    payload = mock_client.post.call_args[1]["data"]
    assert payload["audience"] == "https://api.example.com"


# ---------------------------------------------------------------------------
# OIDC Discovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oidc_discovery_resolves_token_url(monkeypatch):
    """token_url is discovered from /.well-known/openid-configuration."""
    _cache._store.clear()

    discovery_resp = MagicMock()
    discovery_resp.status_code = 200
    discovery_resp.raise_for_status = MagicMock()
    discovery_resp.json.return_value = {
        "token_endpoint": "https://auth.example.com/discovered/token"
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=discovery_resp)
    mock_client.post = AsyncMock(return_value=_mock_token_response("tok_discovered"))

    config = {
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "cid",
        "oauth2_client_secret": "cs",
        "oauth2_issuer_url": "https://auth.example.com/.well-known/openid-configuration",
    }

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        token = await get_oauth2_token(config)

    assert token == "tok_discovered"
    # Discovery GET called with correct URL
    mock_client.get.assert_called_once_with(
        "https://auth.example.com/.well-known/openid-configuration"
    )
    # Token POST called with discovered endpoint
    mock_client.post.assert_called_once()
    assert mock_client.post.call_args[0][0] == "https://auth.example.com/discovered/token"


@pytest.mark.asyncio
async def test_oidc_discovery_full_configuration_url(monkeypatch):
    """oauth2_issuer_url may be the full openid-configuration URL."""
    _cache._store.clear()

    discovery_resp = MagicMock()
    discovery_resp.status_code = 200
    discovery_resp.raise_for_status = MagicMock()
    discovery_resp.json.return_value = {
        "token_endpoint": "https://auth.example.com/v1/token"
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=discovery_resp)
    mock_client.post = AsyncMock(return_value=_mock_token_response("tok_full"))

    full_url = "http://localhost:8000/.well-known/openid-configuration"
    config = {
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "cid",
        "oauth2_client_secret": "cs",
        "oauth2_issuer_url": full_url,
    }

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        token = await get_oauth2_token(config)

    assert token == "tok_full"
    mock_client.get.assert_called_once_with(full_url)


@pytest.mark.asyncio
async def test_oidc_discovery_missing_token_endpoint():
    """Raises if discovery response has no token_endpoint."""
    _cache._store.clear()

    discovery_resp = MagicMock()
    discovery_resp.status_code = 200
    discovery_resp.raise_for_status = MagicMock()
    discovery_resp.json.return_value = {}  # no token_endpoint

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=discovery_resp)

    config = {
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "cid",
        "oauth2_client_secret": "cs",
        "oauth2_issuer_url": "https://auth.example.com",
    }

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="did not return a token_endpoint"):
            await get_oauth2_token(config)


# ---------------------------------------------------------------------------
# Token endpoint errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_endpoint_error_raises(monkeypatch):
    """HTTP 4xx/5xx from the token endpoint raises ValueError."""
    _cache._store.clear()

    error_resp = MagicMock()
    error_resp.status_code = 401
    error_resp.text = '{"error":"invalid_client"}'

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=error_resp)

    config = {
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "bad",
        "oauth2_client_secret": "creds",
        "oauth2_token_url": "https://auth.example.com/token",
    }

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="token request failed"):
            await get_oauth2_token(config)


@pytest.mark.asyncio
async def test_empty_access_token_raises(monkeypatch):
    """Response missing access_token key raises ValueError."""
    _cache._store.clear()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}  # no access_token

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    config = {
        "oauth2_flow": "client_credentials",
        "oauth2_client_id": "cid",
        "oauth2_client_secret": "cs",
        "oauth2_token_url": "https://auth.example.com/token",
    }

    with patch("app.modules.workflow.mcp.oauth2_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="did not contain access_token"):
            await get_oauth2_token(config)
