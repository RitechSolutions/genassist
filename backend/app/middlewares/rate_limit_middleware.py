"""
Rate Limiting Middleware for FastAPI

This middleware provides rate limiting and throttling capabilities using slowapi.
It supports both Redis and in-memory storage backends.
"""

import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request

from app.core.config.settings import settings
from app.core.rate_limit_utils import RATE_LIMIT_GLOBAL_HOUR, RATE_LIMIT_GLOBAL_MINUTE

logger = logging.getLogger(__name__)


def get_user_identifier(request: Request) -> str:
    """
    Get a unique identifier for rate limiting.
    Prefers authenticated user ID, falls back to IP address.
    """
    # # Try to get user ID from request state (set by auth middleware)
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return f"user:{user.id}"

    # Fall back to IP address
    return get_remote_address(request)


def get_conversation_identifier(request: Request) -> str:
    """
    Get conversation_id from path parameters for rate limiting.
    Falls back to user identifier if conversation_id is not found.
    """
    # Try to get conversation_id from path parameters (available after route matching)
    path_params = getattr(request, "path_params", {})
    if path_params and "conversation_id" in path_params:
        conversation_id = path_params["conversation_id"]
        return f"conversation:{conversation_id}"

    # Fall back to user identifier if conversation_id not found
    return get_user_identifier(request)


# Initialize limiter with custom key function
limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=[RATE_LIMIT_GLOBAL_MINUTE, RATE_LIMIT_GLOBAL_HOUR],
    enabled=settings.RATE_LIMIT_ENABLED,
)


def init_rate_limiter(app):
    """
    Initialize rate limiting on the FastAPI app.
    This should be called during app initialization.
    """
    if not settings.RATE_LIMIT_ENABLED:
        logger.info("Rate limiting is disabled")
        return

    try:
        # Configure storage backend
        if settings.RATE_LIMIT_STORAGE_BACKEND == "redis":
            try:
                # Use Redis for distributed rate limiting
                limiter.storage_uri = settings.REDIS_URL
                logger.info(
                    f"Rate limiting initialized with Redis: {settings.REDIS_URL}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to use Redis for rate limiting: {e}. Using in-memory storage."
                )
                limiter.storage_uri = None
        else:
            limiter.storage_uri = None
            logger.info("Rate limiting initialized with in-memory storage")

        # Add the slowapi middleware
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

        logger.info("Rate limiting middleware initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize rate limiting: {e}")
