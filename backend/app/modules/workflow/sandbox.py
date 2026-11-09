"""
Sandboxed execution environment for user-supplied Python code in workflow nodes.

Provides restricted builtins, a safe importer limited to an allowlist,
AST validation to block attribute-chain escapes, and a connection guard
that keeps user code off internal/metadata addresses.
"""

from __future__ import annotations

import _socket
import ast
import builtins
import functools
import importlib
import ipaddress
import logging
import socket
import sys
from typing import Any, Dict, Optional, Union

from app.core.utils.string_utils import truncate_for_log

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module allowlists
# ---------------------------------------------------------------------------

# Modules that user code may import via `import X`
ALLOWED_MODULES: frozenset[str] = frozenset({
    "json", "math", "random", "re", "datetime", "collections", "itertools",
    "functools", "string", "decimal", "fractions", "statistics",
    "copy", "typing", "traceback", "textwrap", "enum", "uuid",
    "hashlib", "hmac", "base64", "csv", "io",
})

# Top-level packages whose submodules are also allowed (numpy.linalg,
# sklearn.preprocessing, scipy.stats, etc.). sklearn and scipy are already
# dependencies used elsewhere in this codebase (e.g. the Train Model node),
# so they're already loaded in the parent process this sandbox forks from -
# no new install or deployment change needed to allow them here too.
ALLOWED_PACKAGES: frozenset[str] = frozenset({
    "numpy", "pandas", "requests", "sklearn", "scipy",
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
    "environ", "system", "popen", "exec", "eval",
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
# Connection guard
# ---------------------------------------------------------------------------

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]

_IPV4_MAPPED = ipaddress.ip_network("::ffff:0:0/96")
_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")
_GLOBAL_UNICAST = ipaddress.ip_network("2000::/3")
_UNIQUE_LOCAL = ipaddress.ip_network("fc00::/7")
# Cloud metadata and host endpoints, blocked even when allowlisted (IMDS, Alibaba, Oracle, Azure WireServer)
_CLOUD_ENDPOINTS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "169.254.0.0/16", "fd00:ec2::/32", "fd20:ce::254/128", "100.100.100.200/32", "192.0.0.192/32",
        "168.63.129.16/32",
    )
)
_ADDRESSED_SOCKET_EVENTS = frozenset({"socket.connect", "socket.sendto", "socket.sendmsg"})
_SOCKET_FAMILY = _socket.socket.family


def _as_ipv4(ip: IPAddress) -> IPAddress:
    """The IPv4 address inside an IPv4-mapped, NAT64 or 6to4 address; any other address unchanged."""
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
        if ip in _NAT64_PREFIX:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if ip.sixtofour is not None:
            return ip.sixtofour
    return ip


def _as_ipv4_network(network: IPNetwork) -> IPNetwork:
    """The IPv4 range inside an IPv4-mapped or NAT64 range; any other range unchanged."""
    if network.version == 6 and network.prefixlen >= 96:
        for prefix in (_IPV4_MAPPED, _NAT64_PREFIX):
            if network.subnet_of(prefix):
                return ipaddress.ip_network((int(network.network_address) & 0xFFFFFFFF, network.prefixlen - 96))
    return network


def _is_public_address(ip: IPAddress) -> bool:
    """Whether *ip*, already passed through _as_ipv4, routes to the public internet."""
    if ip.version == 6 and ip not in _GLOBAL_UNICAST:
        return False
    return ip.is_global and not ip.is_multicast


def connection_allowed(host: Any, allowed_networks: tuple[IPNetwork, ...] = ()) -> bool:
    """Whether sandboxed code may connect to *host*, the host part of a connect() address."""
    if type(host) is not str:  # a subclass can show different text than the C code connects to
        return False
    try:
        ip = _as_ipv4(ipaddress.ip_address(host))
    except ValueError:
        # The audit event carries the address unresolved, so only IP literals can be checked
        return False
    if any(ip in network for network in _CLOUD_ENDPOINTS):
        return False
    return _is_public_address(ip) or any(ip in network for network in allowed_networks)


