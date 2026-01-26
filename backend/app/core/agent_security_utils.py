"""
Utilities for agent-specific security settings (CORS and rate limiting)
"""
import logging
from typing import Tuple
from starlette.requests import Request
from starlette.responses import Response
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


def get_agent_cors_origins(agent_security_settings) -> list[str]:
    """
    Get allowed CORS origins for an agent.
    Returns agent-specific origins if configured, otherwise global defaults.
    """
    default_origins = [
        "http://localhost:8080",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
    ]

    # Start with default origins
    allowed_origins = default_origins.copy()

    # Add global CORS origins from settings if provided
    if settings.CORS_ALLOWED_ORIGINS:
        additional_origins = [
            origin.strip()
            for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]
        for origin in additional_origins:
            if origin not in allowed_origins:
                allowed_origins.append(origin)

    # Add agent-specific origins if configured
    if agent_security_settings and agent_security_settings.cors_allowed_origins:
        agent_origins = [
            origin.strip()
            for origin in agent_security_settings.cors_allowed_origins.split(",")
            if origin.strip()
        ]
        for origin in agent_origins:
            if origin not in allowed_origins:
                allowed_origins.append(origin)

    return allowed_origins


def apply_agent_cors_headers(
    request: Request,
    response: Response,
    agent_security_settings
) -> Response:
    """
    Apply agent-specific CORS headers to the response.
    """
    allowed_origins = get_agent_cors_origins(agent_security_settings)

    # Get the origin from the request
    origin = request.headers.get("origin")

    # If origin is in allowed list, set CORS headers
    if origin and origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    elif "*" in allowed_origins:
        # Allow all origins if explicitly configured
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"

    return response


def get_agent_rate_limit_start(
    agent_security_settings
) -> Tuple[str, str]:
    """
    Get rate limit strings for conversation start endpoint.
    Returns (per_minute, per_hour) rate limit strings.
    Falls back to global defaults if agent-specific limits are not set.
    """
    per_minute = (
        agent_security_settings.rate_limit_conversation_start_per_minute
        if agent_security_settings and agent_security_settings.rate_limit_conversation_start_per_minute
        else settings.RATE_LIMIT_CONVERSATION_START_PER_MINUTE
    )

    per_hour = (
        agent_security_settings.rate_limit_conversation_start_per_hour
        if agent_security_settings and agent_security_settings.rate_limit_conversation_start_per_hour
        else settings.RATE_LIMIT_CONVERSATION_START_PER_HOUR
    )

    return f"{per_minute}/minute", f"{per_hour}/hour"


def get_agent_rate_limit_update(
    agent_security_settings
) -> Tuple[str, str]:
    """
    Get rate limit strings for conversation update endpoint.
    Returns (per_minute, per_hour) rate limit strings.
    Falls back to global defaults if agent-specific limits are not set.
    """
    per_minute = (
        agent_security_settings.rate_limit_conversation_update_per_minute
        if agent_security_settings and agent_security_settings.rate_limit_conversation_update_per_minute
        else settings.RATE_LIMIT_CONVERSATION_UPDATE_PER_MINUTE
    )

    per_hour = (
        agent_security_settings.rate_limit_conversation_update_per_hour
        if agent_security_settings and agent_security_settings.rate_limit_conversation_update_per_hour
        else settings.RATE_LIMIT_CONVERSATION_UPDATE_PER_HOUR
    )

    return f"{per_minute}/minute", f"{per_hour}/hour"
