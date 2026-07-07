# flake8-in-file-ignores: noqa: F401, F403
"""LEGRA provider package.

The heavy submodules (chunking / clustering / embedding / generation / graph / index /
retrieval / core / provider) import faiss, torch, sentence_transformers and
transformers at module load. Those libraries spawn native OpenMP/MKL threads at
import, which makes them unsafe to have loaded in a Celery prefork *master* process:
fork() copies only the calling thread, leaving children with mutexes locked by threads
that no longer exist -> SIGSEGV.

To keep merely importing this package — and everything that transitively imports it
(the data-provider graph, the DI container, Celery task modules) — free of those
libraries, the heavy names are resolved lazily on first attribute access via PEP 562
``__getattr__``. Only the lightweight config is imported eagerly. The full public
surface (Legra, LegraProvider, and the chunking/embedding/... symbols) is unchanged;
it just materializes on first use (at runtime, in a prefork child — post-fork).
"""
import importlib
from typing import TYPE_CHECKING

from . import config as conf
from .config import LegraConfig

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .core import Legra
    from .provider import LegraProvider

# Heavy submodules whose public (``__all__``) symbols are re-exported from this
# package; imported on first access to any non-light attribute (see __getattr__).
_HEAVY_SUBMODULES = (
    "chunking", "clustering", "embedding", "generation", "graph", "index", "retrieval",
)
# Heavy top-level classes -> the submodule that defines them.
_EXTRA_LAZY = {"Legra": ".core", "LegraProvider": ".provider"}

_loaded = False


def _load_heavy():
    """Import the heavy submodules once and hoist their public symbols into globals."""
    global _loaded
    if _loaded:
        return
    g = globals()
    for sub in _HEAVY_SUBMODULES:
        mod = importlib.import_module(f".{sub}", __name__)
        for name in getattr(mod, "__all__", []):
            g.setdefault(name, getattr(mod, name))
    for name, modpath in _EXTRA_LAZY.items():
        mod = importlib.import_module(modpath, __name__)
        g.setdefault(name, getattr(mod, name))
    _loaded = True


def __getattr__(name):  # PEP 562 — lazy attribute resolution
    _load_heavy()
    try:
        return globals()[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'Legra',
    'conf',
    'LegraProvider',
    'LegraConfig',
]