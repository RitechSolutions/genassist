"""Unit tests that the file manager URL download refuses internal addresses and oversized files."""

import socket
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.utils import web_scraping_utils
from app.repositories.file_manager import FileManagerRepository
from app.services import file_manager
from app.services.file_manager import FileManagerService

PUBLIC_IP = "93.184.216.34"
HOST_ADDRESSES = {"public.example": PUBLIC_IP, "internal.example": "10.0.0.5"}


@pytest.fixture
def service():
    return FileManagerService(repository=AsyncMock(spec=FileManagerRepository))


@pytest.fixture
def resolver(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        address = HOST_ADDRESSES.get(host, host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(web_scraping_utils.socket, "getaddrinfo", fake_getaddrinfo)


@pytest.fixture
def responses(monkeypatch):
    requested_urls = []
    replies = {}

    async def fake_send(transport, request):
        url = str(request.url)
        requested_urls.append(url)
        status, headers, content = replies.get(url, (200, {}, b"a,b\n1,2\n"))
        return httpx.Response(status, headers=headers, content=content)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_send)
    return requested_urls, replies


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/data.csv",
        "http://10.0.0.5/data.csv",
        "http://internal.example/data.csv",
        "file:///etc/passwd",
    ],
)
async def test_internal_urls_are_refused_without_a_request(service, resolver, responses, tmp_path, url):
    requested_urls, _ = responses
    destination = tmp_path / "download.csv"

    assert await service.download_file_from_url_to_path(url, str(destination)) is False
    assert requested_urls == []
    assert not destination.exists()


@pytest.mark.asyncio
async def test_a_public_file_is_downloaded(service, resolver, responses, tmp_path):
    destination = tmp_path / "download.csv"

    assert await service.download_file_from_url_to_path("https://public.example/data.csv", str(destination)) is True
    assert destination.read_bytes() == b"a,b\n1,2\n"


@pytest.mark.asyncio
async def test_a_redirect_is_not_followed(service, resolver, responses, tmp_path):
    requested_urls, replies = responses
    replies["https://public.example/data.csv"] = (302, {"location": "http://169.254.169.254/latest/meta-data/"}, b"")
    destination = tmp_path / "download.csv"

    assert await service.download_file_from_url_to_path("https://public.example/data.csv", str(destination)) is False
    assert requested_urls == ["https://public.example/data.csv"]
    assert not destination.exists()


@pytest.mark.asyncio
async def test_a_file_over_the_size_limit_is_refused_and_removed(service, resolver, responses, tmp_path, monkeypatch):
    _, replies = responses
    replies["https://public.example/big.csv"] = (200, {}, b"x" * 11)
    monkeypatch.setattr(file_manager.settings, "MAX_CONTENT_LENGTH", 10)
    destination = tmp_path / "download.csv"

    assert await service.download_file_from_url_to_path("https://public.example/big.csv", str(destination)) is False
    assert not destination.exists()


@pytest.mark.asyncio
async def test_a_file_at_the_size_limit_is_kept(service, resolver, responses, tmp_path, monkeypatch):
    _, replies = responses
    replies["https://public.example/exact.csv"] = (200, {}, b"x" * 10)
    monkeypatch.setattr(file_manager.settings, "MAX_CONTENT_LENGTH", 10)
    destination = tmp_path / "download.csv"

    assert await service.download_file_from_url_to_path("https://public.example/exact.csv", str(destination)) is True
    assert destination.read_bytes() == b"x" * 10


@pytest.mark.asyncio
async def test_a_failed_download_leaves_no_file(service, resolver, responses, tmp_path):
    _, replies = responses
    replies["https://public.example/missing.csv"] = (404, {}, b"")
    destination = tmp_path / "download.csv"

    assert await service.download_file_from_url_to_path("https://public.example/missing.csv", str(destination)) is False
    assert not destination.exists()
