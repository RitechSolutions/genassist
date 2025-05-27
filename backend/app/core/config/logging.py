"""
Central logging configuration for the whole project.
Call  init_logging()  *once* early in startup (before anything logs).
"""
import logging
import os
import sys
import time
import uuid
from typing import Dict

from fastapi import Request
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
from app.core.config.settings import settings
from starlette_context import context as sctx

# --------------------------------------------------------------------------- #
# Context variables that middlewares will fill in per-request
# --------------------------------------------------------------------------- #
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
ip_ctx:         ContextVar[str] = ContextVar("ip",         default="-")
method_ctx:     ContextVar[str] = ContextVar("method",     default="-")
path_ctx:       ContextVar[str] = ContextVar("path",       default="-")
status_ctx:     ContextVar[int] = ContextVar("status",     default=-1)
duration_ctx:   ContextVar[int] = ContextVar("duration",   default=-1)
uid_ctx:        ContextVar[str] = ContextVar("uid",        default="-")

# --------------------------------------------------------------------------- #
# Helper – forward stdlib logging records to Loguru
# --------------------------------------------------------------------------- #
class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.bind(**record.__dict__.get("extra", {})).opt(
            depth=6,  # keep caller info accurate
            exception=record.exc_info
        ).log(level, record.getMessage())

def _patch_stdlib(level: str) -> None:
    logging.root.setLevel(level)
    logging.root.handlers[:] = [_InterceptHandler()]   # replace all handlers
    # Silence overly-chatty libs if desired
    for noise in ("asyncio", "httpx"):
        logging.getLogger(noise).setLevel(logging.WARNING)

# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def init_logging() -> None:
    # ----------- Sinks ------------------------------------------------------ #
    LOG_DIR = getattr(settings, "LOG_DIR", "logs")
    os.makedirs(LOG_DIR, exist_ok=True)

    JSON_FORMAT = (
        '{{"timestamp":"{time:YYYY-MM-DD HH:mm:ss.SSS}",'
        '"level":"{level}",'
        '"message":{message!r},'
        '"file":"{file.name}","line":{line},"function":"{function}",'
        '"request_id":"{extra[request_id]}",'
        '"ip":"{extra[ip]}",'
        '"method":"{extra[method]}",'
        '"path":"{extra[path]}",'
        '"uid":"{extra[uid]}",'
        '"status":"{extra[status]}",'
        '"duration_ms":"{extra[duration]}"}}'
    )

    logger.remove()  # drop default stderr sink

    # Human-friendly console
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> "
            "<level>{level: <8}</level> "
            "[<cyan>{extra[request_id]}</cyan>] "
            "<cyan>{extra[ip]}</cyan> "
            "<blue>{extra[method]}</blue> "
            "<magenta>{extra[path]}</magenta> | "
            "<level>{message}</level>"
        ),
        enqueue=True,
    )

    # Rotating JSON files
    logger.add(f"{LOG_DIR}/access.log",
               level="INFO",
               filter=lambda r: r["level"].name == "INFO",
               rotation="10 MB", retention="7 days", compression="zip",
               format=JSON_FORMAT, enqueue=True)

    logger.add(f"{LOG_DIR}/error.log",
               level="ERROR",
               rotation="5 MB", retention="14 days", compression="zip",
               format=JSON_FORMAT, enqueue=True)

    logger.add(f"{LOG_DIR}/app.log",
               level="DEBUG",
               rotation="10 MB", retention="10 days", compression="zip",
               format=JSON_FORMAT, enqueue=True)

    # Default values so “{extra[…]}” never fails
    logger.configure(extra={
        "request_id": "-", "ip": "-", "method": "-", "path": "-",
        "uid": "-", "status": "-", "duration": "-"
    })

    # Feed stdlib logging into Loguru
    _patch_stdlib(settings.LOG_LEVEL)

    # Fine-tune noisy libraries
    for name, level in {
        "uvicorn":        logging.INFO if settings.DEBUG is False else logging.DEBUG,
        "uvicorn.error":  logging.INFO if settings.DEBUG is False else logging.DEBUG,
        "uvicorn.access": logging.INFO if settings.DEBUG is False else logging.DEBUG,
        "sqlalchemy.engine": logging.WARNING if settings.DEBUG is False else logging.DEBUG,
    }.items():
        logging.getLogger(name).setLevel(level)

    logger.info("✅ Loguru logging configured")


# --------------------------------------------------------------------------- #
# Middleware that writes request/response info into context vars
# --------------------------------------------------------------------------- #

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