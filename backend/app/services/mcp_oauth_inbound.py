"""
Validate inbound OAuth2 access tokens (JWT) for hosted MCP connections.

Clients obtain tokens from their IdP using the client credentials grant, then send:
    Authorization: Bearer <access_token>

Inbound JWTs are matched to an MCP server row (by client id hash). Verification loads the
OIDC discovery document from the configured issuer URL (full path to openid-configuration),
then validates ``iss`` against the document's ``issuer``, signature via ``jwks_uri``, and
optional ``aud`` / scope claims from stored settings.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
import ipaddress
import jwt
from jwt import PyJWKClient, PyJWTError
from urllib.parse import urlparse

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

_OPENID_DOC_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_JWKS_CLIENT_CACHE: Dict[str, Tuple[float, PyJWKClient]] = {}
_CACHE_TTL_SEC = 3600
_MAX_OIDC_DOC_BYTES = 1_048_576  # 1 MiB


def normalize_issuer_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def normalize_issuer_url_full(url: str) -> str:
    """
    Normalize a full OpenID configuration document URL.

    Stored as ``oauth2_issuer_url`` in auth_values.
    """
    return (url or "").strip()


def resolve_oauth2_issuer_url(auth_values: Dict[str, Any]) -> str:
    """
    Effective OpenID configuration document URL for stored MCP oauth2 auth_values.

    Stored key is ``oauth2_issuer_url`` (full URL to openid-configuration).
    """
    raw = auth_values.get("oauth2_issuer_url")
    if raw is None or not str(raw).strip():
        return ""
    return normalize_issuer_url_full(str(raw))


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _is_blocked_host(host: str) -> bool:
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
    Validate URLs used for inbound OIDC discovery / JWKS fetching (SSRF guardrails).

    - Require HTTPS by default.
    - Allow HTTP only for localhost / IP literals in DEBUG (local dev / tests).
    - Block obvious private/localhost targets unless DEBUG.
    """
    raw = normalize_issuer_url_full(url)
    if not raw:
        raise ValueError("OIDC discovery URL is required")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    host = parsed.hostname or ""

    if scheme not in {"https", "http"}:
        raise ValueError("OIDC discovery URL must be http(s)")

    if scheme != "https":
        if not settings.DEBUG:
            raise ValueError("OIDC discovery URL must use https")
        if host.lower() not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Refusing insecure OIDC discovery URL outside localhost")

    if _is_blocked_host(host) and not settings.DEBUG:
        raise ValueError("Refusing to fetch OIDC discovery from private/localhost host")

    return raw


async def _fetch_json_limited(url: str, *, timeout: float) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if len(resp.content or b"") > _MAX_OIDC_DOC_BYTES:
            raise ValueError("OIDC discovery response too large")
        return resp.json()


async def fetch_openid_configuration_document(discovery_url: str) -> Dict[str, Any]:
    """Fetch OIDC discovery document from its full URL (cached)."""
    url = _validate_oidc_fetch_url(discovery_url)
    now = time.time()
    cached = _OPENID_DOC_CACHE.get(url)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]

    doc = await _fetch_json_limited(url, timeout=20.0)

    _OPENID_DOC_CACHE[url] = (now, doc)
    return doc


async def fetch_openid_configuration(issuer_url: str) -> Dict[str, Any]:
    """Legacy: resolve discovery from issuer base URL (no trailing slash)."""
    base = normalize_issuer_url(issuer_url)
    discovery_url = f"{base}/.well-known/openid-configuration"
    return await fetch_openid_configuration_document(discovery_url)


def _jwks_client_for_uri(jwks_uri: str) -> PyJWKClient:
    # Basic SSRF guardrail: jwks_uri comes from the discovery document (network-fetched).
    _validate_oidc_fetch_url(str(jwks_uri))
    now = time.time()
    cached = _JWKS_CLIENT_CACHE.get(jwks_uri)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]
    client = PyJWKClient(jwks_uri)
    _JWKS_CLIENT_CACHE[jwks_uri] = (now, client)
    return client


def looks_like_jwt(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


def unverified_jwt_claims(token: str) -> Optional[Dict[str, Any]]:
    if not looks_like_jwt(token):
        return None
    try:
        return jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
            },
        )
    except PyJWTError:
        return None


def extract_oauth_client_id_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    """
    Pick the OAuth client / application id from JWT claims for MCP server row lookup.

    IdPs use different claim names:
    - ``azp``, ``client_id``: OIDC / Auth0 / Keycloak (common)
    - ``clientId``: occasional camelCase payloads
    - ``appid``: Azure AD / Entra access tokens
    - ``sub`` when ``idtyp`` is ``app`` / ``application``: Azure-style app-only tokens
    """
    for key in ("azp", "client_id", "clientId", "appid"):
        raw = claims.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()

    idtyp = str(claims.get("idtyp") or "").lower()
    if idtyp in {"app", "application"}:
        raw = claims.get("sub")
        if raw is not None and str(raw).strip():
            return str(raw).strip()

    return None


