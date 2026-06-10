"""
Data Module - Unified interface for vector and LEGRA providers and LightRAG

This module provides a clean, unified interface for working with different
data providers (vector databases and LEGRA) as a replacement for the old AgentDataSourceService
works in the workflow module, but specifically focused on the data module's
vector and legra implementations and LightRAG.
"""

from .config import (
    AgentRAGConfig,
    KbRAGConfig,
)


from .providers import SearchResult, BaseDataProvider, FinalizableProvider
from .providers.models import DataProviderInterface

from .service import AgentRAGService

# Singleton manager
from .manager import AgentRAGServiceManager

# VectorProvider / LegraProvider / LightRAGProvider pull torch/sentence_transformers/
# faiss and the lightrag library at import. Re-export them lazily (PEP 562) so importing
# this package — which the DI container and Celery task modules do at boot — stays
# ML-free; they materialize on first use (runtime, in a prefork child).
import importlib as _importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .providers import VectorProvider, LegraProvider, LightRAGProvider


def __getattr__(name):
    if name in ("VectorProvider", "LegraProvider", "LightRAGProvider"):
        return getattr(_importlib.import_module(".providers", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Main service classes
    "AgentRAGService",
    # Tenant-aware singleton manager
    "AgentRAGServiceManager",

    # Provider interfaces
    "BaseDataProvider",
    "FinalizableProvider",

    # Provider classes
    "VectorProvider",
    "LegraProvider",
    "LightRAGProvider",

    # Configuration classes
    "AgentRAGConfig",
    "KbRAGConfig",

    # Data classes
    "SearchResult",
    "DataProviderInterface",
]
