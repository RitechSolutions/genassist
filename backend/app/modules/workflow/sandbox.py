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
from typing import Any, Callable, Dict, Optional, Union

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

IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]

_IPV4_MAPPED = ipaddress.ip_network("::ffff:0:0/96")
_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")
_UNIQUE_LOCAL = ipaddress.ip_network("fc00::/7")
# IPv6 ranges that carry an IPv4 address, with its bit offset: IPv4-mapped, NAT64, 6to4
_EMBEDDED_IPV4 = ((_IPV4_MAPPED, 0), (_NAT64_PREFIX, 0), (ipaddress.ip_network("2002::/16"), 80))
# Not globally reachable per the IANA special-purpose registries, multicast, reserved, and IPv6 outside 2000::/3
_NON_PUBLIC = tuple(
    ipaddress.ip_network(network)
    for network in (
        "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12",
        "192.0.0.0/24", "192.0.2.0/24", "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24",
        "224.0.0.0/3", "::/3", "4000::/2", "8000::/1", "2001::/23", "2001:db8::/32", "3fff::/20",
    )
)
# Globally reachable blocks inside those ranges
_PUBLIC_EXCEPTIONS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "192.0.0.9/32", "192.0.0.10/32", "2001:1::1/128", "2001:1::2/128", "2001:3::/32", "2001:4:112::/48",
        "2001:20::/28", "2001:30::/28",
    )
)
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


def _as_ipv4_network(network: IPNetwork) -> IPNetwork:
    """The IPv4 range inside an IPv4-mapped or NAT64 range; any other range unchanged."""
    if network.version == 6 and network.prefixlen >= 96:
        for prefix in (_IPV4_MAPPED, _NAT64_PREFIX):
            if network.subnet_of(prefix):
                return ipaddress.ip_network((int(network.network_address) & 0xFFFFFFFF, network.prefixlen - 96))
    return network


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


def _ranges(networks: tuple[IPNetwork, ...]) -> dict[int, tuple[tuple[int, int], ...]]:
    """First and last address of each network as ints, keyed by socket family."""
    ranges: dict[int, list[tuple[int, int]]] = {int(socket.AF_INET): [], int(socket.AF_INET6): []}
    for network in networks:
        family = socket.AF_INET if network.version == 4 else socket.AF_INET6
        ranges[int(family)].append((int(network.network_address), int(network.broadcast_address)))
    return {family: tuple(found) for family, found in ranges.items()}


def connection_guard(allowed_networks: tuple[IPNetwork, ...] = ()) -> Callable[[str, tuple], None]:
    """Audit hook allowing only TCP, UDP and Unix sockets, connecting to public addresses or *allowed_networks*.

    User code runs in this process, so the hook keeps its own references to every function and value it uses.
    """
    inet_pton, from_bytes, family_of = _socket.inet_pton, int.from_bytes, _SOCKET_FAMILY.__get__
    type_of, exact_str, exact_tuple = type, str, tuple
    violation, not_a_literal = SandboxViolation, (OSError, ValueError)
    inet, inet6 = int(socket.AF_INET), int(socket.AF_INET6)
    ip_families = frozenset({inet, inet6})
    # Unix sockets stay allowed for socketpair; connecting them is refused below
    socket_families = frozenset({inet, inet6, int(socket.AF_UNIX)})
    socket_types = frozenset({int(socket.SOCK_STREAM), int(socket.SOCK_DGRAM)})
    protocols = frozenset({0, int(socket.IPPROTO_TCP), int(socket.IPPROTO_UDP)})
    type_flags = int(getattr(socket, "SOCK_NONBLOCK", 0)) | int(getattr(socket, "SOCK_CLOEXEC", 0))
    addressed_events = _ADDRESSED_SOCKET_EVENTS
    embedded = tuple((int(n.network_address), int(n.broadcast_address), shift) for n, shift in _EMBEDDED_IPV4)
    cloud, non_public, exceptions, allowed = (
        _ranges(networks) for networks in (_CLOUD_ENDPOINTS, _NON_PUBLIC, _PUBLIC_EXCEPTIONS, allowed_networks)
    )

    def inside(number: int, ranges: tuple[tuple[int, int], ...]) -> bool:
        for first, last in ranges:
            if first <= number <= last:
                return True
        return False

    def address_allowed(family: int, host: str) -> bool:
        try:
            number = from_bytes(inet_pton(family, host), "big")
        except not_a_literal:
            return False  # the event carries the address as written, so only IP literals can be checked
        if family == inet6:
            for first, last, shift in embedded:
                if first <= number <= last:
                    family, number = inet, (number >> shift) & 0xFFFFFFFF
                    break
        if inside(number, cloud[family]):
            return False
        public = not inside(number, non_public[family]) or inside(number, exceptions[family])
        return public or inside(number, allowed[family])

    def guard(event: str, args: tuple) -> None:
        if event == "socket.__new__":
            _, family, kind, protocol = args
            if family not in socket_families or (kind & ~type_flags) not in socket_types or protocol not in protocols:
                raise violation(
                    "opening this kind of socket is blocked. Sandboxed code can only open TCP, UDP and Unix sockets"
                )
            return
        if event not in addressed_events:
            return
        sock, address = args
        if address is None:  # sendmsg on an already connected socket
            return
        # The C field and exact types, since subclasses can override family, indexing and text
        family = family_of(sock)
        host = address[0] if type_of(address) is exact_tuple and address else address
        if type_of(host) is exact_str and family in ip_families and address_allowed(family, host):
            return
        shown = host if type_of(host) is exact_str else "this address"
        raise violation(
            f"connection to {shown} is blocked. Sandboxed code can only connect to public IP addresses "
            "and those an administrator allows"
        )

    return guard


def block_internal_connections(allowed_networks: tuple[IPNetwork, ...] = ()) -> None:
    """Refuse later sockets other than TCP, UDP and Unix, and connections to non-public addresses, in this process.

    Audit hooks fire inside Python's socket module and can't be removed, so libraries and redirects using it are
    checked too. Native code that opens its own sockets (pyarrow's S3 client, libpq) never reaches the hook.
    """
    sys.addaudithook(connection_guard(allowed_networks))


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
