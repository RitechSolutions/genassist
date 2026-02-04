import logging
from inspect import signature
from typing import Any, Callable, cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from starlette.datastructures import State

logger = logging.getLogger(__name__)


async def init_fastapi_cache_with_redis(app, redis_binary: Redis):
    """
    Initialize FastAPI cache using DI-provided Redis binary client.

    Args:
        app: FastAPI application instance
        redis_binary: Redis client with decode_responses=False (from DI)
    """
    logger.info("Initializing FastAPI cache with binary Redis client")

    # tell the type checker what .state is
    app.state = cast(State, app.state)
    app.state.redis = redis_binary  # type: ignore[attr-defined]

    FastAPICache.init(RedisBackend(redis_binary), prefix="auth")

    # Clean cache on start
    # Note: In Redis Cluster mode, Lua scripts without keys are not supported.
    # FastAPICache.clear() may use a Lua script without keys, so we catch this error.
    try:
        await FastAPICache.clear()
    except ResponseError as e:
        if "Lua scripts without any input keys are not supported" in str(e):
            logger.warning(
                "Cannot clear cache on startup: Redis Cluster mode detected. "
                "Lua scripts without keys are not supported in cluster mode. "
                "This is safe to ignore - cache will be populated as needed."
            )
        else:
            # Re-raise other ResponseError exceptions
            raise
    except Exception as e:
        logger.warning(f"Failed to clear cache on startup: {e}. This is safe to ignore.")

    logger.info("FastAPI cache initialized")

def make_key_builder(param: str | int = 1) -> Callable[[Any, str, Any], str]:
    """
    Build a tenant-aware `fastapi-cache` key_builder that plucks *one* argument from the
    wrapped function call and includes tenant context.

    Parameters
    ----------
    param
        • If `int`  -> positional index to grab (default = 1 = first arg *after* `self`)
        • If `str` -> keyword name to grab (falls back to that keyword even
                      when the arg is passed positionally)

    Returns
    -------
    Callable usable as `key_builder=` in `@cache(...)`

    Note
    ----
    Cache keys include tenant context to ensure data isolation between tenants.
    Format: {namespace}:{tenant_id}:{value}
    """
    from app.core.tenant_scope import get_tenant_context

    def _builder(func, namespace, *args, **kwargs):
        # 1) Because fastapi-cache sometimes passes (args, kwargs) inside kwargs
        #    we normalise them first.
        pos_args = kwargs.get("args", args)
        kw_args = kwargs.get("kwargs", kwargs)

        # 2) Extract the chosen argument
        if isinstance(param, int):
            if len(pos_args) <= param:
                raise IndexError(
                    f"Key builder expected at least {param+1} positional args "
                    f"for {func.__qualname__}"
                )
            value = pos_args[param]
        else:  # param is str
            # kw > positional, to allow calling func(username="alice")
            value = kw_args.get(param)
            if value is None and len(pos_args) > 0:
                # find positional index of that param in the signature
                try:
                    pos = list(signature(func).parameters).index(param)
                    value = pos_args[pos]
                except ValueError:
                    pass

        # 3) Include tenant context in cache key for data isolation
        tenant_id = get_tenant_context()
        return f"{namespace}:{tenant_id}:{value}"

    return _builder


async def invalidate_cache(namespace: str, value: Any) -> bool:
    """
    Invalidate a specific cache entry for the current tenant.

    Parameters
    ----------
    namespace : str
        The cache namespace (e.g., "agents:get_by_id_full", "users:get_by_id_for_auth")
    value : Any
        The parameter value used in the cache key (e.g., agent_id, user_id)

    Returns
    -------
    bool
        True if the key was deleted, False if it didn't exist

    Example
    -------
    await invalidate_cache("agents:get_by_id_full", agent_id)
    await invalidate_cache("users:get_by_id_for_auth", user_id)

    Note
    ----
    The cache key format matches the one used by make_key_builder:
    {prefix}:{namespace}:{tenant_id}:{value}
    """
    from app.core.tenant_scope import get_tenant_context

    # Get the current tenant context
    tenant_id = get_tenant_context()

    # Construct the full cache key (must match the format used by FastAPICache)
    # Format: {prefix}:{namespace}:{tenant_id}:{value}
    # The prefix "auth" is set in init_fastapi_cache_with_redis
    cache_key = f"auth:{namespace}:{tenant_id}:{value}"

    try:
        # Get the Redis backend from FastAPICache
        backend = FastAPICache.get_backend()
        if backend:
            # Delete the key from Redis
            result = await backend.clear(namespace=None, key=cache_key)
            logger.debug(f"Invalidated cache key: {cache_key}, result: {result}")
            return True
        else:
            logger.warning("FastAPICache backend not initialized")
            return False
    except ResponseError as e:
        if "Lua scripts without any input keys are not supported" in str(e):
            logger.warning(
                "Cache invalidation skipped (Redis Cluster): %s. Key: %s",
                str(e),
                cache_key,
            )
            return False
        raise
    except Exception as e:
        logger.error(f"Failed to invalidate cache key {cache_key}: {e}")
        return False


async def invalidate_agent_cache(agent_id: UUID, user_id: UUID):
    await invalidate_cache("agents:get_by_id_full", agent_id)
    await invalidate_cache("agents:get_by_user_id", user_id)
