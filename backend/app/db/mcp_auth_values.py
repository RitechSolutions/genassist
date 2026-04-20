"""
Shape of ``mcp_servers.auth_values`` (JSONB) by ``auth_type``.

api_key
    api_key_encrypted (str)
    api_key_hash (str)

oauth2
    oauth2_client_id_encrypted (str)
    oauth2_client_secret_encrypted (str)
    oauth2_issuer_url (str) — full URL to openid-configuration; primary for OIDC
    oauth2_scope (str | null) — space-separated; optional inbound scope/scp check
    oauth2_audience (str | null) — optional JWT aud allowlist (legacy / advanced)
    oauth2_client_id_hash (str)
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def api_key_auth_values(*, api_key_encrypted: str, api_key_hash: str) -> Dict[str, Any]:
    return {"api_key_encrypted": api_key_encrypted, "api_key_hash": api_key_hash}


def oauth2_auth_values(
    *,
    oauth2_client_id_encrypted: str,
    oauth2_client_secret_encrypted: str,
    oauth2_issuer_url: str,
    oauth2_client_id_hash: str,
    oauth2_scope: Optional[str] = None,
    oauth2_audience: Optional[str] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "oauth2_client_id_encrypted": oauth2_client_id_encrypted,
        "oauth2_client_secret_encrypted": oauth2_client_secret_encrypted,
        "oauth2_issuer_url": oauth2_issuer_url,
        "oauth2_client_id_hash": oauth2_client_id_hash,
    }
    if oauth2_audience is not None:
        out["oauth2_audience"] = oauth2_audience
    if oauth2_scope is not None and str(oauth2_scope).strip():
        out["oauth2_scope"] = str(oauth2_scope).strip()
    return out


def merge_oauth2_auth_values(existing: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new dict for oauth2 auth_values after applying updates (skip None values)."""
    base = {k: v for k, v in existing.items() if str(k).startswith("oauth2_")}
    for k, v in updates.items():
        if v is None:
            continue
        if k == "oauth2_audience" and v == "":
            base.pop("oauth2_audience", None)
        elif k == "oauth2_scope" and v == "":
            base.pop("oauth2_scope", None)
        elif k == "oauth2_issuer_url" and v == "":
            base.pop("oauth2_issuer_url", None)
        else:
            base[k] = v
    return base
