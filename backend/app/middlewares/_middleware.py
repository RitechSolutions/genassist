import time
import uuid
from typing import Dict
from loguru import logger
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette_context import context as sctx
from starlette_context.middleware import RawContextMiddleware
from starlette_context.plugins import RequestIdPlugin

from app.middlewares.tenant_middleware import TenantMiddleware
from app.middlewares.tenant_scope_middleware import TenantScopeMiddleware
from app.middlewares.rate_limit_middleware import _request_context
from app.middlewares.session_cleanup_middleware import SessionCleanupMiddleware
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


def get_allowed_origins() -> list[str]:
    """
    Get the list of allowed CORS origins.
    Merges default origins with additional origins from CORS_ALLOWED_ORIGINS environment variable.
    """
    default_origins = [
        "http://localhost:8080",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
    ]

    # Start with default origins
    allowed_origins = default_origins.copy()

    # Add additional origins from environment variable if provided
    if settings.CORS_ALLOWED_ORIGINS:
        # Parse comma-separated origins and strip whitespace
        additional_origins = [
            origin.strip()
            for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]
        # Add unique origins only
        for origin in additional_origins:
            if origin not in allowed_origins:
                allowed_origins.append(origin)

    return allowed_origins


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
            # 4️⃣  Ensures database sessions are closed after each request
            # Middleware(SessionCleanupMiddleware),
            # 5️⃣  CORS
            Middleware(
                CORSMiddleware,
                allow_origins=get_allowed_origins(),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
            Middleware(VersionHeaderMiddleware),
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
        logger.bind(request_id=rid, ip=ip, method=meth, path=pth, uid=uid).info(
            "➡️  Request start"
        )

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
        if (
            response.status_code == 307
            and request.headers.get("x-forwarded-proto") == "https"
        ):
            response.headers["Location"] = response.headers["Location"].replace(
                "http://", "https://"
            )

        return response
