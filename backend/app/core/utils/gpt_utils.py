import functools
import logging

logger = logging.getLogger(__name__)

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
