"""
Validate inbound OAuth2 access tokens (JWT) for hosted MCP connections.

Clients obtain tokens from their IdP using the client credentials grant, then send:
    Authorization: Bearer <access_token>

We resolve the MCP server row by matching JWT ``iss`` + ``azp``/``client_id`` to stored
issuer URL and OAuth client id, then verify the JWT signature using OIDC discovery (JWKS).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx
import jwt
from jwt import PyJWKClient, PyJWTError

logger = logging.getLogger(__name__)

_OPENID_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_JWKS_CLIENT_CACHE: Dict[str, Tuple[float, PyJWKClient]] = {}
_CACHE_TTL_SEC = 3600


def normalize_issuer_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


async def fetch_openid_configuration(issuer_url: str) -> Dict[str, Any]:
    """Fetch OIDC discovery document (cached)."""
    base = normalize_issuer_url(issuer_url)
    now = time.time()
    cached = _OPENID_CACHE.get(base)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]

    discovery_url = f"{base}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(discovery_url)
        resp.raise_for_status()
        doc = resp.json()

    _OPENID_CACHE[base] = (now, doc)
    return doc


def _jwks_client_for_uri(jwks_uri: str) -> PyJWKClient:
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
    return claims.get("azp") or claims.get("client_id")


async def verify_oauth_access_token(
    token: str,
    expected_issuer_norm: str,
    audience: Optional[str],
) -> bool:
    """
    Verify JWT signature and issuer (and optional audience) using JWKS from OIDC discovery.
    ``expected_issuer_norm`` must match ``normalize_issuer_url`` of the stored issuer.
    """
    claims = unverified_jwt_claims(token)
    if not claims:
        return False

    token_iss = normalize_issuer_url(str(claims.get("iss", "")))
    if token_iss != expected_issuer_norm:
        logger.debug("MCP OAuth: issuer mismatch %s vs %s", token_iss, expected_issuer_norm)
        return False

    try:
        doc = await fetch_openid_configuration(expected_issuer_norm)
        jwks_uri = doc.get("jwks_uri")
        if not jwks_uri:
            logger.warning("MCP OAuth: missing jwks_uri in OIDC discovery for %s", expected_issuer_norm)
            return False

        jwks_client = _jwks_client_for_uri(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        decode_kwargs: Dict[str, Any] = {
            "algorithms": ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            "issuer": claims["iss"],
        }
        if audience:
            decode_kwargs["audience"] = audience

        jwt.decode(token, signing_key.key, **decode_kwargs)
        return True
    except PyJWTError as e:
        logger.info("MCP OAuth: JWT verification failed: %s", e)
        return False
    except httpx.HTTPError as e:
        logger.warning("MCP OAuth: OIDC/JWKS fetch failed: %s", e)
        return False
