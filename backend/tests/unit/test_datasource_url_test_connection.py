"""Unit tests that the URL data source test connection refuses internal addresses."""

import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.api.v1.routes import datasources as datasource_routes
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.core.utils import web_scraping_utils
from app.repositories.datasources import DataSourcesRepository
from app.services.datasources import DataSourceService

BLOCKED_MESSAGE = "URL is not allowed or cannot be reached."
PUBLIC_IP = "93.184.216.34"
HOST_ADDRESSES = {
    "public.example": PUBLIC_IP,
    "internal.example": "10.0.0.5",
    "strasse.attacker.example": PUBLIC_IP,
    "xn--strae-oqa.attacker.example": "169.254.169.254",
}


@pytest.fixture
def service():
    return DataSourceService(repository=AsyncMock(spec=DataSourcesRepository))


@pytest.fixture
def resolver(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        # Encodes non-ASCII names the way the real resolver does
        lookup_name = host.encode("idna").decode("ascii")
        address = HOST_ADDRESSES.get(lookup_name, host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(web_scraping_utils.socket, "getaddrinfo", fake_getaddrinfo)


@pytest.fixture
def responses(monkeypatch):
    requested_urls = []
    replies = {}

    async def fake_send(transport, request):
        url = str(request.url)
        requested_urls.append(url)
        status, headers = replies.get(url, (200, {}))
        return httpx.Response(status, headers=headers)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_send)
    return requested_urls, replies


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/",
        "http://10.0.0.5/admin",
        "http://internal.example/",
        "file:///etc/passwd",
    ],
)
async def test_internal_urls_are_refused_without_a_request(service, resolver, responses, url):
    requested_urls, _ = responses

    result = await service.test_connection("url", {"url": url})

    assert result["success"] is False
    assert result["message"] == BLOCKED_MESSAGE
    assert requested_urls == []


@pytest.mark.asyncio
async def test_a_redirect_to_an_internal_address_is_refused(service, resolver, responses):
    requested_urls, replies = responses
    replies["https://public.example/doc"] = (302, {"location": "http://169.254.169.254/latest/meta-data/"})

    result = await service.test_connection("url", {"url": "https://public.example/doc"})

    assert result["success"] is False
    assert result["message"] == BLOCKED_MESSAGE
    assert requested_urls == ["https://public.example/doc"]


@pytest.mark.asyncio
async def test_a_non_ascii_hostname_is_checked_under_the_name_it_connects_to(service, resolver, responses):
    requested_urls, _ = responses

    result = await service.test_connection("url", {"url": "http://straße.attacker.example/latest/meta-data/"})

    assert result["success"] is False
    assert requested_urls == []


@pytest.mark.asyncio
async def test_a_public_url_is_accessible(service, resolver, responses):
    requested_urls, _ = responses

    result = await service.test_connection("url", {"url": "https://public.example/doc"})

    assert result == {"success": True, "message": "URL is accessible."}
    assert requested_urls == ["https://public.example/doc"]


@pytest.mark.asyncio
async def test_a_public_redirect_is_followed(service, resolver, responses):
    requested_urls, replies = responses
    replies["http://public.example/doc"] = (301, {"location": "https://public.example/doc"})

    result = await service.test_connection("url", {"url": "http://public.example/doc"})

    assert result["success"] is True
    assert requested_urls == ["http://public.example/doc", "https://public.example/doc"]


@pytest.mark.asyncio
async def test_a_missing_page_is_still_reported_as_a_failure(service, resolver, responses):
    _, replies = responses
    replies["https://public.example/missing"] = (404, {})

    result = await service.test_connection("url", {"url": "https://public.example/missing"})

    assert result["success"] is False
    assert "404" in result["message"]


def _request(permissions):
    return SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(permissions=permissions)))


@pytest.mark.asyncio
async def test_test_connection_requires_login_and_the_data_source_read_permission():
    route = next(r for r in datasource_routes.router.routes if r.path == "/test-connection")
    calls = [dependency.dependency for dependency in route.dependencies]
    assert datasource_routes.auth in calls
    permission_checks = [call for call in calls if call is not datasource_routes.auth]
    assert permission_checks

    for check in permission_checks:
        await check(_request([P.DataSource.READ]))

    denied = 0
    for check in permission_checks:
        try:
            await check(_request([]))
        except AppException:
            denied += 1
    assert denied == len(permission_checks)
