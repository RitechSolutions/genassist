"""
OAuth2 / OpenID Connect token manager for MCP client connections.

Supports:
- Client Credentials flow (machine-to-machine)
- OIDC Discovery (auto-detect token_url from /.well-known/openid-configuration)
- In-memory token caching with automatic expiry
"""

import ipaddress
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

_MAX_OIDC_DOC_BYTES = 1_048_576  # 1 MiB


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _is_blocked_host(host: str) -> bool:
    """
    Return True if the host is an obvious SSRF target.

    We block localhost and private/loopback/link-local IP literals. We *do not* resolve DNS
    (hostnames can still point to private IPs); this is a best-effort guardrail.
    """
    h = (host or "").strip().lower()
    if not h:
        return True
    if h in {"localhost"}:
        return True
    if _is_ip_literal(h):
        ip = ipaddress.ip_address(h)
        return bool(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    return False


def _validate_oidc_fetch_url(url: str) -> str:
    """
    Validate URLs used for OIDC discovery / token endpoint fetches (SSRF guardrails).

    - Require HTTPS by default.
    - Allow HTTP only for localhost / IP literals in DEBUG (local dev / tests).
    - Block obvious private/localhost targets unless DEBUG.
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("OIDC discovery URL is required")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    host = parsed.hostname or ""

    if scheme not in {"https", "http"}:
        raise ValueError("OIDC discovery URL must be http(s)")

    if scheme != "https":
        # Local dev / tests only.
        if not settings.DEBUG:
            raise ValueError("OIDC discovery URL must use https")
        if host.lower() not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Refusing insecure OIDC discovery URL outside localhost")

    if _is_blocked_host(host) and not settings.DEBUG:
        raise ValueError("Refusing to fetch OIDC discovery from private/localhost host")

    return raw


async def _fetch_json_limited(url: str, *, timeout: float) -> Dict[str, Any]:
    """
    Fetch JSON with a response size cap to reduce SSRF blast radius.
    """
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        # Best-effort size cap: relies on content already buffered by httpx.
        if len(resp.content or b"") > _MAX_OIDC_DOC_BYTES:
            raise ValueError("OIDC discovery response too large")
        return resp.json()


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


async def _discover_token_url_from_document(issuer_url: str) -> str:
    """
    Fetch the openid-configuration document at ``issuer_url`` and return token_endpoint.
    """
    url = _validate_oidc_fetch_url(issuer_url)
    logger.debug("OIDC discovery: fetching %s", url)
    data = await _fetch_json_limited(url, timeout=10)

    token_url: Optional[str] = data.get("token_endpoint")
    if not token_url:
        raise ValueError(
            f"OIDC discovery at {url} did not return a token_endpoint"
        )
    logger.debug("OIDC discovery: resolved token_endpoint = %s", token_url)
    return token_url

async def _client_credentials(config: Dict[str, Any]) -> str:
    """
    Obtain an access token using the OAuth2 Client Credentials flow.

    Required config keys:
        oauth2_client_id     (str)
        oauth2_client_secret (str)

    One of:
        oauth2_token_url       (str)  — direct token endpoint
        oauth2_issuer_url      (str)  — full openid-configuration URL (preferred)

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
        iss = (issuer_url or "").strip()
        if iss:
            token_url = await _discover_token_url_from_document(iss)
        else:
            raise ValueError("OAuth2 config requires oauth2_token_url or oauth2_issuer_url")

    # Check cache (audience affects token content for many providers, e.g. Auth0)
    aud_key = audience or ""
    # Include issuer_url too (some deployments share token URLs across issuers/tenants).
    iss_key = (issuer_url or "").strip()
    cache_key = f"cc:{client_id}:{token_url}:{' '.join(sorted(scopes))}:{aud_key}:{iss_key}"
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
