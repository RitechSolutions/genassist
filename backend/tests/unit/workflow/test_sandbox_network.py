import http.server
import ipaddress
import socket
import sys
import threading

import pytest

from app.modules.workflow import utils
from app.modules.workflow.sandbox import (
    SandboxViolation,
    connection_allowed,
    parse_allowed_networks,
    refuse_internal_address,
)
from app.modules.workflow.utils import _execute_python_code_sync

BODY = "a,b\nsecret,42\n"
BLOCKED = "is blocked. Sandboxed code can only connect to public IP addresses and those an administrator allows"
# requests and pandas read the system proxy settings, which crashes forked children on macOS
skip_on_macos = pytest.mark.skipif(
    sys.platform == "darwin", reason="system proxy lookup crashes forked children on macOS"
)
SESSION = "session = requests.Session()\nsession.trust_env = False\n"


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
    assert not connection_allowed(host)


@pytest.mark.parametrize("host", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"])
def test_public_hosts_are_allowed(host):
    assert connection_allowed(host)


def test_cloud_endpoints_stay_blocked_even_when_listed():
    allowed = parse_allowed_networks("169.254.0.0/16,fd00::/8,168.63.0.0/16,0.0.0.0/0")

    for host in [
        "169.254.169.254", "::ffff:169.254.169.254", "fd00:ec2::254", "fd20:ce::254",
        "168.63.129.16", "64:ff9b::a83f:8110",
    ]:
        assert not connection_allowed(host, allowed)
    assert connection_allowed("168.63.129.17", allowed)
    assert connection_allowed("10.0.0.1", allowed)


def test_hosts_that_are_not_plain_strings_are_refused():
    class Host(str):
        def __str__(self):
            return "8.8.8.8"

    assert not connection_allowed(Host("127.0.0.1"))
    assert not connection_allowed(b"8.8.8.8")


def test_allowed_networks_open_listed_internal_addresses(caplog):
    parse_allowed_networks.cache_clear()
    allowed = parse_allowed_networks(
        "10.0.5.12, 10.20.0.0/16,,internal.example,10.30.0.0/1,64:ff9b::a28:0/112,::ffff:10.50.0.0/112"
    )

    assert connection_allowed("10.0.5.12", allowed)
    assert connection_allowed("::ffff:10.20.3.4", allowed)
    assert connection_allowed("64:ff9b::a28:304", allowed) and connection_allowed("10.40.3.4", allowed)
    assert connection_allowed("10.50.3.4", allowed)
    assert not connection_allowed("10.0.5.13", allowed)
    assert not connection_allowed("127.0.0.1", allowed)
    assert len(allowed) == 4
    assert "internal.example" in caplog.text and "10.30.0.0/1" in caplog.text


def test_ipv6_allowlist_entries_must_be_unique_local(caplog):
    parse_allowed_networks.cache_clear()
    allowed = parse_allowed_networks("::/0,2002:a00:5::/48,64:ff9b:1::/48,fd00::/8")

    assert allowed == (ipaddress.ip_network("fd00::/8"),)
    assert connection_allowed("fd12::1", allowed)
    assert not connection_allowed("::ffff:127.0.0.1", allowed)
    assert not connection_allowed("64:ff9b:1::a9fe:a9fe", allowed)
    assert "fc00::/7" in caplog.text


def test_guard_checks_the_real_socket_and_address():
    class FakeFamily(socket.socket):
        @property
        def family(self):
            return socket.AF_INET

    class Address(tuple):
        def __getitem__(self, index):
            return "8.8.8.8" if index == 0 else tuple.__getitem__(self, index)

    with socket.socket() as tcp, socket.socket(socket.AF_UNIX) as unix, FakeFamily(socket.AF_UNIX) as fake:
        refuse_internal_address("socket.connect", (tcp, ("8.8.8.8", 53)))
        refuse_internal_address("socket.sendmsg", (tcp, None))
        refuse_internal_address("socket.getaddrinfo", ("localhost", 80, 0, 0, 0))
        refuse_internal_address("socket.connect", (tcp, ("10.0.5.12", 80)), parse_allowed_networks("10.0.5.12"))
        for event, args in [
            ("socket.connect", (tcp, ("127.0.0.1", 80))),
            ("socket.sendto", (tcp, ("10.0.0.1", 53))),
            ("socket.connect", (tcp, ("localhost", 80))),
            ("socket.connect", (tcp, Address(("127.0.0.1", 80)))),
            ("socket.connect", (unix, "/var/run/docker.sock")),
            ("socket.connect", (fake, ("8.8.8.8", 53))),
        ]:
            with pytest.raises(SandboxViolation, match=BLOCKED):
                refuse_internal_address(event, args)


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
def test_raw_sockets_cannot_reach_an_internal_address(internal_url, code):
    port = int(internal_url.rstrip("/").rsplit(":", 1)[1])

    response = _run(code, {"address": ("127.0.0.1", port)})

    assert response["error"] == f"Sandbox violation: connection to 127.0.0.1 {BLOCKED}"


def test_unix_sockets_are_blocked():
    code = "s = requests.adapters.socket\ns.socket(s.AF_UNIX).connect('/var/run/docker.sock')"

    response = _run(code, {})

    assert response["error"] == f"Sandbox violation: connection to /var/run/docker.sock {BLOCKED}"


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
