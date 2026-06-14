"""Microsoft Entra ID OIDC routes (authorization code + PKCE)."""

from __future__ import annotations

import json
import logging
import secrets
from typing import Annotated
from urllib.parse import urljoin

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import RedirectResponse
from fastapi_injector import Injected
from pydantic import BaseModel, Field

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.sso.microsoft_entra_oidc import (
    build_authorize_url,
    claims_email,
    claims_entra_oid,
    exchange_authorization_code,
    generate_pkce_pair,
    validate_microsoft_id_token,
)
from app.core.tenant_scope import get_tenant_context, set_tenant_context
from app.dependencies.dependency_injection import RedisString
from app.dependencies.injector import injector
from app.middlewares.rate_limit_middleware import limiter
from app.services.auth import AuthService
from app.services.users import UserService

logger = logging.getLogger(__name__)

router = APIRouter()

STATE_PREFIX = "ms_oidc:state:"
HANDOFF_PREFIX = "ms_oidc:handoff:"


class MicrosoftSsoCompleteRequest(BaseModel):
    code: str = Field(..., min_length=8, max_length=256)


def _require_sso_feature() -> None:
    if not settings.SSO_MICROSOFT_ENABLED:
        raise AppException(status_code=404, error_key=ErrorKey.SSO_MICROSOFT_DISABLED)
    if not settings.microsoft_sso_is_configured():
        raise AppException(status_code=503, error_key=ErrorKey.SSO_MICROSOFT_NOT_CONFIGURED)


def _redis():
    return injector.get(RedisString)


@router.get("/sso/microsoft/status", summary="Whether Microsoft SSO is available")
async def microsoft_sso_status():
    return {
        "microsoft_sso_enabled": bool(
            settings.SSO_MICROSOFT_ENABLED and settings.microsoft_sso_is_configured()
        )
    }


@router.get("/sso/microsoft/start", summary="Begin Microsoft Entra sign-in (redirect)")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_HOUR}/hour")
async def microsoft_sso_start(request: Request):
    _require_sso_feature()
    redis = _redis()
    tenant_slug = get_tenant_context()
    nonce = secrets.token_urlsafe(16)
    state_key = secrets.token_urlsafe(24)
    code_verifier, code_challenge = generate_pkce_pair()
    payload = json.dumps(
        {
            "nonce": nonce,
            "code_verifier": code_verifier,
            "tenant_slug": tenant_slug,
        }
    )
    await redis.setex(f"{STATE_PREFIX}{state_key}", 600, payload)

    url = build_authorize_url(
        entra_tenant_segment=settings.SSO_MICROSOFT_ENTRA_TENANT_ID or "",
        client_id=settings.SSO_MICROSOFT_CLIENT_ID or "",
        redirect_uri=settings.SSO_MICROSOFT_REDIRECT_URI or "",
        state=state_key,
        nonce=nonce,
        code_challenge=code_challenge,
    )
    return RedirectResponse(url=url, status_code=302)


