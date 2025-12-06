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


from .providers import SearchResult, BaseDataProvider, FinalizableProvider, LegraProvider, VectorProvider, LightRAGProvider
from .providers.models import DataProviderInterface

from .service import AgentRAGService

# Singleton manager
from .manager import AgentRAGServiceManager


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
