import functools
import logging
import re
from typing import Optional, Tuple
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey

logger = logging.getLogger(__name__)


# Non-retryable error patterns (provider-agnostic) to use for any model in langchain
# Maps error patterns to their corresponding ErrorKey values
NON_RETRYABLE_ERROR_PATTERNS = [
    (r"context_length_exceeded", "LLM_CONTEXT_LENGTH_EXCEEDED"),
    (r"maximum context length", "LLM_CONTEXT_LENGTH_EXCEEDED"),
    (r"rate_limit", "LLM_RATE_LIMIT_EXCEEDED"),
    (r"quota.*exceeded", "LLM_QUOTA_EXCEEDED"),
    (r"insufficient.*quota", "LLM_QUOTA_EXCEEDED"),
    (r"billing.*hard.*limit", "LLM_BILLING_LIMIT_REACHED"),
    (r"invalid.*api.*key", "LLM_INVALID_API_KEY"),
    (r"authentication.*failed", "LLM_AUTHENTICATION_FAILED"),
    (r"incorrect.*api.*key", "LLM_INVALID_API_KEY"),
]

def is_non_retryable_llm_error(error_message: str) -> Optional[Tuple[str, str]]:
    """
    Check if an error message matches known non-retryable LLM error patterns.

    Args:
        error_message: The error message to check (from any LLM provider)

    Returns:
        A tuple of (matched_pattern, error_key_name) if matched, None otherwise

    Example:
        >>> is_non_retryable_llm_error("Error: context_length_exceeded")
        ("context_length_exceeded", "LLM_CONTEXT_LENGTH_EXCEEDED")
    """
    error_message_lower = error_message.lower()

    for pattern, error_key_name in NON_RETRYABLE_ERROR_PATTERNS:
        if re.search(pattern, error_message_lower, re.IGNORECASE):
            return pattern, error_key_name

    return None


def check_and_raise_if_non_retryable(error: Exception) -> None:
    """
    Check if an exception is a non-retryable LLM error and raise AppException if so.

    This function examines the error message and raises an AppException with the
    appropriate ErrorKey if it matches known non-retryable patterns. Otherwise,
    it does nothing and the original exception can be retried.

    Args:
        error: The exception to check

    Raises:
        AppException: If the error matches a non-retryable pattern

    Example:
        try:
            response = await llm.ainvoke(messages)
        except Exception as e:
            check_and_raise_if_non_retryable(e)  # Raises AppException if non-retryable
            # Otherwise, continue with retry logic
            ...
    """

    error_str = str(error)
    result = is_non_retryable_llm_error(error_str)

    if result:
        _, error_key_name = result
        error_key = ErrorKey[error_key_name]  # Get ErrorKey enum from string name

        logger.error(f"Non-retryable LLM error detected: {error_key_name} - {error_str}")

        raise AppException(
            error_key=error_key,
            status_code=400,
            error_detail=error_str
        )


def retry_async(max_attempts=3, fallback=None, exception_message="Retry failed"):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs, _attempt=attempt, _last_error=last_error)
                except Exception as e:
                    last_error = e
                    logger.warning(f"{func.__name__} attempt {attempt} failed: {e}")
            logger.error(f"{func.__name__} failed after {max_attempts} attempts.")
            if fallback is not None:
                return fallback
            raise last_error or Exception(exception_message)
        return wrapper
    return decorator