async def _load_oidc_state_and_set_tenant(state: str) -> dict:
    redis = _redis()
    raw = await redis.get(f"{STATE_PREFIX}{state}")
    if not raw:
        raise AppException(
            error_key=ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
            status_code=400,
            error_detail="missing_or_expired_oauth_state",
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise AppException(
            error_key=ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
            status_code=400,
            error_detail="invalid_oauth_state_json",
        ) from None
    tenant_slug = payload.get("tenant_slug") or "master"
    set_tenant_context(tenant_slug)
    return {"redis": redis, "payload": payload, "state": state}


@router.get("/sso/microsoft/callback", summary="OAuth redirect from Microsoft")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_HOUR}/hour")
async def microsoft_sso_callback(
    request: Request,
    code: str = Query(..., min_length=4),
    state: str = Query(..., min_length=16),
    auth_service: AuthService = Injected(AuthService),
    user_service: UserService = Injected(UserService),
):
    _require_sso_feature()
    ctx = await _load_oidc_state_and_set_tenant(state)
    redis = ctx["redis"]
    oidc = ctx["payload"]
    state_key = ctx["state"]

    async def _cleanup_state() -> None:
        await redis.delete(f"{STATE_PREFIX}{state_key}")

    try:
        token_json = await exchange_authorization_code(
            entra_tenant_segment=settings.SSO_MICROSOFT_ENTRA_TENANT_ID or "",
            client_id=settings.SSO_MICROSOFT_CLIENT_ID or "",
            client_secret=settings.SSO_MICROSOFT_CLIENT_SECRET or "",
            redirect_uri=settings.SSO_MICROSOFT_REDIRECT_URI or "",
            code=code,
            code_verifier=oidc["code_verifier"],
        )
        id_token = token_json.get("id_token")
        if not id_token:
            hint = ""
            if isinstance(token_json, dict):
                hint = (token_json.get("error") or "") + (
                    ": " + str(token_json.get("error_description", ""))[:200]
                    if token_json.get("error_description")
                    else ""
                )
            raise AppException(
                error_key=ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
                status_code=400,
                error_detail=("missing_id_token " + hint.strip()).strip()[:450],
            )

        id_payload = validate_microsoft_id_token(
            id_token,
            client_id=settings.SSO_MICROSOFT_CLIENT_ID or "",
            expected_nonce=oidc["nonce"],
            configured_entra_tenant_id=settings.SSO_MICROSOFT_ENTRA_TENANT_ID,
        )
        entra_oid = claims_entra_oid(id_payload)
        if not entra_oid:
            raise AppException(
                error_key=ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
                status_code=400,
                error_detail="missing_oid_or_sub_claim",
            )
        email = claims_email(id_payload)

        user = await user_service.resolve_user_for_microsoft_sso(entra_oid=entra_oid, email=email)
        tenant_id = get_tenant_context()
        token_data = {
            "sub": user.username,
            "user_id": str(user.id),
            "tenant_id": tenant_id,
            "origin": settings.LOCAL_FINE_TUNING_CALL_ORIGIN,
        }
        access_token = auth_service.create_access_token(data=token_data)
        refresh_token = auth_service.create_refresh_token(data=token_data)

        handoff = secrets.token_urlsafe(24)
        handoff_body = json.dumps(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "force_upd_pass_date": user.force_upd_pass_date.isoformat()
                if user.force_upd_pass_date
                else None,
            }
        )
        await redis.setex(f"{HANDOFF_PREFIX}{handoff}", 120, handoff_body)

        base = (settings.SSO_MICROSOFT_POST_LOGIN_FRONTEND_URL or "").rstrip("/") + "/"
        redirect_target = urljoin(base, f"login/sso-callback?sso_code={handoff}")
        if not settings.is_microsoft_sso_redirect_url_allowed(redirect_target):
            await redis.delete(f"{HANDOFF_PREFIX}{handoff}")
            raise AppException(
                error_key=ErrorKey.SSO_MICROSOFT_REDIRECT_NOT_ALLOWED,
                status_code=400,
            )
        await _cleanup_state()
        return RedirectResponse(url=redirect_target, status_code=302)
    except AppException:
        await _cleanup_state()
        raise
    except ValueError as e:
        await _cleanup_state()
        detail = str(e).strip()[:500] or "oauth_step_failed"
        logger.warning("Microsoft SSO callback step failed: %s", detail)
        raise AppException(
            error_key=ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
            status_code=400,
            error_detail=detail,
        ) from e
    except Exception as e:
        await _cleanup_state()
        logger.exception("Microsoft SSO callback failed")
        raise AppException(
            error_key=ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
            status_code=500,
            error_detail=f"unexpected:{type(e).__name__}",
            error_obj=e,
        ) from e


@router.post("/sso/microsoft/complete", summary="Exchange one-time SSO code for GenAssist tokens")
# Note: slowapi's @limiter.limit breaks OpenAPI / Pydantic resolution for this JSON body signature; keep unwrapped.
async def microsoft_sso_complete(
    request: Request,
    payload: Annotated[MicrosoftSsoCompleteRequest, Body()],
):
    _require_sso_feature()
    redis = _redis()
    key = f"{HANDOFF_PREFIX}{payload.code}"
    raw = await redis.get(key)
    if not raw:
        raise AppException(error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS, status_code=401)
    await redis.delete(key)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise AppException(error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS, status_code=401) from None
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_type": data.get("token_type", "bearer"),
        "force_upd_pass_date": data.get("force_upd_pass_date"),
    }
