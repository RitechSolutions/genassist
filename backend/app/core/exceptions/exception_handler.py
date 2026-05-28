import json
import logging
import os
import re

from fastapi import Request, WebSocket, WebSocketException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.error_messages import ErrorKey, get_error_message
from app.core.exceptions.exception_classes import AppException, UpstreamServiceError

logger = logging.getLogger(__name__)

_SSO_CLIENT_ERROR_KEYS = frozenset(
    {
        ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
        ErrorKey.SSO_MICROSOFT_USER_DENIED,
        ErrorKey.SSO_MICROSOFT_REDIRECT_NOT_ALLOWED,
        ErrorKey.SSO_MICROSOFT_NOT_CONFIGURED,
        ErrorKey.SSO_MICROSOFT_DISABLED,
    }
)


def _sanitize_public_error_detail(text: str, max_len: int = 450) -> str:
    """Single-line hint for API clients; strips obvious secret patterns."""
    if not text:
        return ""
    t = " ".join(str(text).split())
    t = re.sub(
        r"(client_secret|client_assertion|password|refresh_token|code_verifier)=[^\s&\"']+",
        r"\1=***",
        t,
        flags=re.I,
    )
    return t[:max_len]


def _response_error_detail(error: AppException) -> str | None:
    raw = (error.error_detail or "").strip()
    if not raw:
        return None
    sanitized = _sanitize_public_error_detail(raw)
    if not sanitized:
        return None
    if os.getenv("ENV") == "dev":
        return sanitized
    if error.error_key in _SSO_CLIENT_ERROR_KEYS:
        return sanitized
    return None


def init_error_handlers(app):
    @app.exception_handler(AppException)
    def handle_app_exception(request: Request, error: AppException):
        if error.error_detail:
            logger.exception(error.error_detail)
        logger.info(f"Handled bad request: {error}")
        response = {
            'error': get_error_message(request=request, error_key=error.error_key, error_variables=error.error_variables),
            'error_code': error.status_code,
            'error_key': error.error_key.value,
            'error_detail': _response_error_detail(error),
            }
        return JSONResponse(content=jsonable_encoder(response), status_code=error.status_code)

    @app.exception_handler(UpstreamServiceError)
    def handle_upstream_service_error(request: Request, error: UpstreamServiceError):
        """Return the upstream response body unchanged so its error envelope
        (already client-safe) reaches the caller without re-wrapping."""
        logger.info(f"Forwarding upstream error: {error.status_code} {error.body}")
        return JSONResponse(content=jsonable_encoder(error.body), status_code=error.status_code)

    # Regex for:  Key (name)=(Summarizer12) already exists.
    _DUP_DETAIL_RE = re.compile(
            r"Key \((?P<field>[^)]+)\)=\((?P<value>[^)]+)\)"
            )


    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        orig = exc.orig
        sqlstate = getattr(orig, "sqlstate", "")

        # Role delete: SQLAlchemy may try to null FKs on user_roles/api_key_roles; role_id is NOT NULL.
        if sqlstate == "23502":
            detail_lower = (getattr(orig, "detail", "") or str(exc)).lower()
            if "role_id" in detail_lower and (
                "user_roles" in detail_lower or "api_key_roles" in detail_lower
            ):
                msg = get_error_message(
                    request=request, error_key=ErrorKey.ROLE_CANNOT_DELETE_IN_USE
                )
                return JSONResponse(
                    status_code=409,
                    content=jsonable_encoder(
                        {
                            "error": msg,
                            "error_code": 409,
                            "error_key": ErrorKey.ROLE_CANNOT_DELETE_IN_USE.value,
                            "error_detail": None,
                        }
                    ),
                )

        if sqlstate != "23505":  # not a duplicate-key error
            raise exc  # let FastAPI handle anything else

        #  asyncpg sometimes gives column_name directly
        field = getattr(orig, "column_name", None)
        value = None

        # Parse the DETAIL string for field + value
        detail: str = getattr(orig, "detail", "") or str(orig)
        m = _DUP_DETAIL_RE.search(detail)
        if m:
            field = field or m.group("field")
            value = m.group("value")

        # Build a uniform response
        # TODO Handle multi language
        return JSONResponse(
                status_code=400,
                content={
                    "error": f"{field}='{value}' already exists" if field else "Duplicate value",
                    },
                )


    @app.exception_handler(500)
    def handle_internal_server_error(request: Request, _: Exception):
        response = {
            "error": get_error_message(error_key=ErrorKey.INTERNAL_ERROR, request=request),
            }
        return JSONResponse(content=jsonable_encoder(response), status_code=500)


    @app.exception_handler(WebSocketException)
    async def websocket_exception_handler(websocket: WebSocket, exc: WebSocketException):
        # exc.code is the close-code we set above
        await websocket.close(code=exc.code, reason=exc.reason or "WebSocket error")


async def send_socket_error(websocket: WebSocket, error_key: ErrorKey, lang: str = "en"):
    await websocket.send_text(json.dumps({
        "type": "error",
        "error": get_error_message(error_key, lang=lang),
        "error_key": error_key.value,
        }))

