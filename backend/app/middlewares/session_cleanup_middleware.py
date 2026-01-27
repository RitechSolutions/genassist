"""
Middleware for cleaning up AsyncSession instances at the end of each request.

This ensures that database connections are properly returned to the pool,
preventing connection leaks when using DI-injected sessions.
"""
import logging
from contextvars import ContextVar
from typing import List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Context variable to store sessions that need cleanup at end of request
_sessions_to_cleanup: ContextVar[List[AsyncSession]] = ContextVar(
    "sessions_to_cleanup", default=None
)


def register_session_for_cleanup(session: AsyncSession) -> None:
    """
    Register an AsyncSession instance to be closed at the end of the request.

    Call this when creating a session via DI to ensure it gets cleaned up.
    """
    sessions = _sessions_to_cleanup.get()
    if sessions is None:
        sessions = []
        _sessions_to_cleanup.set(sessions)
    sessions.append(session)
    logger.debug(f"Registered session for cleanup. Total pending: {len(sessions)}")


def get_sessions_for_cleanup() -> List[AsyncSession]:
    """Get all sessions registered for cleanup in the current request context."""
    return _sessions_to_cleanup.get() or []


def clear_session_cleanup_registry() -> None:
    """Clear the session cleanup registry for the current request context."""
    _sessions_to_cleanup.set(None)


class AsyncSessionCleanupMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures all DI-injected AsyncSession instances are properly
    closed at the end of each request, returning connections to the pool.
    """

    async def dispatch(self, request: Request, call_next):
        # Initialize the cleanup registry for this request
        _sessions_to_cleanup.set([])

        try:
            response = await call_next(request)
            return response
        finally:
            # Clean up all registered sessions
            sessions = get_sessions_for_cleanup()
            for session in sessions:
                try:
                    if session.is_active:
                        # Rollback any uncommitted transaction
                        await session.rollback()
                    await session.close()
                    logger.debug("Closed DI-injected AsyncSession")
                except Exception as e:
                    logger.warning(f"Error closing session during cleanup: {e}")

            if sessions:
                logger.debug(f"Cleaned up {len(sessions)} AsyncSession(s)")

            # Clear the registry
            clear_session_cleanup_registry()
