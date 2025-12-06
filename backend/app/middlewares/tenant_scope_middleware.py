import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.tenant_scope import set_tenant_context, clear_tenant_context

logger = logging.getLogger(__name__)


class TenantScopeMiddleware(BaseHTTPMiddleware):
    """Middleware to set tenant context for dependency injection"""

    async def dispatch(self, request: Request, call_next):
        # Get tenant_id from request state (set by TenantMiddleware)
        tenant_id = getattr(request.state, "tenant_id", None)
        set_tenant_context(tenant_id if tenant_id else "master")

        try:
            response = await call_next(request)
            return response
        finally:
            # Clear tenant context after request
            clear_tenant_context()
