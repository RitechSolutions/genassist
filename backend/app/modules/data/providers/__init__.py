"""
Data Providers Module

This module contains all the provider implementations for different data sources.
Each provider implements the BaseDataProvider interface.
"""

import importlib as _importlib
from typing import TYPE_CHECKING

from .models import SearchResult
from .base import BaseDataProvider, FinalizableProvider
from .plain import PlainProvider
# Config types are lightweight — the vector/legra/lightrag packages expose them eagerly
# while lazy-loading their heavy provider implementations.
from .vector import VectorConfig
from .legra import LegraConfig
from .lightrag import LightRAGConfig

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .vector import VectorProvider
    from .legra import LegraProvider
    from .lightrag import LightRAGProvider

# Provider implementations are loaded lazily (PEP 562): VectorProvider pulls the
# chunking/embedding/db backends (torch/sentence_transformers/faiss), LegraProvider
# pulls faiss/torch/sentence_transformers, and LightRAGProvider pulls the lightrag
# library. These spawn native threads at import and must NOT be loaded into a Celery
# prefork master process (fork() of locked mutexes -> SIGSEGV). Importing this package
# stays ML-free; the heavy import happens only on actual provider use — at runtime, in
# a prefork child (post-fork).
_LAZY_PROVIDERS = {
    "VectorProvider": ".vector",
    "LegraProvider": ".legra",
    "LightRAGProvider": ".lightrag",
}


def __getattr__(name):
    if name in _LAZY_PROVIDERS:
        return getattr(_importlib.import_module(_LAZY_PROVIDERS[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseDataProvider",
    "FinalizableProvider",
    "SearchResult",
    "LegraProvider",
    "VectorProvider",
    "LightRAGProvider",
    "LegraConfig",
    "VectorConfig",
    "LightRAGConfig",
    "PlainProvider",
]