@functools.lru_cache(maxsize=8)
def parse_allowed_networks(raw: Optional[str]) -> tuple[IPNetwork, ...]:
    """IPs and CIDR ranges from the comma-separated SANDBOX_ALLOWED_NETWORKS setting."""
    networks = []
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            network = _as_ipv4_network(ipaddress.ip_network(entry))
            # Other IPv6 ranges can carry IPv4 hosts (NAT64, 6to4, translated forms) past the IPv4 checks
            if network.version == 6 and not network.subnet_of(_UNIQUE_LOCAL):
                raise ValueError("IPv6 entries must be inside fc00::/7; list IPv4 hosts in IPv4 form")
            networks.append(network)
        except ValueError as exc:
            logger.error("Ignoring SANDBOX_ALLOWED_NETWORKS entry %r: %s", entry, exc)
    return tuple(networks)


def refuse_internal_address(event: str, args: tuple, allowed_networks: tuple[IPNetwork, ...] = ()) -> None:
    """Audit hook body: raise when a socket call targets anything but an allowed IP address."""
    if event not in _ADDRESSED_SOCKET_EVENTS:
        return
    sock, address = args
    if address is None:  # sendmsg on an already connected socket
        return
    # The C field and an exact tuple, since subclasses can override family and indexing
    family = _SOCKET_FAMILY.__get__(sock)
    is_ip_address = family in (socket.AF_INET, socket.AF_INET6) and type(address) is tuple
    host = address[0] if is_ip_address else address
    if not (is_ip_address and connection_allowed(host, allowed_networks)):
        raise SandboxViolation(
            f"connection to {host} is blocked. Sandboxed code can only connect to public IP addresses "
            "and those an administrator allows"
        )


def block_internal_connections(allowed_networks: tuple[IPNetwork, ...] = ()) -> None:
    """Refuse every later connection from this process to a non-public address.

    Audit hooks fire inside Python's socket module and can't be removed, so libraries and redirects using it are
    checked too. Native code that opens its own sockets (pyarrow's S3 client, libpq) never reaches the hook.
    """

    def guard(event: str, args: tuple) -> None:
        if event in _ADDRESSED_SOCKET_EVENTS:
            refuse_internal_address(event, args, allowed_networks)

    sys.addaudithook(guard)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PRESEEDED_MODULES: dict[str, str] = {
    "json": "json",
    "requests": "requests",
    "datetime": "datetime",
    "math": "math",
    "re": "re",
    "pandas": "pandas",
    "numpy": "numpy",
    "traceback": "traceback",
}


class _TruncatingLogger:
    """Wrapper around a real logger that truncates messages from user code."""

    def __init__(self, real_logger: Any) -> None:
        self._logger = real_logger

    def _truncate(self, args: tuple) -> tuple:
        return tuple(truncate_for_log(str(a)) for a in args)

    def debug(self, msg: str, *args: Any) -> None:
        self._logger.debug(msg, *self._truncate(args))

    def info(self, msg: str, *args: Any) -> None:
        self._logger.info(msg, *self._truncate(args))

    def warning(self, msg: str, *args: Any) -> None:
        self._logger.warning(msg, *self._truncate(args))

    def error(self, msg: str, *args: Any) -> None:
        self._logger.error(msg, *self._truncate(args))


def make_sandboxed_namespace(params: Dict[str, Any], logger_instance: Any) -> dict:
    """Build an exec namespace with restricted builtins and pre-seeded modules.

    The returned dict is suitable for passing directly to ``exec(code, namespace)``.
    """
    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "params": params,
        "result": None,
        "logger": _TruncatingLogger(logger_instance),
    }

    for alias, mod_name in _PRESEEDED_MODULES.items():
        try:
            namespace[alias] = importlib.import_module(mod_name)
        except ImportError:
            # Optional dependency (pandas, numpy) may not be installed
            pass

    return namespace
