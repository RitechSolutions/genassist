import json
import logging
import os
import re
from fastapi import Request, WebSocket, WebSocketException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from app.core.exceptions.error_messages import ErrorKey, get_error_message
from app.core.exceptions.exception_classes import AppException


logger = logging.getLogger(__name__)


def init_error_handlers(app):
    @app.exception_handler(AppException)
    def handle_app_exception(request: Request, error: AppException):
        if error.error_detail:
            logger.exception(error.error_detail)
        logger.info(f"Handled bad request: {error}")
        response = {
            "error": get_error_message(
                request=request,
                error_key=error.error_key,
                error_variables=error.error_variables,
            ),
            "error_code": error.status_code,
            "error_key": error.error_key.value,
            "error_detail": error.error_detail if os.getenv("ENV") == "dev" else None,
        }
        return JSONResponse(
            content=jsonable_encoder(response), status_code=error.status_code
        )

    # Regex for:  Key (name)=(Summarizer12) already exists.
    _DUP_DETAIL_RE = re.compile(r"Key \((?P<field>[^)]+)\)=\((?P<value>[^)]+)\)")

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        orig = exc.orig  # asyncpg UniqueViolationError
        if getattr(orig, "sqlstate", "") != "23505":  # not a duplicate-key error
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
                "error": (
                    f"{field}='{value}' already exists" if field else "Duplicate value"
                ),
            },
        )

    @app.exception_handler(500)
    def handle_internal_server_error(request: Request, _: Exception):
        response = {
            "error": get_error_message(
                error_key=ErrorKey.INTERNAL_ERROR, request=request
            ),
        }
        return JSONResponse(content=jsonable_encoder(response), status_code=500)

    @app.exception_handler(WebSocketException)
    async def websocket_exception_handler(
        websocket: WebSocket, exc: WebSocketException
    ):
        # exc.code is the close-code we set above
        await websocket.close(code=exc.code, reason=exc.reason or "WebSocket error")


async def send_socket_error(
    websocket: WebSocket, error_key: ErrorKey, lang: str = "en"
):
    await websocket.send_text(
        json.dumps(
            {
                "type": "error",
                "error": get_error_message(error_key, lang=lang),
                "error_key": error_key.value,
            }
        )
    )
