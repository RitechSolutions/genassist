"""
Central logging configuration for the whole project.
Call  init_logging()  *once* early in startup (before anything logs).
"""

import logging
import os
import sys

from contextvars import ContextVar
from loguru import logger
from app.core.config.settings import settings
from app.core.project_path import DATA_VOLUME


# --------------------------------------------------------------------------- #
# Context variables that middlewares will fill in per-request
# --------------------------------------------------------------------------- #
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
ip_ctx: ContextVar[str] = ContextVar("ip", default="-")
method_ctx: ContextVar[str] = ContextVar("method", default="-")
path_ctx: ContextVar[str] = ContextVar("path", default="-")
status_ctx: ContextVar[int] = ContextVar("status", default=-1)
duration_ctx: ContextVar[int] = ContextVar("duration", default=-1)
uid_ctx: ContextVar[str] = ContextVar("uid", default="-")


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
            depth=6, exception=record.exc_info  # keep caller info accurate
        ).log(level, record.getMessage())


def _patch_stdlib(level: str) -> None:
    logging.root.setLevel(level)
    logging.root.handlers[:] = [_InterceptHandler()]  # replace all handlers
    # Silence overly-chatty libs if desired
    for noise in (
        "asyncio",
        "httpx",
        "pdfminer",
        "pdfminer.pdfinterp",
        "pdfminer.pdfparser",
        "pdfminer.psparser",
        "pdfminer.pdfdocument",
        "pdfminer.pdfpage",
        "pdfminer.pdfdevice",
        "pdfminer.cmapdb",
    ):
        logging.getLogger(noise).setLevel(logging.WARNING)


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def init_logging() -> None:
    # ----------- Sinks ------------------------------------------------------ #
    LOG_DIR = str(DATA_VOLUME / getattr(settings, "LOG_DIR", "logs"))
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
        enqueue=False,  # Disabled to avoid multiprocessing queue issues
    )

    # Rotating JSON files
    logger.add(
        f"{LOG_DIR}/access.log",
        level="INFO",
        filter=lambda r: r["level"].name == "INFO",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format=JSON_FORMAT,
        enqueue=False,
    )  # Disabled to avoid multiprocessing queue issues

    logger.add(
        f"{LOG_DIR}/error.log",
        level="ERROR",
        rotation="5 MB",
        retention="14 days",
        compression="zip",
        format=JSON_FORMAT,
        enqueue=False,
    )  # Disabled to avoid multiprocessing queue issues

    logger.add(
        f"{LOG_DIR}/app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="10 days",
        compression="zip",
        format=JSON_FORMAT,
        enqueue=False,
    )  # Disabled to avoid multiprocessing queue issues

    # Default values so “{extra[…]}” never fails
    logger.configure(
        extra={
            "request_id": "-",
            "ip": "-",
            "method": "-",
            "path": "-",
            "uid": "-",
            "status": "-",
            "duration": "-",
        }
    )

    # Feed stdlib logging into Loguru
    _patch_stdlib(settings.LOG_LEVEL)

    # Fine-tune noisy libraries
    for name, level in {
        "uvicorn": logging.INFO if settings.DEBUG is False else logging.DEBUG,
        "uvicorn.error": logging.INFO if settings.DEBUG is False else logging.DEBUG,
        "uvicorn.access": logging.INFO if settings.DEBUG is False else logging.DEBUG,
        "sqlalchemy.engine": (
            logging.WARNING if settings.DEBUG is False else logging.DEBUG
        ),
    }.items():
        logging.getLogger(name).setLevel(level)

    logger.info("✅ Loguru logging configured")
