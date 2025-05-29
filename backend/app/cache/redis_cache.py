from inspect import signature
from typing import Any, Callable, cast
from redis.asyncio import Redis
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from starlette.datastructures import State


async def init_fastapi_cache_with_redis(app, settings):
    # ── Redis pool & cache initialisation ─────────────────
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)

    # tell the type checker what .state is
    app.state = cast(State, app.state)
    app.state.redis = redis  # type: ignore[attr-defined]

    FastAPICache.init(RedisBackend(redis), prefix="auth")
    await FastAPICache.clear() #clean cache on start

def make_key_builder(param: str | int = 1) -> Callable[[Any, str, Any], str]:
    """
    Build a `fastapi-cache` key_builder that plucks *one* argument from the
    wrapped function call.

    Parameters
    ----------
    param
        • If `int`  -> positional index to grab (default = 1 = first arg *after* `self`)
        • If `str` -> keyword name to grab (falls back to that keyword even
                      when the arg is passed positionally)

    Returns
    -------
    Callable usable as `key_builder=` in `@cache(...)`
    """

    def _builder(func, namespace, *args, **kwargs):
        # 1) Because fastapi-cache sometimes passes (args, kwargs) inside kwargs
        #    we normalise them first.
        pos_args = kwargs.get("args", args)
        kw_args  = kwargs.get("kwargs", kwargs)

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
        return f"{namespace}:{value}"

    return _builder