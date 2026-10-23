"""Unit tests that the file manager URL download refuses internal addresses and oversized files."""

import socket
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils import web_scraping_utils
from app.repositories.file_manager import FileManagerRepository
from app.services import file_manager
from app.services.file_manager import FileManagerService

BLOCKED_MESSAGE = "URL is not allowed or cannot be reached."
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


def _error_detail(call):
    with pytest.raises(AppException) as raised:
        call()
    return raised.value.error_detail


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

    with pytest.raises(AppException) as raised:
        await service.download_file_from_url_to_path(url, str(destination))

    assert raised.value.error_detail == BLOCKED_MESSAGE
    assert raised.value.status_code == 400
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

    with pytest.raises(AppException):
        await service.download_file_from_url_to_path("https://public.example/data.csv", str(destination))

    assert requested_urls == ["https://public.example/data.csv"]
    assert not destination.exists()


@pytest.mark.asyncio
async def test_a_file_over_the_size_limit_is_refused_and_removed(service, resolver, responses, tmp_path, monkeypatch):
    _, replies = responses
    replies["https://public.example/big.csv"] = (200, {}, b"x" * 11)
    monkeypatch.setattr(file_manager.settings, "MAX_CONTENT_LENGTH", 10)
    destination = tmp_path / "download.csv"

    with pytest.raises(AppException) as raised:
        await service.download_file_from_url_to_path("https://public.example/big.csv", str(destination))

    assert "larger than" in raised.value.error_detail
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
async def test_a_failed_download_is_reported_and_leaves_no_file(service, resolver, responses, tmp_path):
    _, replies = responses
    replies["https://public.example/missing.csv"] = (404, {}, b"")
    destination = tmp_path / "download.csv"

    with pytest.raises(AppException) as raised:
        await service.download_file_from_url_to_path("https://public.example/missing.csv", str(destination))

    assert "404" in raised.value.error_detail
    assert not destination.exists()


@pytest.mark.asyncio
async def test_a_refused_download_never_deletes_a_file_that_was_already_there(service, resolver, responses, tmp_path):
    destination = tmp_path / "existing.csv"
    destination.write_bytes(b"keep me")

    with pytest.raises(AppException):
        await service.download_file_from_url_to_path("http://internal.example/data.csv", str(destination))

    assert destination.read_bytes() == b"keep me"


@pytest.mark.asyncio
async def test_our_own_file_link_is_read_from_storage_without_a_request(service, resolver, responses, tmp_path, monkeypatch):
    requested_urls, _ = responses
    file_id = uuid.uuid4()
    stored_file = SimpleNamespace(id=file_id)
    monkeypatch.setattr(service, "get_file_by_id", AsyncMock(return_value=stored_file))
    monkeypatch.setattr(service, "get_file_content", AsyncMock(return_value=b"own,file\n1,2\n"))
    destination = tmp_path / "download.csv"

    own_link = f"http://app:8000/api/file-manager/files/{file_id}/source?X-Tenant-Id=master"
    assert await service.download_file_from_url_to_path(own_link, str(destination)) is True

    assert destination.read_bytes() == b"own,file\n1,2\n"
    assert requested_urls == []
    service.get_file_by_id.assert_awaited_once_with(file_id)


@pytest.mark.asyncio
async def test_a_timeout_with_no_message_is_still_reported_as_a_download_error(service, resolver, tmp_path, monkeypatch):
    async def timing_out(transport, request):
        raise httpx.ReadTimeout("")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", timing_out)

    with pytest.raises(AppException) as raised:
        await service.download_file_from_url_to_path("https://public.example/slow.csv", str(tmp_path / "download.csv"))

    assert raised.value.error_detail == "Could not download the file: ReadTimeout"


@pytest.mark.asyncio
async def test_a_disk_error_does_not_reveal_the_server_path(service, resolver, responses, tmp_path, monkeypatch):
    def failing_makedirs(*args, **kwargs):
        raise PermissionError(13, "Permission denied", "/secret/server/folder")

    monkeypatch.setattr(file_manager.os, "makedirs", failing_makedirs)

    with pytest.raises(AppException) as raised:
        await service.download_file_from_url_to_path("https://public.example/data.csv", str(tmp_path / "download.csv"))

    assert raised.value.error_detail == "Could not download the file."


@pytest.mark.asyncio
async def test_an_own_file_missing_from_storage_is_reported_as_not_found(service, resolver, responses, tmp_path, monkeypatch):
    monkeypatch.setattr(service, "get_file_by_id", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr(service, "get_file_content", AsyncMock(side_effect=FileNotFoundError("blob gone")))
    destination = tmp_path / "download.csv"

    with pytest.raises(AppException) as raised:
        await service.download_file_from_url_to_path(f"http://app:8000/api/file-manager/files/{uuid.uuid4()}/source", str(destination))

    assert raised.value.status_code == 404
    assert not destination.exists()


@pytest.mark.asyncio
async def test_an_own_file_link_to_a_deleted_file_is_reported_as_not_found(service, resolver, responses, tmp_path, monkeypatch):
    monkeypatch.setattr(service, "get_file_by_id", AsyncMock(side_effect=AppException(ErrorKey.DATASOURCE_NOT_FOUND)))

    with pytest.raises(AppException) as raised:
        await service.download_file_from_url_to_path(f"http://app:8000/api/file-manager/files/{uuid.uuid4()}/source", str(tmp_path / "download.csv"))

    assert raised.value.status_code == 404
    assert raised.value.error_detail == "File not found."


@pytest.mark.asyncio
async def test_a_public_link_that_merely_contains_a_uuid_is_still_downloaded(service, resolver, responses, tmp_path):
    requested_urls, _ = responses
    destination = tmp_path / "download.csv"
    public_link = f"https://public.example/files/{uuid.uuid4()}/data.csv"

    assert await service.download_file_from_url_to_path(public_link, str(destination)) is True
    assert requested_urls == [public_link]


@pytest.mark.asyncio
async def test_a_failed_own_file_write_never_deletes_a_file_that_was_already_there(service, resolver, responses, tmp_path, monkeypatch):
    monkeypatch.setattr(service, "get_file_by_id", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr(service, "get_file_content", AsyncMock(return_value=b"own,file\n1,2\n"))
    monkeypatch.setattr(file_manager.os, "makedirs", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError(13, "Permission denied")))
    destination = tmp_path / "existing.csv"
    destination.write_bytes(b"keep me")

    with pytest.raises(AppException):
        await service.download_file_from_url_to_path(f"http://app:8000/api/file-manager/files/{uuid.uuid4()}/source", str(destination))

    assert destination.read_bytes() == b"keep me"
