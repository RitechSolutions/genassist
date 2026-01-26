"""
Rate Limiting Middleware for FastAPI

This middleware provides rate limiting and throttling capabilities using slowapi.
It supports both Redis and in-memory storage backends.
"""

import logging
from contextvars import ContextVar
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request

from app.core.config.settings import settings
from app.core.rate_limit_utils import RATE_LIMIT_GLOBAL_HOUR, RATE_LIMIT_GLOBAL_MINUTE

logger = logging.getLogger(__name__)

# Context variable to store the current request for rate limit functions
_request_context: ContextVar[Request] = ContextVar('request_context', default=None)


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


def get_agent_rate_limit_start(request: Request = None) -> str:
    """
    Get agent-specific rate limit for conversation start.
    Falls back to global default if agent not found or no agent-specific limit.
    Can be called with or without request parameter (uses context if not provided).
    """
    from app.core.agent_security_utils import get_agent_rate_limit_start as get_rate_limits

    # Get request from parameter or context
    if request is None:
        request = _request_context.get()
    
    if request is None:
        return f"{settings.RATE_LIMIT_CONVERSATION_START_PER_MINUTE}/minute"

    agent = getattr(request.state, "agent", None)
    if agent and hasattr(agent, "security_settings") and agent.security_settings:
        per_minute, _ = get_rate_limits(agent.security_settings)
        return per_minute

    return f"{settings.RATE_LIMIT_CONVERSATION_START_PER_MINUTE}/minute"


def get_agent_rate_limit_start_hour(request: Request = None) -> str:
    """
    Get agent-specific rate limit per hour for conversation start.
    Falls back to global default if agent not found or no agent-specific limit.
    Can be called with or without request parameter (uses context if not provided).
    """
    from app.core.agent_security_utils import get_agent_rate_limit_start as get_rate_limits

    # Get request from parameter or context
    if request is None:
        request = _request_context.get()
    
    if request is None:
        return f"{settings.RATE_LIMIT_CONVERSATION_START_PER_HOUR}/hour"

    agent = getattr(request.state, "agent", None)
    if agent and hasattr(agent, "security_settings") and agent.security_settings:
        _, per_hour = get_rate_limits(agent.security_settings)
        return per_hour

    return f"{settings.RATE_LIMIT_CONVERSATION_START_PER_HOUR}/hour"


def get_agent_rate_limit_update(request: Request = None) -> str:
    """
    Get agent-specific rate limit for conversation update.
    Falls back to global default if agent not found or no agent-specific limit.
    Can be called with or without request parameter (uses context if not provided).
    """
    from app.core.agent_security_utils import get_agent_rate_limit_update as get_rate_limits

    # Get request from parameter or context
    if request is None:
        request = _request_context.get()
    
    if request is None:
        return f"{settings.RATE_LIMIT_CONVERSATION_UPDATE_PER_MINUTE}/minute"

    agent = getattr(request.state, "agent", None)
    if agent and hasattr(agent, "security_settings") and agent.security_settings:
        per_minute, _ = get_rate_limits(agent.security_settings)
        return per_minute

    return f"{settings.RATE_LIMIT_CONVERSATION_UPDATE_PER_MINUTE}/minute"


def get_agent_rate_limit_update_hour(request: Request = None) -> str:
    """
    Get agent-specific rate limit per hour for conversation update.
    Falls back to global default if agent not found or no agent-specific limit.
    Can be called with or without request parameter (uses context if not provided).
    """
    from app.core.agent_security_utils import get_agent_rate_limit_update as get_rate_limits

    # Get request from parameter or context
    if request is None:
        request = _request_context.get()
    
    if request is None:
        return f"{settings.RATE_LIMIT_CONVERSATION_UPDATE_PER_HOUR}/hour"

    agent = getattr(request.state, "agent", None)
    if agent and hasattr(agent, "security_settings") and agent.security_settings:
        _, per_hour = get_rate_limits(agent.security_settings)
        return per_hour

    return f"{settings.RATE_LIMIT_CONVERSATION_UPDATE_PER_HOUR}/hour"


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
