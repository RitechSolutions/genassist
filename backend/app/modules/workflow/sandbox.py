"""
Sandboxed execution environment for user-supplied Python code in workflow nodes.

Provides restricted builtins, a safe importer limited to an allowlist,
AST validation to block attribute-chain escapes, and an SSRF-safe
requests wrapper that blocks internal/metadata endpoints.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import ipaddress
import logging
import socket
from typing import Any, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module allowlists
# ---------------------------------------------------------------------------

# Modules that user code may import via `import X`
ALLOWED_MODULES: frozenset[str] = frozenset({
    "json", "math", "re", "datetime", "collections", "itertools",
    "functools", "string", "decimal", "fractions", "statistics",
    "copy", "typing", "traceback", "textwrap", "enum", "uuid",
    "hashlib", "hmac", "base64", "csv", "io",
})

# Top-level packages whose submodules are also allowed (numpy.linalg, etc.)
ALLOWED_PACKAGES: frozenset[str] = frozenset({
    "numpy", "pandas", "requests",
})

# Union used by the safe importer
_ALL_ALLOWED_TOP_LEVEL = ALLOWED_MODULES | ALLOWED_PACKAGES

# ---------------------------------------------------------------------------
# Dangerous dunder / attribute names blocked by the AST validator
# ---------------------------------------------------------------------------

_DUNDER_DENYLIST: frozenset[str] = frozenset({
    "__subclasses__", "__bases__", "__mro__", "__class__",
    "__globals__", "__builtins__", "__code__", "__func__",
    "__self__", "__init_subclass__", "__set_name__",
    "__reduce__", "__reduce_ex__",
})

_ATTR_DENYLIST: frozenset[str] = frozenset({
    "environ", "system", "popen", "exec", "eval", "compile",
    "subprocess", "execvp", "execvpe", "spawnl",
})

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class SandboxViolation(Exception):
    """Raised when user code attempts a disallowed operation."""


# ---------------------------------------------------------------------------
# AST validation
# ---------------------------------------------------------------------------


def validate_code_ast(code: str) -> None:
    """Parse *code* and reject dangerous attribute access patterns.

    Raises ``SandboxViolation`` if a violation is found, or ``SyntaxError``
    if the code cannot be parsed.
    """
    tree = ast.parse(code)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            name = node.attr
            if name in _DUNDER_DENYLIST:
                raise SandboxViolation(
                    f"Access to '{name}' is not allowed in sandboxed execution"
                )
            if name in _ATTR_DENYLIST:
                raise SandboxViolation(
                    f"Access to '{name}' is not allowed in sandboxed execution"
                )


# ---------------------------------------------------------------------------
# Safe __import__ replacement
# ---------------------------------------------------------------------------

_real_import = builtins.__import__


def _safe_import(
    name: str,
    globals: dict | None = None,
    locals: dict | None = None,
    fromlist: tuple = (),
    level: int = 0,
) -> Any:
    """Drop-in ``__import__`` that only allows modules in the allowlist."""
    top_level = name.split(".")[0]

    if top_level in _ALL_ALLOWED_TOP_LEVEL:
        return _real_import(name, globals, locals, fromlist, level)

    raise ImportError(
        f"Import of '{name}' is not allowed in sandboxed execution. "
        f"Allowed modules: {', '.join(sorted(_ALL_ALLOWED_TOP_LEVEL))}"
    )


# ---------------------------------------------------------------------------
# Restricted builtins
# ---------------------------------------------------------------------------

_DANGEROUS_BUILTINS: frozenset[str] = frozenset({
    "open", "exec", "eval", "compile", "__import__",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr",
    "breakpoint", "exit", "quit", "input",
    "memoryview", "help",
})


def _make_safe_builtins() -> dict:
    """Return a copy of ``__builtins__`` with dangerous names removed and
    ``__import__`` replaced by the sandboxed version."""
    src = builtins.__dict__ if isinstance(builtins, type(importlib)) else builtins.__dict__
    safe = {k: v for k, v in src.items() if k not in _DANGEROUS_BUILTINS}
    safe["__import__"] = _safe_import
    return safe


# Cache a single copy — it is not mutated by exec.
_SAFE_BUILTINS: dict = _make_safe_builtins()

# ---------------------------------------------------------------------------
# SSRF-safe requests wrapper
# ---------------------------------------------------------------------------

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local + AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fd00::/8"),
]


def _is_blocked_url(url: str) -> bool:
    """Return True if *url* resolves to an internal/metadata IP."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True

        # Resolve hostname to IP(s)
        for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(sockaddr[0])
            for network in _BLOCKED_NETWORKS:
                if ip in network:
                    return True
    except Exception:
        # If we can't resolve it, block it to be safe
        return True
    return False


class _SandboxedRequests:
    """Thin proxy around the ``requests`` library that blocks internal URLs."""

    def __init__(self) -> None:
        self._requests = importlib.import_module("requests")

    def _checked(self, method: str, url: str, **kwargs: Any) -> Any:
        if _is_blocked_url(url):
            raise SandboxViolation(
                f"HTTP request to '{urlparse(url).hostname}' is blocked — "
                "requests to internal/private networks are not allowed"
            )
        return getattr(self._requests, method)(url, **kwargs)

    def get(self, url: str, **kw: Any) -> Any:
        return self._checked("get", url, **kw)

    def post(self, url: str, **kw: Any) -> Any:
        return self._checked("post", url, **kw)

    def put(self, url: str, **kw: Any) -> Any:
        return self._checked("put", url, **kw)

    def patch(self, url: str, **kw: Any) -> Any:
        return self._checked("patch", url, **kw)

    def delete(self, url: str, **kw: Any) -> Any:
        return self._checked("delete", url, **kw)

    def head(self, url: str, **kw: Any) -> Any:
        return self._checked("head", url, **kw)

    def request(self, method: str, url: str, **kw: Any) -> Any:
        return self._checked("request", url, method=method, **kw)


# Singleton — reuse across executions.
_sandboxed_requests = _SandboxedRequests()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PRESEEDED_MODULES: dict[str, str] = {
    "json": "json",
    "requests": "__sandboxed__",  # special-cased below
    "datetime": "datetime",
    "math": "math",
    "re": "re",
    "pandas": "pandas",
    "numpy": "numpy",
    "traceback": "traceback",
}


def make_sandboxed_namespace(params: Dict[str, Any], logger_instance: Any) -> dict:
    """Build an exec namespace with restricted builtins and pre-seeded modules.

    The returned dict is suitable for passing directly to ``exec(code, namespace)``.
    """
    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "params": params,
        "result": None,
        "logger": logger_instance,
    }

    for alias, mod_name in _PRESEEDED_MODULES.items():
        if alias == "requests":
            namespace[alias] = _sandboxed_requests
        else:
            try:
                namespace[alias] = importlib.import_module(mod_name)
            except ImportError:
                # Optional dependency (pandas, numpy) may not be installed
                pass

    return namespace
