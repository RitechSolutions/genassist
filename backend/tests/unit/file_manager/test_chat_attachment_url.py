"""Chat attachments on local storage get a working link while the turn runs.

The turn runs on its own FileManagerService, whose storage provider was set up
without a base URL (only ``initialize`` sets one). Sending a message with an
uploaded file used to fail the whole turn with "Storage provider base URL not set".
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.api.v1.routes  # noqa: F401  (loads the routes first; the use case module imports them circularly)
from app.core.tenant_scope import set_tenant_context
from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.repositories.file_manager import FileManagerRepository
from app.services.file_manager import FileManagerService
from app.use_cases import chat_as_client_use_case

BASE_URL = "http://localhost:8000"


@pytest.fixture
def service(tmp_path):
    svc = FileManagerService(repository=AsyncMock(spec=FileManagerRepository))
    # A provider set up the way the turn's lazy init does it: no base_url in its config.
    svc.storage_provider = LocalFileSystemProvider({"base_path": str(tmp_path)})
    return svc


@pytest.fixture(autouse=True)
def tenant():
    set_tenant_context("master")


CONVERSATION_ID = uuid.uuid4()


def _local_file(tmp_path):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="photo.jpg",
        file_extension="jpg",
        mime_type="image/jpeg",
        storage_provider="local",
        storage_path=str(tmp_path),
        path=f"agents_config/upload-chat-files/{CONVERSATION_ID}/photo.jpg",
    )


def _source_url(base, file_id):
    return f"{base}/api/file-manager/files/{file_id}/source?X-Tenant-Id=master"


@pytest.mark.asyncio
async def test_local_file_url_uses_the_given_base_url(service, tmp_path):
    await service.storage_provider.initialize()
    file = _local_file(tmp_path)
    assert await service.get_file_url(file, base_url=BASE_URL) == _source_url(BASE_URL, file.id)


@pytest.mark.asyncio
async def test_local_file_url_still_needs_some_base_url(service, tmp_path):
    await service.storage_provider.initialize()
    with pytest.raises(ValueError, match="base URL not set"):
        await service.get_file_url(_local_file(tmp_path))


@pytest.mark.asyncio
async def test_provider_base_url_wins_over_the_given_one(service, tmp_path):
    service.storage_provider.config["base_url"] = "https://files.example"
    await service.storage_provider.initialize()
    file = _local_file(tmp_path)
    assert await service.get_file_url(file, base_url=BASE_URL) == _source_url("https://files.example", file.id)


@pytest.mark.asyncio
async def test_chat_attachment_on_local_storage_gets_a_single_prefixed_link(service, tmp_path, monkeypatch):
    await service.storage_provider.initialize()
    file = _local_file(tmp_path)
    service.get_file_by_id = AsyncMock(return_value=file)
    recorded = AsyncMock()
    monkeypatch.setattr(chat_as_client_use_case, "process_file_upload_from_chat", recorded)

    attachment = {"name": "photo.jpg", "type": "image/jpeg", "file_id": str(file.id)}
    model = SimpleNamespace(metadata={"attachments": [attachment]})

    await chat_as_client_use_case.process_attachments_from_metadata(
        base_url=BASE_URL,
        conversation_id=CONVERSATION_ID,
        model=model,
        tenant_id="master",
        current_user_id=uuid.uuid4(),
        file_manager_service=service,
    )

    expected = _source_url(BASE_URL, file.id)
    assert attachment["file_url"] == expected
    assert attachment["file_local_path"] == f"{file.storage_path}/{file.path}"
    assert attachment["file_storage_provider"] == "local"
    assert recorded.await_args.kwargs["file_url"] == expected
