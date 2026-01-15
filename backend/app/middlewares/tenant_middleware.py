import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette_context import context as sctx
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to extract tenant information from requests"""

    def get_tenant_slug(self, source_data: dict) -> str:
        tenant_header_name = settings.TENANT_HEADER_NAME.lower()

        # lowercase the keys of the source data to make the check case-insensitive
        source_data_lower = {k.lower(): v for k, v in source_data.items()}

        # check for multiple cases of the tenant header name
        if tenant_header_name in source_data_lower:
            return source_data_lower[tenant_header_name]
        return None

    async def dispatch(self, request: Request, call_next):
        if not settings.MULTI_TENANT_ENABLED:
            # Single tenant mode - no tenant resolution needed
            request.state.tenant_id = None
            request.state.tenant_slug = None
            return await call_next(request)

        tenant_slug = None

        # Method 1: Extract from header
        tenant_slug = self.get_tenant_slug(request.headers)
        
        # Method 2: Extract from query parameter (fallback when header not available)
        if not tenant_slug:
            tenant_slug = self.get_tenant_slug(request.query_params)

        # Method 3: Extract from subdomain (if enabled)
        if not tenant_slug and settings.TENANT_SUBDOMAIN_ENABLED:
            host = request.headers.get("host", "")
            if "." in host:
                subdomain = host.split(".")[0]
                if subdomain and subdomain != "www":
                    tenant_slug = subdomain

        # Store tenant information in request state
        request.state.tenant_id = tenant_slug
        request.state.tenant_slug = tenant_slug

        # Add tenant info to logging context
        if tenant_slug:
            sctx["tenant_slug"] = tenant_slug
            sctx["tenant_id"] = tenant_slug

        logger.info(
            f"Request processed with tenant_slug: {tenant_slug}, tenant_id: {tenant_slug}"
        )

        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(
                f"Request failed for tenant {tenant_slug} (id: {tenant_slug}): {e}"
            )
            raise
