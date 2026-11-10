import _socket
import builtins
import http.server
import ipaddress
import socket
import sys
import threading

import pytest

from app.modules.workflow import sandbox, utils
from app.modules.workflow.sandbox import SandboxViolation, connection_guard, parse_allowed_networks
from app.modules.workflow.utils import _execute_python_code_sync

BODY = "a,b\nsecret,42\n"
BLOCKED = "is blocked. Sandboxed code can only connect to public IP addresses and those an administrator allows"
SOCKET_BLOCKED = "opening this kind of socket is blocked. Sandboxed code can only open TCP, UDP and Unix sockets"
# requests and pandas read the system proxy settings, which crashes forked children on macOS
skip_on_macos = pytest.mark.skipif(
    sys.platform == "darwin", reason="system proxy lookup crashes forked children on macOS"
)
SESSION = "session = requests.Session()\nsession.trust_env = False\n"
# socket() arguments by constant name, for the kinds of socket this platform has
OTHER_SOCKETS = [
    names
    for names in [
        ("AF_INET", "SOCK_RAW"), ("AF_INET6", "SOCK_RAW"), ("AF_PACKET", "SOCK_RAW"), ("AF_NETLINK", "SOCK_RAW"),
        ("AF_INET", "SOCK_STREAM", "IPPROTO_SCTP"), ("AF_INET", "SOCK_DGRAM", "IPPROTO_ICMP"),
    ]
    if all(hasattr(socket, name) for name in names)
]
NAT64 = ipaddress.ip_network("64:ff9b::/96")


@pytest.fixture
def internal_url():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.2:{self.server.server_port}/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY.encode())

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()


def _run(code, params):
    return _execute_python_code_sync(code, params, wrap_code=False)


def allows(host, networks=(), family=None):
    """Whether the guard lets a socket of the host's family connect to *host*"""
    family = family or (socket.AF_INET6 if ":" in host else socket.AF_INET)
    with socket.socket(family) as sock:
        try:
            connection_guard(networks)("socket.connect", (sock, (host, 80)))
        except SandboxViolation:
            return False
    return True


def _ipaddress_allows(ip):
    """The address rule stated with ipaddress: embedded IPv4 judged as IPv4, IPv6 public only inside 2000::/3"""
    if ip.version == 6:
        ip = ip.ipv4_mapped or ip.sixtofour or (ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF) if ip in NAT64 else ip)
    if any(ip in network for network in sandbox._CLOUD_ENDPOINTS):
        return False
    return ip.is_global and not ip.is_multicast and (ip.version == 4 or ip in ipaddress.ip_network("2000::/3"))


def _socket_args(names):
    """socket() family, type and protocol for constant *names*, protocol 0 when not named"""
    values = tuple(getattr(socket, name) for name in names)
    return values if len(values) == 3 else (*values, 0)


def _boundaries(network):
    """Both ends of *network* and the addresses just outside it"""
    kind, top = type(network.network_address), 2**network.max_prefixlen - 1
    ends = (int(network.network_address), int(network.broadcast_address))
    return {kind(n) for end in ends for n in (end - 1, end, end + 1) if 0 <= n <= top}


@pytest.mark.parametrize(
    "host",
    [
        "0.0.0.0", "127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254",
        "100.64.0.1", "100.100.100.200", "192.0.0.192", "224.0.0.1", "255.255.255.255",
        "::", "::1", "::ffff:127.0.0.1", "::ffff:169.254.169.254", "::127.0.0.1",
        "64:ff9b::a9fe:a9fe", "64:ff9b:1::1", "fe80::1%eth0", "fec0::1", "fd00:ec2::254", "ff02::1",
        "::ffff:0:7f00:1", "2002:7f00:1::", "fd20:ce::254",
        "localhost", "metadata.google.internal", "127.1", "2130706433", "0x7f000001", "",
    ],
)
def test_non_public_and_unresolved_hosts_are_refused(host):
    assert not allows(host)


