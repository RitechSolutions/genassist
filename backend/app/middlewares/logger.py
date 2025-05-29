import inspect
from fastapi import Request
import logging

logger = logging.getLogger(__name__)

async def log_request_info(request: Request, call_next):
    """Logs request details before processing."""
    frame = inspect.currentframe()
    func_name = frame.f_back.f_code.co_name if frame and frame.f_back else "Unknown"

    # Get request headers
    content_type = request.headers.get("content-type", "")

    # Only log body for non-binary requests
    if "multipart/form-data" in content_type or "application/octet-stream" in content_type:
        request_text = "[Binary data skipped]"
    else:
        request_data = await request.body()
        request_text = request_data.decode("utf-8", errors="ignore") if request_data else None


    request_info = (
        f"➡️ {request.method} {request.url}, Function: {func_name}\n"
        f"➡️ Headers: {dict(request.headers)}\n"
        f"➡️ Query params: {request.query_params}\n"
        f"➡️ Body: {request_text}"
    )
    logger.debug("%s", request_info)

    response = await call_next(request)
    return response