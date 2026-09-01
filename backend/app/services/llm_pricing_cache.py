"""
In-memory cache of llm_cost_rates loaded via sync SQLAlchemy (per tenant).

Read by resolve_live_pricing from synchronous workflow code without an async session.
Invalidated when rates are updated via the API.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config.settings import settings
from app.db.models.llm_cost_rate import LlmCostRateModel

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_condition = threading.Condition(_lock)
_TTL_SECONDS = 60.0
_FAILURE_COOLDOWN_SECONDS = 5.0
_cache: dict[str, tuple[float, dict[str, dict[str, dict[str, float]]]]] = {}
_next_retry: dict[str, float] = {}
_refreshing: set[str] = set()
_global_generation = 0
_tenant_generation: dict[str, int] = {}
_sync_session_factories: dict[str, sessionmaker[Any]] = {}


def _session_factory_for_tenant(tenant: str) -> sessionmaker[Any]:
    with _lock:
        if tenant not in _sync_session_factories:
            url = settings.get_tenant_database_url_sync(tenant)
            engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=2,
            )
            _sync_session_factories[tenant] = sessionmaker(bind=engine)
        return _sync_session_factories[tenant]


def invalidate_llm_cost_rates_cache(tenant: str | None = None) -> None:
    global _global_generation
    with _lock:
        if tenant is None:
            _global_generation += 1
            _cache.clear()
            _next_retry.clear()
        else:
            _tenant_generation[tenant] = _tenant_generation.get(tenant, 0) + 1
            _cache.pop(tenant, None)
            _next_retry.pop(tenant, None)


_PENDING_INVALIDATIONS = "llm_cost_rate_invalidations"


def invalidate_llm_cost_rates_cache_after_commit(session: Any, tenant: str | None = None) -> None:
    """Queue ``tenant``'s invalidation until ``session`` commits"""
    info = getattr(session, "sync_session", session).info
    info.setdefault(_PENDING_INVALIDATIONS, set()).add(tenant)


@event.listens_for(Session, "after_commit")
def _invalidate_committed_rate_changes(session: Session) -> None:
    if session.in_nested_transaction():
        return
    for tenant in session.info.pop(_PENDING_INVALIDATIONS, ()):
        invalidate_llm_cost_rates_cache(tenant)


@event.listens_for(Session, "after_rollback")
def _drop_rolled_back_rate_changes(session: Session) -> None:
    if session.in_nested_transaction():
        return
    session.info.pop(_PENDING_INVALIDATIONS, None)


def _load_db_nested(tenant: str) -> dict[str, dict[str, dict[str, float]]] | None:
    nested: dict[str, dict[str, dict[str, float]]] = {}
    try:
        factory = _session_factory_for_tenant(tenant)
        with factory() as session:
            rows = session.execute(
                select(
                    LlmCostRateModel.provider_key,
                    LlmCostRateModel.model_key,
                    LlmCostRateModel.input_per_1k,
                    LlmCostRateModel.output_per_1k,
                    LlmCostRateModel.cache_read_per_1k,
                    LlmCostRateModel.cache_creation_per_1k,
                ).where(LlmCostRateModel.is_deleted == 0)
            ).all()
            for r in rows:
                pk = (r.provider_key or "").lower()
                mk = (r.model_key or "").lower().strip()
                if not pk or not mk:
                    continue
                rates = {
                    "input_per_1k": float(r.input_per_1k),
                    "output_per_1k": float(r.output_per_1k),
                }
                # Left out when unconfigured, so pricing falls back to its provider default
                if r.cache_read_per_1k is not None:
                    rates["cache_read_per_1k"] = float(r.cache_read_per_1k)
                if r.cache_creation_per_1k is not None:
                    rates["cache_creation_per_1k"] = float(r.cache_creation_per_1k)
                nested.setdefault(pk, {})[mk] = rates
    except Exception as e:
        logger.warning("Failed loading llm_cost_rates for tenant %s: %s", tenant, e)
        return None
    return nested


def _refresh(tenant: str, generation: tuple) -> tuple:
    loaded = None
    current = generation
    try:
        loaded = _load_db_nested(tenant)
    finally:
        with _condition:
            _refreshing.discard(tenant)
            current = (_global_generation, _tenant_generation.get(tenant, 0))
            if current == generation:
                if loaded is None:
                    _next_retry[tenant] = time.monotonic() + _FAILURE_COOLDOWN_SECONDS
                else:
                    _cache[tenant] = (time.monotonic() + _TTL_SECONDS, loaded)
                    _next_retry.pop(tenant, None)
            _condition.notify_all()
    return loaded, current


def _refresh_in_background(tenant: str, generation: tuple) -> None:
    try:
        _refresh(tenant, generation)
    except Exception:
        # Bookkeeping already ran in _refresh's finally; the next caller retries
        logger.warning("Background llm_cost_rates refresh failed for tenant %s", tenant, exc_info=True)


def get_db_pricing_nested(tenant: str) -> dict[str, dict[str, dict[str, float]]]:
    """Cached {provider: {model: rates}} from llm_cost_rates, refreshed every _TTL_SECONDS.
    One DB load at a time per tenant. An expired warm entry is served stale while a
    background thread refreshes. Only a cold miss blocks, rather than pricing with an empty table"""
    while True:
        with _condition:
            while True:
                now = time.monotonic()
                entry = _cache.get(tenant)
                if entry is not None and now < entry[0]:
                    return entry[1]
                stale = entry[1] if entry is not None else None
                if now < _next_retry.get(tenant, 0.0):
                    return stale if stale is not None else {}
                if tenant not in _refreshing:
                    break
                if stale is not None:
                    return stale
                _condition.wait()
            _refreshing.add(tenant)
            generation = (_global_generation, _tenant_generation.get(tenant, 0))

        if stale is not None:
            try:
                threading.Thread(
                    target=_refresh_in_background,
                    args=(tenant, generation),
                    name=f"llm-cost-rates-refresh-{tenant}",
                    daemon=True,
                ).start()
            except Exception:
                with _condition:
                    _refreshing.discard(tenant)
                    _condition.notify_all()
                logger.warning("Could not start the llm_cost_rates refresh thread for tenant %s", tenant, exc_info=True)
            return stale

        loaded, current = _refresh(tenant, generation)
        if current == generation:
            return loaded if loaded is not None else {}
