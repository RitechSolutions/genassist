import re
import time
import uuid
from typing import Dict, Pattern

from loguru import logger
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette_context import context as sctx
from starlette_context.middleware import RawContextMiddleware
from starlette_context.plugins import RequestIdPlugin

from app import settings
from app.core.config.logging import (
    duration_ctx,
    ip_ctx,
    method_ctx,
    path_ctx,
    request_id_ctx,
    status_ctx,
    uid_ctx,
)
from app.middlewares.rate_limit_middleware import _request_context
from app.middlewares.session_cleanup_middleware import TransactionMiddleware
from app.middlewares.tenant_middleware import TenantMiddleware
from app.middlewares.tenant_scope_middleware import TenantScopeMiddleware


def get_allowed_origins() -> list[str]:
    """
    Get the list of allowed CORS origins.
    Merges default origins with additional origins from CORS_ALLOWED_ORIGINS environment variable.
    """
    default_origins = [
        "http://localhost:8080",
        "http://localhost:8002",
        "http://localhost:3000",
        "http://localhost:8022",  # plugin-js example widget
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8022",
    ]

    # Start with default origins
    allowed_origins = default_origins.copy()

    # Add additional origins from environment variable if provided
    if settings.CORS_ALLOWED_ORIGINS:
        # Parse comma-separated origins and strip whitespace
        additional_origins = [origin.strip() for origin in settings.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]
        # Add unique origins only
        for origin in additional_origins:
            # Never allow wildcard origins here. With allow_credentials=True, "*" is unsafe and
            # also not permitted by the CORS spec for credentialed requests.
            if origin == "*":
                logger.warning("Ignoring CORS_ALLOWED_ORIGINS='*' because credentials are enabled")
                continue
            if origin not in allowed_origins:
                allowed_origins.append(origin)

    return allowed_origins


_static_allowed_origins: set[str] | None = None


def _get_static_origins() -> set[str]:
    global _static_allowed_origins
    if _static_allowed_origins is None:
        _static_allowed_origins = set(get_allowed_origins())
    return _static_allowed_origins


# Sentinel distinguishes "not yet compiled" from "compiled to None" (no/invalid regex).
_UNCOMPILED: object = object()
_agent_origin_regex: Pattern[str] | None | object = _UNCOMPILED


def _get_agent_origin_regex() -> Pattern[str] | None:
    """
    Compile (once) the optional regex that a dynamic per-agent Origin must match
    before AgentCORSMiddleware will reflect it. Returns None when unconfigured or
    invalid, in which case dynamic origins are reflected unrestricted.
    """
    global _agent_origin_regex
    if _agent_origin_regex is _UNCOMPILED:
        pattern = settings.CORS_AGENT_ALLOWED_ORIGIN_REGEX
        compiled: Pattern[str] | None = None
        if pattern:
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                logger.error(f"Invalid CORS_AGENT_ALLOWED_ORIGIN_REGEX, ignoring it: {exc}")
        else:
            logger.info(
                "CORS_AGENT_ALLOWED_ORIGIN_REGEX is not set; AgentCORSMiddleware will reflect "
                "any non-static Origin. Set it to restrict dynamic agent origins."
            )
        _agent_origin_regex = compiled
    return _agent_origin_regex  # type: ignore[return-value]


def _is_allowed_dynamic_origin(origin: str) -> bool:
    """
    Whether a non-static Origin may be reflected with credentials. When no regex is
    configured we preserve the historical reflect-any behavior; when one is configured
    the Origin must match it.
    """
    regex = _get_agent_origin_regex()
    if regex is None:
        return True
    # fullmatch (not match) so a pattern for "https://app.example.com" cannot be
    # bypassed by a suffixed origin like "https://app.example.com.attacker.com".
    return regex.fullmatch(origin) is not None


class AgentCORSMiddleware(BaseHTTPMiddleware):
    """
    Dynamic CORS for origins not in the global static list.

    Origins configured per-agent in the database are unknown to the global
    CORSMiddleware.  This middleware sits *before* it: if the requesting
    Origin is already in the static list it defers to CORSMiddleware;
    otherwise it reflects the Origin so per-agent origins work.

    Security: all endpoints authenticate via API key / JWT (not cookies),
    so reflecting the origin does not enable CSRF today. As defense in depth
    against a future shift to cookie auth, a non-static Origin is only reflected
    when it passes ``CORS_AGENT_ALLOWED_ORIGIN_REGEX`` (when configured).
    """

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if not origin or origin in _get_static_origins():
            return await call_next(request)

        # Unknown (per-agent) origin: only reflect it if it passes the configured
        # allowlist/regex. Otherwise fall through without credentialed CORS headers
        # so the browser blocks the cross-origin request.
        if not _is_allowed_dynamic_origin(origin):
            if request.method == "OPTIONS":
                return Response(status_code=400)
            return await call_next(request)

        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": request.headers.get("access-control-request-method", "*"),
                    "Access-Control-Allow-Headers": request.headers.get("access-control-request-headers", "*"),
                    "Access-Control-Allow-Credentials": "true",
                },
            )

        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response


