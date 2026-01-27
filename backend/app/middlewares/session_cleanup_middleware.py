"""
Middleware to ensure database sessions are properly closed after each request.

This middleware ensures that AsyncSession instances created via dependency injection
are properly closed when the request completes, preventing connection leaks.
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


class SessionCleanupMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures database sessions are closed after each request.

    This is necessary because fastapi-injector's enable_cleanup might not properly
    handle async cleanup of AsyncSession.close(). This middleware explicitly closes
    any sessions created during the request.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and ensure session cleanup"""
        try:
            # Process the request
            response = await call_next(request)
            return response
        finally:
            # Always cleanup session, even if request failed
            try:
                # Try to get the session from the injector
                # This will only work if a session was created in this request scope
                try:
                    session = injector.get(AsyncSession)
                    if session and not session.close():
                        await session.close()
                        logger.debug("Closed database session after request")
                except Exception as e:  # pylint: disable=broad-except
                    # Session might not exist or already closed - this is fine
                    logger.debug(f"Session cleanup: {e}")
            except Exception as e:  # pylint: disable=broad-except
                # Injector might not have a session - this is fine
                logger.debug(f"Could not cleanup session: {e}")
