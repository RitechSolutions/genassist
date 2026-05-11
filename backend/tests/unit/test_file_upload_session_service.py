import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.filemanager.providers.s3.provider import S3StorageProvider
from app.schemas.files_upload_direct import (
    FinalizeDirectUploadRequest,
    PresignDirectUploadCreate,
)
from app.services.file_upload_session import (
    STATUS_AWAITING_CLIENT_UPLOAD,
    STATUS_COMPLETED,
    STATUS_FAILED,
    UPLOAD_MODE_DIRECT_S3,
    FileUploadSessionService,
)


def _row(**kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        status="receiving",
        original_filename="demo.pdf",
        content_type="application/pdf",
        temp_path="/tmp/demo.part",
        owner_pod_id=None,
        bytes_received=0,
        expected_bytes=None,
        next_chunk_index=0,
        multipart_upload_id=None,
        object_key=None,
        parts_json={},
        error_message=None,
        result_json=None,
        is_deleted=0,
        upload_mode=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_append_chunk_rejects_out_of_order():
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    repo.get_by_id.return_value = _row(id=sid, next_chunk_index=2, bytes_received=10)

    with pytest.raises(ValueError, match="Out-of-order chunk"):
        await service.append_chunk(sid, b"abc", chunk_index=3)


@pytest.mark.asyncio
async def test_append_chunk_duplicate_returns_current_total():
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    repo.get_by_id.return_value = _row(id=sid, next_chunk_index=2, bytes_received=15)

    total = await service.append_chunk(sid, b"abc", chunk_index=1)
    assert total == 15


@pytest.mark.asyncio
async def test_append_chunk_assigns_owner_and_advances():
    repo = AsyncMock()
    repo.advance_chunk_progress.return_value = True
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    row = _row(id=sid, next_chunk_index=0, bytes_received=0, owner_pod_id=None)
    repo.get_by_id.return_value = row

    total = await service.append_chunk(sid, b"hello", chunk_index=0)
    assert total == 5
    assert row.owner_pod_id is not None
    repo.update.assert_called()
    repo.advance_chunk_progress.assert_called_once()


@pytest.mark.asyncio
async def test_complete_session_fails_for_missing_staged_file(monkeypatch):
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    row = _row(id=sid, bytes_received=10, expected_bytes=10, temp_path="/tmp/missing.part")
    repo.get_by_id.return_value = row
    monkeypatch.setattr("app.services.file_upload_session.os.path.isfile", lambda _: False)

    with pytest.raises(ValueError, match="Staged upload file missing on server"):
        await service.complete_session(
            sid,
            request=SimpleNamespace(base_url="http://localhost/"),
            file_manager_service=AsyncMock(),
            app_settings_svc=AsyncMock(),
        )


@pytest.mark.asyncio
async def test_complete_session_multipart_integrity_mismatch():
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    row = _row(
        id=sid,
        bytes_received=15,
        expected_bytes=15,
        multipart_upload_id="upload-1",
        object_key="uploads/file.bin",
        parts_json={"0": {"part_number": 1, "etag": "e1", "size": 10}},
    )
    repo.get_by_id.return_value = row

    fm = AsyncMock()
    storage = object.__new__(S3StorageProvider)
    storage.name = "s3"
    storage.complete_multipart_upload = AsyncMock()
    storage.abort_multipart_upload = AsyncMock()
    fm.initialize.return_value = storage
    settings_svc = AsyncMock()
    settings_svc.get_by_type_and_name.return_value = {"values": {}}
    service._multipart_enabled = lambda: True

    with pytest.raises(ValueError, match="integrity check failed"):
        await service.complete_session(
            sid,
            request=SimpleNamespace(base_url="http://localhost/"),
            file_manager_service=fm,
            app_settings_svc=settings_svc,
        )


# ==================== Direct S3 (presigned PUT) flow tests ====================


def _build_fm_service(provider_name: str = "s3"):
    """Mock for ``FileManagerService`` exposing the bits the direct flow uses."""
    fm = AsyncMock()
    storage = MagicMock()
    storage.name = provider_name
    storage.get_base_path = MagicMock(return_value="my-bucket")
    storage.generate_presigned_put_url = AsyncMock(
        return_value="https://my-bucket.s3.amazonaws.com/key?sig"
    )
    storage.head_object = AsyncMock()
    storage.delete_file = AsyncMock(return_value=True)
    fm.initialize.return_value = storage
    fm.get_file_source_url = AsyncMock(return_value="http://localhost/api/file-manager/files/abc/source")
    fm.repository = MagicMock()
    fm.repository.create_file = AsyncMock()
    fm.repository.get_file_by_id = AsyncMock()
    fm.repository.delete_file = AsyncMock()
    fm.repository.db = MagicMock()
    fm.repository.db.commit = AsyncMock()
    fm.repository.db.refresh = AsyncMock()
    return fm, storage


def _build_settings_svc():
    s = AsyncMock()
    s.get_by_type_and_name.return_value = {"values": {"file_manager_provider": "s3"}}
    return s


@pytest.mark.asyncio
async def test_create_direct_upload_session_disabled_flag_returns_501(monkeypatch):
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    monkeypatch.setattr(service, "_direct_s3_enabled", lambda: False)

    with pytest.raises(AppException) as ei:
        await service.create_direct_upload_session(
            PresignDirectUploadCreate(
                original_filename="x.pdf", expected_size=10, content_type="application/pdf"
            ),
            request=SimpleNamespace(base_url="http://localhost/"),
            file_manager_service=AsyncMock(),
            app_settings_svc=AsyncMock(),
        )
    assert ei.value.status_code == 501


@pytest.mark.asyncio
async def test_create_direct_upload_session_wrong_provider_returns_501(monkeypatch):
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    monkeypatch.setattr(service, "_direct_s3_enabled", lambda: True)
    fm, _ = _build_fm_service(provider_name="local")

    with pytest.raises(AppException) as ei:
        await service.create_direct_upload_session(
            PresignDirectUploadCreate(
                original_filename="x.pdf", expected_size=10, content_type="application/pdf"
            ),
            request=SimpleNamespace(base_url="http://localhost/"),
            file_manager_service=fm,
            app_settings_svc=_build_settings_svc(),
        )
    assert ei.value.status_code == 501


@pytest.mark.asyncio
async def test_create_direct_upload_session_happy_path(monkeypatch):
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    monkeypatch.setattr(service, "_direct_s3_enabled", lambda: True)
    monkeypatch.setattr(service, "_direct_s3_expires_in", lambda: 600)

    fm, storage = _build_fm_service()
    file_uuid = uuid.uuid4()
    fm.repository.create_file.return_value = SimpleNamespace(id=file_uuid)

    resp = await service.create_direct_upload_session(
        PresignDirectUploadCreate(
            original_filename="report.pdf",
            expected_size=2048,
            content_type="application/pdf",
        ),
        request=SimpleNamespace(base_url="http://localhost/"),
        file_manager_service=fm,
        app_settings_svc=_build_settings_svc(),
        sub_folder="uploads",
    )

    assert resp.file_id == str(file_uuid)
    assert resp.method == "PUT"
    assert resp.required_headers == {"Content-Type": "application/pdf"}
    assert resp.object_key.startswith("uploads/")
    assert resp.expires_in == 600
    storage.generate_presigned_put_url.assert_awaited_once()
    repo.create.assert_awaited_once()
    persisted = repo.create.call_args.args[0]
    assert persisted.status == STATUS_AWAITING_CLIENT_UPLOAD
    assert persisted.upload_mode == UPLOAD_MODE_DIRECT_S3
    assert persisted.result_json["file_id"] == str(file_uuid)


@pytest.mark.asyncio
async def test_finalize_direct_upload_size_mismatch_cleans_up(monkeypatch):
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    file_uuid = uuid.uuid4()
    row = _row(
        id=sid,
        status=STATUS_AWAITING_CLIENT_UPLOAD,
        upload_mode=UPLOAD_MODE_DIRECT_S3,
        bytes_received=0,
        expected_bytes=2048,
        result_json={
            "object_key": "uploads/key.pdf",
            "file_id": str(file_uuid),
            "sub_folder": "uploads",
            "unique_filename": "key.pdf",
            "provider_name": "s3",
        },
    )
    repo.get_by_id.return_value = row
    fm, storage = _build_fm_service()
    storage.head_object.return_value = {
        "key": "uploads/key.pdf",
        "size": 9999,  # wildly different from expected_bytes=2048
        "etag": "abc",
        "content_type": "application/pdf",
    }

    with pytest.raises(ValueError, match="Size mismatch"):
        await service.finalize_direct_upload_session(
            sid,
            FinalizeDirectUploadRequest(success=True, etag="abc"),
            request=SimpleNamespace(base_url="http://localhost/"),
            file_manager_service=fm,
            app_settings_svc=_build_settings_svc(),
        )
    storage.delete_file.assert_awaited_once_with("uploads/key.pdf")
    fm.repository.delete_file.assert_awaited_once_with(file_uuid)
    assert row.status == STATUS_FAILED


@pytest.mark.asyncio
async def test_finalize_direct_upload_client_failure_cleans_up():
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    file_uuid = uuid.uuid4()
    row = _row(
        id=sid,
        status=STATUS_AWAITING_CLIENT_UPLOAD,
        upload_mode=UPLOAD_MODE_DIRECT_S3,
        result_json={
            "object_key": "uploads/key.pdf",
            "file_id": str(file_uuid),
            "sub_folder": "uploads",
            "unique_filename": "key.pdf",
            "provider_name": "s3",
        },
    )
    repo.get_by_id.return_value = row
    fm, storage = _build_fm_service()

    with pytest.raises(ValueError, match="Client reported upload failure"):
        await service.finalize_direct_upload_session(
            sid,
            FinalizeDirectUploadRequest(
                success=False, error_message="Client reported upload failure."
            ),
            request=SimpleNamespace(base_url="http://localhost/"),
            file_manager_service=fm,
            app_settings_svc=_build_settings_svc(),
        )

    storage.delete_file.assert_awaited_once_with("uploads/key.pdf")
    fm.repository.delete_file.assert_awaited_once_with(file_uuid)
    assert row.status == STATUS_FAILED
    storage.head_object.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_direct_upload_success_completes():
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    file_uuid = uuid.uuid4()
    row = _row(
        id=sid,
        status=STATUS_AWAITING_CLIENT_UPLOAD,
        upload_mode=UPLOAD_MODE_DIRECT_S3,
        bytes_received=0,
        expected_bytes=2048,
        original_filename="report.pdf",
        result_json={
            "object_key": "uploads/key.pdf",
            "file_id": str(file_uuid),
            "sub_folder": "uploads",
            "unique_filename": "key.pdf",
            "provider_name": "s3",
        },
    )
    repo.get_by_id.return_value = row

    fm, storage = _build_fm_service()
    storage.head_object.return_value = {
        "key": "uploads/key.pdf",
        "size": 2048,
        "etag": "abc",
        "content_type": "application/pdf",
    }
    db_file = SimpleNamespace(
        id=file_uuid,
        name="key.pdf",
        size=None,
        mime_type=None,
        file_metadata={},
    )
    fm.repository.get_file_by_id.return_value = db_file

    resp = await service.finalize_direct_upload_session(
        sid,
        FinalizeDirectUploadRequest(success=True, etag="abc"),
        request=SimpleNamespace(base_url="http://localhost/"),
        file_manager_service=fm,
        app_settings_svc=_build_settings_svc(),
    )

    assert resp.file_id == str(file_uuid)
    assert resp.original_filename == "report.pdf"
    assert resp.file_url and resp.file_url.endswith("/source")
    assert db_file.size == 2048
    assert db_file.file_metadata["status"] == "completed"
    assert row.status == STATUS_COMPLETED
    assert row.bytes_received == 2048
    storage.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_direct_upload_idempotent_when_already_completed():
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    file_uuid = uuid.uuid4()
    cached = {
        "object_key": "uploads/key.pdf",
        "file_id": str(file_uuid),
        "sub_folder": "uploads",
        "unique_filename": "key.pdf",
        "provider_name": "s3",
        "file_url": "http://localhost/api/file-manager/files/abc/source",
        "filename": "key.pdf",
        "original_filename": "report.pdf",
        "file_type": "url",
    }
    row = _row(
        id=sid,
        status=STATUS_COMPLETED,
        upload_mode=UPLOAD_MODE_DIRECT_S3,
        result_json=cached,
        original_filename="report.pdf",
    )
    repo.get_by_id.return_value = row

    fm, _ = _build_fm_service()

    resp = await service.finalize_direct_upload_session(
        sid,
        FinalizeDirectUploadRequest(success=True),
        request=SimpleNamespace(base_url="http://localhost/"),
        file_manager_service=fm,
        app_settings_svc=_build_settings_svc(),
    )
    assert resp.file_id == str(file_uuid)
    assert resp.file_url == cached["file_url"]
    fm.initialize.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_rejects_legacy_session_mode():
    repo = AsyncMock()
    service = FileUploadSessionService(repo)
    sid = uuid.uuid4()
    row = _row(id=sid, status="receiving", upload_mode="server_chunked")
    repo.get_by_id.return_value = row

    with pytest.raises(ValueError, match="direct-S3 upload flow"):
        await service.finalize_direct_upload_session(
            sid,
            FinalizeDirectUploadRequest(success=True),
            request=SimpleNamespace(base_url="http://localhost/"),
            file_manager_service=AsyncMock(),
            app_settings_svc=AsyncMock(),
        )


# ==================== Provider-level presign smoke test ====================


def test_s3_client_generate_presigned_put_url_calls_boto3():
    """Sanity check the new ``S3Client.generate_presigned_put_url`` shim."""
    from app.core.utils.s3_utils import S3Client

    client = object.__new__(S3Client)
    client.bucket_name = "my-bucket"
    fake_boto = MagicMock()
    fake_boto.generate_presigned_url.return_value = "https://signed"
    client.s3_client = fake_boto

    url = client.generate_presigned_put_url(
        file_key="uploads/x.pdf",
        content_type="application/pdf",
        expires_in=600,
    )
    assert url == "https://signed"
    fake_boto.generate_presigned_url.assert_called_once()
    args, kwargs = fake_boto.generate_presigned_url.call_args
    assert args[0] == "put_object"
    assert kwargs["Params"]["Bucket"] == "my-bucket"
    assert kwargs["Params"]["Key"] == "uploads/x.pdf"
    assert kwargs["Params"]["ContentType"] == "application/pdf"
    assert kwargs["ExpiresIn"] == 600
