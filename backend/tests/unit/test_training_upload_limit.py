"""The 2 GB Train Data Source upload limit, on every upload path.

Each path is checked just below, exactly at and just above the limit:
single multipart POST (/file-manager/upload), chunked session (create, chunk,
complete) and direct S3 (presign, finalize). Uploads without
purpose="training_data" keep the regular File Manager limit.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.routes import file_manager as file_manager_routes
from app.api.v1.routes import ml_models
from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils import training_upload
from app.schemas.files_upload_direct import FinalizeDirectUploadRequest, PresignDirectUploadCreate
from app.services.file_upload_session import (
    STATUS_AWAITING_CLIENT_UPLOAD,
    STATUS_COMPLETED,
    STATUS_FAILED,
    UPLOAD_MODE_DIRECT_S3,
    FileUploadSessionService,
)

GIB = 1024**3
LIMIT = 2 * GIB
BELOW, AT, ABOVE = LIMIT - 1, LIMIT, LIMIT + 1
TRAINING = "training_data"
REQUEST = SimpleNamespace(base_url="http://localhost/")


def _assert_too_large(exc: AppException) -> None:
    assert exc.status_code == 413
    assert exc.error_key == ErrorKey.ML_TRAINING_UPLOAD_TOO_LARGE
    assert "2 GB" in exc.error_detail


def _session_row(**kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        status="receiving",
        original_filename="sales.parquet",
        content_type=None,
        temp_path="/tmp/sales.part",
        bytes_received=0,
        expected_bytes=None,
        error_message=None,
        result_json=None,
        upload_mode=None,
        upload_purpose=TRAINING,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# -- Limit and message ---------------------------------------------------------

def test_default_training_upload_limit_is_2_gib():
    assert settings.ML_TRAINING_UPLOAD_MAX_BYTES == LIMIT
    assert training_upload.training_upload_max_bytes() == LIMIT


def test_effective_limit_never_exceeds_the_extraction_limit(monkeypatch):
    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_BYTES", GIB)
    assert training_upload.training_upload_max_bytes() == GIB


@pytest.mark.parametrize(
    ("size", "label"),
    [(LIMIT, "2 GB"), (int(2.5 * GIB), "2.5 GB"), (300 * 1024**2, "300 MB"), (512, "512 bytes")],
)
def test_format_bytes(size, label):
    assert training_upload.format_bytes(size) == label


def test_too_large_message_names_both_sizes():
    exc = training_upload.training_upload_too_large(int(2.5 * GIB), LIMIT)
    _assert_too_large(exc)
    assert "2.5 GB" in exc.error_detail


@pytest.mark.asyncio
async def test_limits_endpoint_reports_the_effective_limit(monkeypatch):
    limits = await ml_models.get_training_data_limits()
    assert limits.max_upload_bytes == LIMIT and limits.max_upload_label == "2 GB"
    assert ".parquet" in limits.supported_extensions

    monkeypatch.setattr(settings, "ML_EXTRACT_MAX_BYTES", GIB)
    limits = await ml_models.get_training_data_limits()
    assert limits.max_upload_bytes == GIB and limits.max_upload_label == "1 GB"


# -- Chunked session -------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("size", [BELOW, AT])
async def test_session_create_accepts_up_to_the_limit(size):
    repo = AsyncMock()
    await FileUploadSessionService(repo).create_session(
        "sales.parquet", size, purpose=TRAINING
    )
    persisted = repo.create.call_args.args[0]
    assert persisted.upload_purpose == TRAINING and persisted.expected_bytes == size


@pytest.mark.asyncio
async def test_session_create_rejects_above_the_limit():
    repo = AsyncMock()
    with pytest.raises(AppException) as exc_info:
        await FileUploadSessionService(repo).create_session(
            "sales.parquet", ABOVE, purpose=TRAINING
        )
    _assert_too_large(exc_info.value)
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_uploads_keep_the_regular_limit():
    repo = AsyncMock()
    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        await FileUploadSessionService(repo).create_session("notes.pdf", AT)


@pytest.mark.asyncio
async def test_training_purpose_only_accepts_training_file_types():
    repo = AsyncMock()
    with pytest.raises(AppException) as exc_info:
        await FileUploadSessionService(repo).create_session("notes.pdf", 10, purpose=TRAINING)
    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_FILE_UNSUPPORTED
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(("chunk", "ok"), [(9, True), (10, True), (11, False)])
async def test_session_chunks_are_checked_against_the_limit(monkeypatch, chunk, ok):
    # Ten bytes left before the limit: 9 ends below it, 10 exactly at it, 11 above.
    repo = AsyncMock()
    row = _session_row(bytes_received=LIMIT - 10)
    repo.get_by_id.return_value = row
    append = AsyncMock()
    monkeypatch.setattr("app.services.file_upload_session.append_bytes_to_path", append)
    service = FileUploadSessionService(repo)

    if ok:
        assert await service.append_chunk(row.id, b"x" * chunk, 0) == LIMIT - 10 + chunk
        append.assert_awaited_once()
    else:
        with pytest.raises(AppException) as exc_info:
            await service.append_chunk(row.id, b"x" * chunk, 0)
        _assert_too_large(exc_info.value)
        assert row.status == STATUS_FAILED
        append.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_complete_rejects_above_the_limit():
    repo = AsyncMock()
    row = _session_row(bytes_received=ABOVE, expected_bytes=ABOVE)
    repo.get_by_id.return_value = row
    with pytest.raises(AppException) as exc_info:
        await FileUploadSessionService(repo).complete_session(
            row.id, REQUEST, AsyncMock(), AsyncMock()
        )
    _assert_too_large(exc_info.value)
    assert row.status == STATUS_FAILED


@pytest.mark.asyncio
async def test_session_complete_registers_a_file_at_the_limit(monkeypatch):
    repo = AsyncMock()
    row = _session_row(bytes_received=AT, expected_bytes=AT)
    repo.get_by_id.return_value = row
    monkeypatch.setattr("app.services.file_upload_session.os.path.isfile", lambda _: True)
    monkeypatch.setattr(
        "app.services.file_upload_session.file_storage_settings.FILE_MANAGER_ENABLED", True
    )
    fm = AsyncMock()
    fm.initialize.return_value = SimpleNamespace(name="local", get_base_path=lambda: "/data")
    fm.create_file_from_local_path.return_value = SimpleNamespace(
        id=uuid.uuid4(), path="uploads/x.parquet", storage_provider="s3", storage_path="bucket"
    )
    fm.get_file_source_url.return_value = "http://localhost/source"

    await FileUploadSessionService(repo).complete_session(row.id, REQUEST, fm, AsyncMock())

    assert fm.create_file_from_local_path.await_args.kwargs["max_file_size"] == LIMIT
    assert row.status == STATUS_COMPLETED


# -- Direct S3 -------------------------------------------------------------------

def _s3_file_manager():
    fm = AsyncMock()
    storage = MagicMock()
    storage.name = "s3"
    storage.get_base_path = MagicMock(return_value="bucket")
    storage.generate_presigned_put_url = AsyncMock(return_value="https://bucket.s3/key?sig")
    storage.head_object = AsyncMock()
    storage.delete_file = AsyncMock(return_value=True)
    fm.initialize.return_value = storage
    fm.get_file_source_url = AsyncMock(return_value="http://localhost/source")
    fm.repository = MagicMock()
    fm.repository.create_file = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    fm.repository.get_file_by_id = AsyncMock()
    fm.repository.delete_file = AsyncMock()
    fm.repository.db = MagicMock(commit=AsyncMock(), refresh=AsyncMock())
    return fm, storage


def _settings_svc():
    svc = AsyncMock()
    svc.get_by_type_and_name.return_value = {"values": {"file_manager_provider": "s3"}}
    return svc


def _direct_service(repo):
    service = FileUploadSessionService(repo)
    service._direct_s3_enabled = lambda: True
    service._direct_s3_expires_in = lambda: 600
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [BELOW, AT])
async def test_presign_accepts_up_to_the_limit(size):
    repo = AsyncMock()
    fm, storage = _s3_file_manager()
    await _direct_service(repo).create_direct_upload_session(
        PresignDirectUploadCreate(original_filename="sales.parquet", expected_size=size, purpose=TRAINING),
        REQUEST,
        fm,
        _settings_svc(),
    )
    storage.generate_presigned_put_url.assert_awaited_once()
    assert repo.create.call_args.args[0].upload_purpose == TRAINING


@pytest.mark.asyncio
async def test_presign_rejects_above_the_limit_before_signing():
    repo = AsyncMock()
    fm, storage = _s3_file_manager()
    with pytest.raises(AppException) as exc_info:
        await _direct_service(repo).create_direct_upload_session(
            PresignDirectUploadCreate(original_filename="sales.parquet", expected_size=ABOVE, purpose=TRAINING),
            REQUEST,
            fm,
            _settings_svc(),
        )
    _assert_too_large(exc_info.value)
    storage.generate_presigned_put_url.assert_not_awaited()


def _awaiting_finalize_row(size):
    return _session_row(
        status=STATUS_AWAITING_CLIENT_UPLOAD,
        upload_mode=UPLOAD_MODE_DIRECT_S3,
        expected_bytes=size,
        result_json={
            "object_key": "uploads/key.parquet",
            "file_id": str(uuid.uuid4()),
            "sub_folder": "uploads",
            "unique_filename": "key.parquet",
            "provider_name": "s3",
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [BELOW, AT])
async def test_finalize_accepts_an_object_up_to_the_limit(size):
    repo = AsyncMock()
    row = _awaiting_finalize_row(size)
    repo.get_by_id.return_value = row
    fm, storage = _s3_file_manager()
    storage.head_object.return_value = {"size": size, "etag": "e", "content_type": None}
    fm.repository.get_file_by_id.return_value = SimpleNamespace(
        id=row.result_json["file_id"], name="key.parquet", size=None, mime_type=None, file_metadata={}
    )

    await _direct_service(repo).finalize_direct_upload_session(
        row.id, FinalizeDirectUploadRequest(success=True, etag="e"), REQUEST, fm, _settings_svc()
    )

    assert row.status == STATUS_COMPLETED
    storage.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_rejects_and_deletes_an_object_above_the_limit():
    repo = AsyncMock()
    row = _awaiting_finalize_row(None)
    repo.get_by_id.return_value = row
    fm, storage = _s3_file_manager()
    storage.head_object.return_value = {"size": ABOVE, "etag": "e", "content_type": None}

    with pytest.raises(AppException) as exc_info:
        await _direct_service(repo).finalize_direct_upload_session(
            row.id, FinalizeDirectUploadRequest(success=True, etag="e"), REQUEST, fm, _settings_svc()
        )

    _assert_too_large(exc_info.value)
    storage.delete_file.assert_awaited()


# -- Single multipart POST /file-manager/upload ------------------------------------

def _upload_mocks():
    fm = AsyncMock()
    fm.initialize.return_value = SimpleNamespace(name="local", get_base_path=lambda: "/data")
    fm.create_file.return_value = SimpleNamespace(
        id=uuid.uuid4(), path="uploads/x.parquet", storage_provider="s3", storage_path="bucket"
    )
    fm.get_file_source_url.return_value = "http://localhost/source"
    return fm, AsyncMock()


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [BELOW, AT])
async def test_upload_accepts_a_training_file_up_to_the_limit(size):
    fm, settings_svc = _upload_mocks()
    upload = SimpleNamespace(filename="sales.parquet", size=size)

    result = await file_manager_routes.upload_files(
        REQUEST, [upload], purpose=TRAINING, file_manager_service=fm, app_settings_svc=settings_svc
    )

    assert result[0]["original_filename"] == "sales.parquet"
    assert fm.create_file.await_args.kwargs["max_file_size"] == LIMIT


@pytest.mark.asyncio
async def test_upload_rejects_a_training_file_above_the_limit_before_storing():
    fm, settings_svc = _upload_mocks()
    upload = SimpleNamespace(filename="sales.parquet", size=ABOVE)

    with pytest.raises(AppException) as exc_info:
        await file_manager_routes.upload_files(
            REQUEST, [upload], purpose=TRAINING, file_manager_service=fm, app_settings_svc=settings_svc
        )

    _assert_too_large(exc_info.value)
    fm.create_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_without_purpose_keeps_the_regular_limit():
    fm, settings_svc = _upload_mocks()
    upload = SimpleNamespace(filename="notes.pdf", size=settings.MAX_CONTENT_LENGTH + 1)

    with pytest.raises(AppException) as exc_info:
        await file_manager_routes.upload_files(
            REQUEST, [upload], purpose=None, file_manager_service=fm, app_settings_svc=settings_svc
        )

    assert exc_info.value.error_key == ErrorKey.FILE_SIZE_TOO_LARGE
    fm.create_file.assert_not_awaited()
