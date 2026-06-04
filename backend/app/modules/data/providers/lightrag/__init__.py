"""
LightRAG Module

This module provides LightRAG-based graph search capabilities.
"""

import importlib
from typing import TYPE_CHECKING

from .config import LightRAGConfig

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .provider import LightRAGProvider

# LightRAGProvider imports the heavy ``lightrag`` library at module load. Resolve it
# lazily (PEP 562) so importing this package stays free of that dependency — important
# for the Celery prefork master process. The provider materializes on first use, at
# runtime in a prefork child (post-fork).


def __getattr__(name):
    if name == "LightRAGProvider":
        return getattr(importlib.import_module(".provider", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LightRAGConfig",
    "LightRAGProvider"
]
