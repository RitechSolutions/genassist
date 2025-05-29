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

from app import settings
from app.core.config.logging import duration_ctx, ip_ctx, method_ctx, path_ctx, request_id_ctx, status_ctx, uid_ctx


ALLOWED_ORIGINS = [
    "http://localhost",
    "https://localhost",
    "http://localhost:8080",
    "https://localhost:8080",
    "http://localhost:8081",
    "http://localhost:8081",
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:8080",
    "https://127.0.0.1:8080",
    "http://0.0.0.0:3000",
    "https://0.0.0.0:3000",
    "http://0.0.0.0:8080",
    "https://0.0.0.0:8080",
    "https://genassist.ritech.io",
    "https://genassist-dev.ritech.io",
    "https://genassist-test.ritech.io",
    "https://genassist.ritech.io",
]


def build_middlewares() -> list[Middleware]:
    """
    Middlewares that must run **before** user-code.
    Order matters:

    1. RawContextMiddleware – creates `starlette_context` and the X-Request-ID header.
    2. RequestContextMiddleware – copies data into the Loguru ContextVars and
       times the request.
    3. CORS – normal cross-origin checks.
    """
    return [
        # 1️⃣  Generates a request-scoped UUID and puts it in `request.headers`
        Middleware(
            RawContextMiddleware,
            plugins=(RequestIdPlugin(),),
        ),
        # 2️⃣  Fills Loguru context vars, measures duration, etc.
        Middleware(RequestContextMiddleware),
        # 3️⃣  CORS
        Middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(VersionHeaderMiddleware),

    ]

# -------------------------------------------------------------------------------- #
# Middleware that writes request/response info into context vars for loguru logging
# -------------------------------------------------------------------------------- #

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Logs start/end of every request and populates Loguru ContextVars."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        # ------------------------------------------------------------------ #
        # 1️⃣  Prepare contextual values
        # ------------------------------------------------------------------ #
        rid = (
                sctx.get("X-Request-ID")  # created by RequestIdPlugin
                or request.headers.get("X-Request-ID")  # client-supplied
                or str(uuid.uuid4())  # last-chance fallback
        )
        ip   = request.client.host if request.client else "-"
        meth = request.method
        pth  = request.url.path
        uid  = getattr(getattr(request.state, "user", None), "id", "guest")

        # ------------------------------------------------------------------ #
        # 2️⃣  Set ContextVars *and keep the tokens* so we can restore later
        # ------------------------------------------------------------------ #
        tokens: Dict = {
            request_id_ctx: request_id_ctx.set(rid),
            ip_ctx:         ip_ctx.set(ip),
            method_ctx:     method_ctx.set(meth),
            path_ctx:       path_ctx.set(pth),
            uid_ctx:        uid_ctx.set(uid),
        }

        # ------------------------------------------------------------------ #
        # 3️⃣  Log “request started”
        # ------------------------------------------------------------------ #
        logger.bind(request_id=rid, ip=ip, method=meth, path=pth, uid=uid) \
              .info("➡️  Request start")

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
                logger.bind(**bind_common).info("✅ Request handled")
            else:
                logger.bind(**bind_common).exception("❌ Request error")

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
        return response