"""Microsoft Entra ID (Azure AD) OIDC v2.0 — authorize URL, PKCE, token exchange, id_token validation."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

logger = logging.getLogger(__name__)


def _format_entra_token_error_response(response: httpx.Response) -> str:
    """Short, single-line summary from Entra OAuth error JSON (for logs / safe client hints)."""
    try:
        data = response.json()
        err = data.get("error") or "unknown_error"
        desc = data.get("error_description") or data.get("suberror") or ""
        if isinstance(desc, str):
            desc = " ".join(desc.split())[:400]
        out = f"{err}: {desc}".strip() if desc else str(err)
        return out[:500]
    except Exception:
        return (response.text or "")[:500]


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for S256 PKCE."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def build_authorize_url(
    *,
    entra_tenant_segment: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    base = f"https://login.microsoftonline.com/{entra_tenant_segment}/oauth2/v2.0/authorize"
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{base}?{urlencode(params)}"


async def exchange_authorization_code(
    *,
    entra_tenant_segment: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    token_url = f"https://login.microsoftonline.com/{entra_tenant_segment}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    own_client = client is None
    c = client or httpx.AsyncClient(timeout=30.0)
    try:
        r = await c.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        try:
            body = r.json()
        except Exception:
            raise ValueError("token_exchange:non_json_response") from None
        if isinstance(body, dict) and body.get("error") and not body.get("id_token"):
            detail = _format_entra_token_error_response(r)
            logger.warning("Entra token 200 with error payload: %s", detail)
            raise ValueError(f"token_exchange:{detail}") from None
        return body
    except httpx.HTTPStatusError as e:
        detail = _format_entra_token_error_response(e.response)
        logger.warning(
            "Entra token HTTP error: status=%s body=%s",
            e.response.status_code,
            detail,
        )
        raise ValueError(f"token_exchange:{detail}") from e
    except httpx.RequestError as e:
        logger.warning("Entra token request error: %s", e)
        raise ValueError(f"token_exchange:network:{type(e).__name__}") from e
    finally:
        if own_client:
            await c.aclose()


def validate_microsoft_id_token(
    id_token: str,
    *,
    client_id: str,
    expected_nonce: str,
    configured_entra_tenant_id: str | None,
) -> dict[str, Any]:
    """
    Verify RS256 signature via tenant JWKS, aud, iss, exp, and nonce.
    Issuer uses ``tid`` from the token (v2.0 format).
    """
    unverified = jwt.decode(id_token, options={"verify_signature": False})
    tid = unverified.get("tid")
    if not tid:
        raise ValueError("id_token_missing_tid")
    if unverified.get("nonce") != expected_nonce:
        raise ValueError("id_token_bad_nonce")

    if configured_entra_tenant_id and configured_entra_tenant_id.lower() not in (
        "common",
        "organizations",
        "consumers",
    ):
        if str(tid).lower() != str(configured_entra_tenant_id).lower():
            raise ValueError("id_token_tid_mismatch")

    issuer = f"https://login.microsoftonline.com/{tid}/v2.0"
    jwks_url = f"https://login.microsoftonline.com/{tid}/discovery/v2.0/keys"
    try:
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except PyJWTError as e:
        logger.warning("id_token JWT validation failed: %s", e)
        raise ValueError(f"id_token_jwt:{type(e).__name__}") from e
    except Exception as e:
        logger.warning("id_token JWKS/signing key error: %s", e)
        raise ValueError(f"id_token_jwks:{type(e).__name__}") from e


def claims_email(payload: dict[str, Any]) -> str | None:
    raw = payload.get("email") or payload.get("preferred_username") or payload.get("upn")
    if isinstance(raw, str) and "@" in raw:
        return raw.strip().lower()
    return None


def claims_entra_oid(payload: dict[str, Any]) -> str | None:
    oid = payload.get("oid") or payload.get("sub")
    if isinstance(oid, str) and oid.strip():
        return oid.strip()
    return None
