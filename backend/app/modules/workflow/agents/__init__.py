import importlib as _importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # static analyzers don't see PEP 562 __getattr__ — declare names here
    from .react_agent import ReActAgent
    from .tool_agent import ToolAgent
    from .cot_agent import ChainOfThoughtAgent

# The agent classes pull heavy ML deps (torch/transformers) transitively through their
# tooling/LLM stack. They are runtime constructs (instantiated during workflow
# execution). Resolve them lazily (PEP 562) so importing this package — which the DI
# container reaches via ThreadScopedRAG (.rag) at boot — stays ML-free; the agents
# materialize on first use, in a prefork child (post-fork).
_LAZY = {
    "ReActAgent": ".react_agent",
    "ToolAgent": ".tool_agent",
    "ChainOfThoughtAgent": ".cot_agent",
}


def __getattr__(name):
    if name in _LAZY:
        return getattr(_importlib.import_module(_LAZY[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ReActAgent", "ToolAgent", "ChainOfThoughtAgent"]