@pytest.mark.parametrize("host", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"])
def test_public_hosts_are_allowed(host):
    assert allows(host)


def test_guard_allows_nothing_ipaddress_calls_non_public_at_special_range_boundaries():
    special = [
        network
        for constants in (ipaddress._IPv4Constants, ipaddress._IPv6Constants)
        for value in vars(constants).values()
        for network in (value if isinstance(value, list) else [value])
        if isinstance(network, (ipaddress.IPv4Network, ipaddress.IPv6Network))
    ]
    ours = [*sandbox._NON_PUBLIC, *sandbox._PUBLIC_EXCEPTIONS, *sandbox._CLOUD_ENDPOINTS]
    ours += [network for network, _ in sandbox._EMBEDDED_IPV4]
    samples = {ip for network in special + ours for ip in _boundaries(network)}

    assert [ip for ip in samples if allows(str(ip)) and not _ipaddress_allows(ip)] == []


def test_cloud_endpoints_stay_blocked_even_when_listed():
    allowed = parse_allowed_networks("169.254.0.0/16,fd00::/8,168.63.0.0/16,0.0.0.0/0")

    for host in [
        "169.254.169.254", "::ffff:169.254.169.254", "fd00:ec2::254", "fd20:ce::254",
        "168.63.129.16", "64:ff9b::a83f:8110",
    ]:
        assert not allows(host, allowed)
    assert allows("168.63.129.17", allowed)
    assert allows("10.0.0.1", allowed)


def test_hosts_that_are_not_plain_strings_are_refused():
    class Host(str):
        pass

    assert not allows(Host("8.8.8.8"), family=socket.AF_INET)
    assert not allows(b"8.8.8.8", family=socket.AF_INET)


def test_allowed_networks_open_listed_internal_addresses(caplog):
    parse_allowed_networks.cache_clear()
    allowed = parse_allowed_networks(
        "10.0.5.12, 10.20.0.0/16,,internal.example,10.30.0.0/1,64:ff9b::a28:0/112,::ffff:10.50.0.0/112"
    )

    assert allows("10.0.5.12", allowed)
    assert allows("::ffff:10.20.3.4", allowed)
    assert allows("64:ff9b::a28:304", allowed) and allows("10.40.3.4", allowed)
    assert allows("10.50.3.4", allowed)
    assert not allows("10.0.5.13", allowed)
    assert not allows("127.0.0.1", allowed)
    assert len(allowed) == 4
    assert "internal.example" in caplog.text and "10.30.0.0/1" in caplog.text


def test_ipv6_allowlist_entries_must_be_unique_local(caplog):
    parse_allowed_networks.cache_clear()
    allowed = parse_allowed_networks("::/0,2002:a00:5::/48,64:ff9b:1::/48,fd00::/8")

    assert allowed == (ipaddress.ip_network("fd00::/8"),)
    assert allows("fd12::1", allowed)
    assert not allows("::ffff:127.0.0.1", allowed)
    assert not allows("64:ff9b:1::a9fe:a9fe", allowed)
    assert "fc00::/7" in caplog.text


def test_guard_checks_the_real_socket_and_address():
    class FakeFamily(socket.socket):
        @property
        def family(self):
            return socket.AF_INET

    class Address(tuple):
        def __getitem__(self, index):
            return "8.8.8.8" if index == 0 else tuple.__getitem__(self, index)

    guard = connection_guard()
    with socket.socket() as tcp, socket.socket(socket.AF_UNIX) as unix, FakeFamily(socket.AF_UNIX) as fake:
        guard("socket.connect", (tcp, ("8.8.8.8", 53)))
        guard("socket.sendmsg", (tcp, None))
        guard("socket.getaddrinfo", ("localhost", 80, 0, 0, 0))
        connection_guard(parse_allowed_networks("10.0.5.12"))("socket.connect", (tcp, ("10.0.5.12", 80)))
        for event, args in [
            ("socket.connect", (tcp, ("127.0.0.1", 80))),
            ("socket.sendto", (tcp, ("10.0.0.1", 53))),
            ("socket.connect", (tcp, ("localhost", 80))),
            ("socket.connect", (tcp, Address(("127.0.0.1", 80)))),
            ("socket.connect", (unix, "/var/run/docker.sock")),
            ("socket.connect", (fake, ("8.8.8.8", 53))),
        ]:
            with pytest.raises(SandboxViolation, match=BLOCKED):
                guard(event, args)


def test_only_tcp_udp_and_unix_sockets_can_be_opened():
    guard = connection_guard()
    flags = getattr(socket, "SOCK_NONBLOCK", 0) | getattr(socket, "SOCK_CLOEXEC", 0)

    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM | flags):
            guard("socket.__new__", (None, family, kind, 0))
    guard("socket.__new__", (None, socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP))
    guard("socket.__new__", (None, socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP))
    # -1 is a socket wrapped around a file descriptor without saying what it is
    for family, kind, protocol in [*map(_socket_args, OTHER_SOCKETS), (-1, -1, -1)]:
        with pytest.raises(SandboxViolation, match=SOCKET_BLOCKED):
            guard("socket.__new__", (None, family, kind, protocol))