def build_middlewares() -> list[Middleware]:
    """
    Middlewares that must run **before** user-code.
    Order matters:

    1. RawContextMiddleware – creates `starlette_context` and the X-Request-ID header.
    2. TenantMiddleware – extracts tenant information from requests.
    3. RequestContextMiddleware – copies data into the Loguru ContextVars and
       times the request.
    4. CORS – normal cross-origin checks.
    """
    middlewares = [
        # 1️⃣  Generates a request-scoped UUID and puts it in `request.headers`
        Middleware(
            RawContextMiddleware,
            plugins=(RequestIdPlugin(),),
        ),
    ]

    # 2️⃣  Tenant resolution (only if multi-tenancy is enabled)
    if settings.MULTI_TENANT_ENABLED:
        middlewares.append(Middleware(TenantMiddleware))
        # Add tenant scope middleware after tenant middleware
        middlewares.append(Middleware(TenantScopeMiddleware))

    middlewares.extend(
        [
            # 3️⃣  Fills Loguru context vars, measures duration, etc.
            Middleware(RequestContextMiddleware),
            # 4️⃣  Agent-route preflight handler (must sit before CORSMiddleware)
            Middleware(AgentCORSMiddleware),
            # 5️⃣  CORS
            Middleware(
                CORSMiddleware,
                allow_origins=get_allowed_origins(),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
            Middleware(VersionHeaderMiddleware),
            # 6️⃣  DB transaction boundary — must be the *innermost* user middleware so
            #     it runs inside the tenant scope (tenant context still active when it
            #     commits/rolls back the request-scoped session after the endpoint).
            Middleware(TransactionMiddleware),
        ]
    )

    return middlewares


# -------------------------------------------------------------------------------- #
# Middleware that writes request/response info into context vars for loguru logging
# -------------------------------------------------------------------------------- #


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Logs start/end of every request and populates Loguru ContextVars."""

    async def dispatch(self, request: Request, call_next):
        # Set request in context for rate limit functions
        _request_context.set(request)

        start = time.perf_counter()

        # ------------------------------------------------------------------ #
        # 1️⃣  Prepare contextual values
        # ------------------------------------------------------------------ #
        rid = (
            sctx.get("X-Request-ID")  # created by RequestIdPlugin
            or request.headers.get("X-Request-ID")  # client-supplied
            or str(uuid.uuid4())  # last-chance fallback
        )
        ip = request.client.host if request.client else "-"
        meth = request.method
        pth = request.url.path
        uid = getattr(getattr(request.state, "user", None), "id", "guest")

        # ------------------------------------------------------------------ #
        # 2️⃣  Set ContextVars *and keep the tokens* so we can restore later
        # ------------------------------------------------------------------ #
        tokens: Dict = {
            request_id_ctx: request_id_ctx.set(rid),
            ip_ctx: ip_ctx.set(ip),
            method_ctx: method_ctx.set(meth),
            path_ctx: path_ctx.set(pth),
            uid_ctx: uid_ctx.set(uid),
        }

        # ------------------------------------------------------------------ #
        # 3️⃣  Log “request started”
        # ------------------------------------------------------------------ #
        logger.bind(request_id=rid, ip=ip, method=meth, path=pth, uid=uid).info("➡️  Request start")

        try:
            # Do the work
            response = await call_next(request)
            code = response.status_code
            ok = True
        except Exception as exc:
            code = 500
            ok = False
            raise exc
        finally:
            # ------------------------------------------------------------------ #
            # 4️⃣  Compute duration and fill the remaining vars
            # ------------------------------------------------------------------ #
            dur_ms = (time.perf_counter() - start) * 1000
            status_ctx.set(code)
            duration_ctx.set(f"{dur_ms:.2f}")

            bind_common = dict(
                request_id=rid,
                ip=ip,
                method=meth,
                path=pth,
                uid=uid,
                status=code,
                duration=f"{dur_ms:.2f}",
            )

            if ok:
                logger.bind(**bind_common).info(f"✅ Request handled {code}")
            else:
                logger.bind(**bind_common).error(f"❌ Request error {code}")

            # ------------------------------------------------------------------ #
            # 5️⃣  Always restore ContextVars to previous state
            # ------------------------------------------------------------------ #
            for var, token in tokens.items():
                var.reset(token)
            # duration_ctx and status_ctx were never set before, no tokens
            duration_ctx.set(-1)
            status_ctx.set(-1)

        return response


# --------------------------------------------------------------------------- #
# Middleware that writes API version in response headers
# --------------------------------------------------------------------------- #


class VersionHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-API-Version"] = str(settings.API_VERSION)

        # If behind a proxy that terminates TLS, ensure redirects use https
        # this might not be the right place for this logic, but it's convenient
        if response.status_code == 307 and request.headers.get("x-forwarded-proto") == "https":
            response.headers["Location"] = response.headers["Location"].replace("http://", "https://")

        return response
