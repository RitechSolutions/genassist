"""
In-memory cache of llm_cost_rates loaded via sync SQLAlchemy (per tenant).

Used by find_pricing from synchronous workflow code without an async session.
Invalidated when rates are updated via the API.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.llm_cost_rate import LlmCostRateModel

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_TTL_SECONDS = 60.0
_cache: dict[str, tuple[float, dict[str, dict[str, dict[str, float]]]]] = {}
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
    with _lock:
        if tenant is None:
            _cache.clear()
        else:
            _cache.pop(tenant, None)


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


def get_db_pricing_nested(tenant: str) -> dict[str, dict[str, dict[str, float]]]:
    """Cached {provider: {model: rates}} from llm_cost_rates, refreshed every _TTL_SECONDS."""
    with _lock:
        entry = _cache.get(tenant)
        if entry is not None and time.monotonic() < entry[0]:
            return entry[1]
    loaded = _load_db_nested(tenant)
    if loaded is None:
        return entry[1] if entry is not None else {}
    with _lock:
        _cache[tenant] = (time.monotonic() + _TTL_SECONDS, loaded)
    return loaded