def _aud_claim_as_str_list(raw: Any) -> List[str]:
    """Normalize JWT ``aud`` claim (string or list) to comparable strings."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [str(raw).strip()] if str(raw).strip() else []


def _expected_audiences_from_config(audience: Optional[str]) -> List[str]:
    """Split optional comma-separated ``oauth2_audience`` into stripped non-empty parts."""
    if audience is None or not str(audience).strip():
        return []
    return [p.strip() for p in str(audience).split(",") if p.strip()]


def _token_audience_matches_allowlist(token_aud: Any, expected: List[str]) -> bool:
    """
    True if the token's ``aud`` intersects ``expected`` (case-insensitive).

    Comma-separated ``oauth2_audience`` is an allowlist: the token is valid if any configured
    value matches any value in the token's ``aud`` (string or list).

    Empty ``expected`` means do not require an ``aud`` claim.
    """
    if not expected:
        return True
    token_auds = {a.lower() for a in _aud_claim_as_str_list(token_aud)}
    if not token_auds:
        return False
    allowed = {e.lower() for e in expected}
    return bool(token_auds & allowed)


def _token_scope_claim_set(claims: Dict[str, Any]) -> Set[str]:
    """Normalize ``scope`` / ``scp`` claims to a lowercase set of space-separated tokens."""
    s: Set[str] = set()
    for key in ("scope", "scp"):
        raw = claims.get(key)
        if isinstance(raw, str):
            for p in raw.split():
                if p.strip():
                    s.add(p.strip().lower())
        elif isinstance(raw, list):
            for x in raw:
                if isinstance(x, str) and x.strip():
                    s.add(x.strip().lower())
    return s


def _required_scopes_from_config(scope_config: Optional[str]) -> Set[str]:
    if scope_config is None or not str(scope_config).strip():
        return set()
    return {p.strip().lower() for p in str(scope_config).split() if p.strip()}


def _token_satisfies_required_scopes(claims: Dict[str, Any], required: Set[str]) -> bool:
    """Every required scope must appear in the token's scope/scp claims."""
    if not required:
        return True
    present = _token_scope_claim_set(claims)
    return required <= present


async def verify_oauth_access_token(
    token: str,
    issuer_url: str,
    audience: Optional[str],
    required_scopes: Optional[str] = None,
) -> bool:
    """
    Verify JWT using JWKS from OIDC discovery.

    ``issuer_url`` must be the full URL of the openid-configuration document.
    The JWT ``iss`` must match the ``issuer`` field from that document (after normalization).
    """
    disc = normalize_issuer_url_full(issuer_url)
    if not disc:
        return False

    audience_raw: Optional[str] = None
    if audience is not None:
        audience_raw = str(audience).strip() or None
    expected_audiences = _expected_audiences_from_config(audience_raw)
    need_scopes = _required_scopes_from_config(required_scopes)

    claims = unverified_jwt_claims(token)
    if not claims:
        return False

    try:
        doc = await fetch_openid_configuration_document(disc)
        issuer_from_doc = normalize_issuer_url(str(doc.get("issuer") or ""))
        if not issuer_from_doc:
            logger.warning("MCP OAuth: discovery document missing issuer for %s", disc)
            return False

        token_iss = normalize_issuer_url(str(claims.get("iss", "")))
        if token_iss != issuer_from_doc:
            logger.debug("MCP OAuth: issuer mismatch %s vs %s", token_iss, issuer_from_doc)
            return False

        jwks_uri = doc.get("jwks_uri")
        if not jwks_uri:
            logger.warning("MCP OAuth: missing jwks_uri in OIDC discovery for %s", disc)
            return False

        jwks_client = _jwks_client_for_uri(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        decode_kwargs: Dict[str, Any] = {
            "algorithms": [
                "RS256", "RS384", "RS512",
                "PS256", "PS384", "PS512",
                "ES256", "ES384", "ES512",
            ],
            "issuer": claims["iss"],
            "leeway": 120,
            "options": {"verify_aud": False},
        }

        decoded = jwt.decode(token, signing_key.key, **decode_kwargs)

        if expected_audiences:
            token_aud = decoded.get("aud")
            if not _token_audience_matches_allowlist(token_aud, expected_audiences):
                logger.warning(
                    "MCP OAuth: audience mismatch (token aud=%r, "
                    "expected oauth2_audience=%r).",
                    token_aud,
                    expected_audiences,
                )
                return False

        if need_scopes and not _token_satisfies_required_scopes(decoded, need_scopes):
            logger.warning(
                "MCP OAuth: scope mismatch (token scopes=%r, required oauth2_scope=%r).",
                _token_scope_claim_set(decoded),
                need_scopes,
            )
            return False

        return True
    except PyJWTError as e:
        logger.info("MCP OAuth: JWT verification failed: %s", e)
        return False
    except httpx.HTTPError as e:
        logger.warning("MCP OAuth: OIDC/JWKS fetch failed: %s", e)
        return False