def test_guard_does_not_depend_on_module_state_after_it_is_built(monkeypatch):
    guard = connection_guard(parse_allowed_networks("10.0.5.12"))
    for name in [*vars(sandbox), *vars(builtins)]:
        if not name.startswith("__"):
            monkeypatch.setitem(vars(sandbox), name, None)
    for cls in (ipaddress.IPv4Address, ipaddress.IPv6Address):
        monkeypatch.setattr(cls, "is_global", True)
        monkeypatch.setattr(cls, "is_private", False)
    monkeypatch.setattr(ipaddress._BaseNetwork, "__contains__", lambda *_: True)
    monkeypatch.setattr(ipaddress, "ip_address", lambda _: ipaddress.IPv4Address("8.8.8.8"))
    monkeypatch.setattr(_socket, "inet_pton", lambda *_: bytes([8, 8, 8, 8]))

    with socket.socket() as tcp, socket.socket(socket.AF_INET6) as tcp6:
        guard("socket.connect", (tcp, ("8.8.8.8", 53)))
        guard("socket.connect", (tcp, ("10.0.5.12", 80)))
        guard("socket.connect", (tcp6, ("2606:4700:4700::1111", 443)))
        guard("socket.__new__", (tcp, socket.AF_INET6, socket.SOCK_DGRAM, 0))
        for address in [(tcp, ("127.0.0.1", 80)), (tcp, ("10.0.5.13", 80)), (tcp6, ("::ffff:169.254.169.254", 80))]:
            with pytest.raises(SandboxViolation, match=BLOCKED):
                guard("socket.connect", address)
        with pytest.raises(SandboxViolation, match=SOCKET_BLOCKED):
            guard("socket.__new__", (tcp, socket.AF_INET, socket.SOCK_RAW, 0))


@skip_on_macos
@pytest.mark.parametrize(
    "code",
    [
        "result = requests.get(params['url']).text",
        "import requests\nresult = requests.get(params['url']).text",
        "import requests\nresult = requests.Session().get(params['url']).text",
        "result = pandas.read_csv(params['url']).to_dict('records')",
    ],
)
def test_libraries_cannot_reach_an_internal_url(internal_url, code):
    response = _run(code, {"url": internal_url})

    assert response["error"] == f"Sandbox violation: connection to 127.0.0.1 {BLOCKED}"


@skip_on_macos
@pytest.mark.parametrize("host", ["0.0.0.0", "2130706433", "localhost"])
def test_other_spellings_of_an_internal_address_are_blocked(internal_url, host):
    url = internal_url.replace("127.0.0.1", host)

    response = _run("result = requests.get(params['url']).text", {"url": url})

    assert BLOCKED in response["error"]


@pytest.mark.parametrize(
    "code",
    [
        "requests.adapters.socket.create_connection(params['address'])",
        "requests.adapters.socket.socket().connect_ex(params['address'])",
        "s = requests.adapters.socket\ns.socket(s.AF_INET, s.SOCK_DGRAM).sendto(b'x', params['address'])",
    ],
)
def test_socket_calls_cannot_reach_an_internal_address(internal_url, code):
    port = int(internal_url.rstrip("/").rsplit(":", 1)[1])

    response = _run(code, {"address": ("127.0.0.1", port)})

    assert response["error"] == f"Sandbox violation: connection to 127.0.0.1 {BLOCKED}"


@pytest.mark.parametrize("names", OTHER_SOCKETS)
def test_scripts_cannot_open_other_sockets(names):
    arguments = ", ".join(f"s.{name}" for name in names)

    response = _run(f"s = requests.adapters.socket\ns.socket({arguments})", {})

    assert response["error"] == f"Sandbox violation: {SOCKET_BLOCKED}"


def test_unix_sockets_cannot_connect():
    code = "s = requests.adapters.socket\ns.socket(s.AF_UNIX).connect('/var/run/docker.sock')"

    response = _run(code, {})

    assert response["error"] == f"Sandbox violation: connection to /var/run/docker.sock {BLOCKED}"


def test_scripts_can_use_local_socket_pairs():
    code = "a, b = requests.adapters.socket.socketpair()\na.sendall(b'ping')\nresult = b.recv(4)"

    response = _run(code, {})

    assert "error" not in response
    assert response["result"] == b"ping"


def test_listed_network_is_reachable(internal_url, monkeypatch):
    monkeypatch.setattr(utils.settings, "SANDBOX_ALLOWED_NETWORKS", "127.0.0.1")

    response = _run(SESSION + "result = session.get(params['url']).text", {"url": internal_url})

    assert "error" not in response
    assert response["result"] == BODY


def test_redirect_to_an_internal_address_is_blocked(internal_url, monkeypatch):
    monkeypatch.setattr(utils.settings, "SANDBOX_ALLOWED_NETWORKS", "127.0.0.1")

    response = _run(SESSION + "result = session.get(params['url']).text", {"url": internal_url + "redirect"})

    assert response["error"] == f"Sandbox violation: connection to 127.0.0.2 {BLOCKED}"


def test_requests_is_the_real_library():
    response = _run("result = (requests.request.__module__, requests.exceptions.RequestException.__name__)", {})

    assert response["result"] == ("requests.api", "RequestException")
