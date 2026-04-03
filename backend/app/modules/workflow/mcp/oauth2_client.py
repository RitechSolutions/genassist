"""
OAuth2 / OpenID Connect token manager for MCP client connections.

Supports:
- Client Credentials flow (machine-to-machine)
- OIDC Discovery (auto-detect token_url from /.well-known/openid-configuration)
- In-memory token caching with automatic expiry
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class _TokenCache:
    """Thread-safe in-memory token cache."""

    def __init__(self) -> None:
        self._store: Dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        token, expires_at = entry
        # 30-second safety buffer before actual expiry
        if time.monotonic() < expires_at - 30:
            return token
        del self._store[key]
        return None

    def set(self, key: str, token: str, expires_in: int) -> None:
        self._store[key] = (token, time.monotonic() + expires_in)


# Module-level singleton cache shared across all MCP connections
_cache = _TokenCache()


async def _discover_token_url(issuer_url: str) -> str:
    """
    Discover the token endpoint via OIDC Discovery.

    Fetches <issuer>/.well-known/openid-configuration and returns token_endpoint.
    """
    discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    logger.debug(f"OIDC discovery: fetching {discovery_url}")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(discovery_url)
        resp.raise_for_status()
        data = resp.json()

    token_url: Optional[str] = data.get("token_endpoint")
    if not token_url:
        raise ValueError(
            f"OIDC discovery at {discovery_url} did not return a token_endpoint"
        )
    logger.debug(f"OIDC discovery: resolved token_endpoint = {token_url}")
    return token_url


async def _client_credentials(config: Dict[str, Any]) -> str:
    """
    Obtain an access token using the OAuth2 Client Credentials flow.

    Required config keys:
        oauth2_client_id     (str)
        oauth2_client_secret (str)

    One of:
        oauth2_token_url     (str)  — direct token endpoint
        oauth2_issuer_url    (str)  — OIDC issuer, token URL auto-discovered

    Optional config keys:
        oauth2_scopes        (List[str])
        oauth2_audience      (str)   — some providers (Auth0, etc.) require this
    """
    client_id: str = config.get("oauth2_client_id", "")
    client_secret: str = config.get("oauth2_client_secret", "")
    token_url: Optional[str] = config.get("oauth2_token_url")
    issuer_url: Optional[str] = config.get("oauth2_issuer_url")
    scopes: List[str] = config.get("oauth2_scopes") or []
    audience: Optional[str] = config.get("oauth2_audience")

    if not client_id or not client_secret:
        raise ValueError(
            "OAuth2 Client Credentials flow requires oauth2_client_id and oauth2_client_secret"
        )

    # Resolve token URL
    if not token_url:
        if not issuer_url:
            raise ValueError(
                "OAuth2 config requires either oauth2_token_url or oauth2_issuer_url"
            )
        token_url = await _discover_token_url(issuer_url)

    # Check cache
    cache_key = f"cc:{client_id}:{token_url}:{' '.join(sorted(scopes))}"
    cached = _cache.get(cache_key)
    if cached:
        logger.debug(f"OAuth2: using cached token for client_id={client_id}")
        return cached

    # Build request payload
    payload: Dict[str, str] = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if scopes:
        payload["scope"] = " ".join(scopes)
    if audience:
        payload["audience"] = audience

    logger.debug(f"OAuth2: requesting new token from {token_url} for client_id={client_id}")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(token_url, data=payload)
        if resp.status_code >= 400:
            raise ValueError(
                f"OAuth2 token request failed ({resp.status_code}): {resp.text}"
            )
        token_data = resp.json()

    access_token: str = token_data.get("access_token", "")
    if not access_token:
        raise ValueError(f"OAuth2 response did not contain access_token: {token_data}")

    expires_in: int = int(token_data.get("expires_in", 3600))
    _cache.set(cache_key, access_token, expires_in)
    logger.debug(f"OAuth2: token obtained, expires_in={expires_in}s")
    return access_token


async def get_oauth2_token(config: Dict[str, Any]) -> str:
    """
    Public entry point: obtain an OAuth2 access token based on connection config.

    Dispatches to the correct flow based on config["oauth2_flow"].
    Currently supported flows:
        "client_credentials" (default)
    """
    flow: str = config.get("oauth2_flow", "client_credentials")

    if flow == "client_credentials":
        return await _client_credentials(config)

    raise ValueError(
        f"Unsupported OAuth2 flow '{flow}'. "
        "Supported flows: 'client_credentials'"
    )
