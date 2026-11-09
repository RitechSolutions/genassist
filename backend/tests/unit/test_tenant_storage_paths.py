import io
from contextvars import Context
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile

from app.core.tenant_scope import TenantContextError, clear_tenant_context, set_tenant_context
from app.core.utils.storage_path import (
    is_reserved_storage_path,
    is_tenant_scoped_storage_path,
    path_relative_to_tenant_root,
    strip_reserved_file_metadata,
    tenant_scoped_storage_prefix,
)
from app.schemas.file import FileBase
from app.services.file_manager import FileManagerService


def test_tenant_scoped_storage_prefix_uses_reserved_tenant_root():
    assert tenant_scoped_storage_prefix("uploads", "tenant-a") == "tenants/tenant-a/uploads"
    assert tenant_scoped_storage_prefix("", "tenant-a") == "tenants/tenant-a"
    # A folder copied from a stored path is not nested twice...
    assert tenant_scoped_storage_prefix("tenants/tenant-a/uploads", "tenant-a") == "tenants/tenant-a/uploads"
    assert tenant_scoped_storage_prefix("/tenants/tenant-a", "tenant-a") == "tenants/tenant-a"
    # ...but another tenant's root always stays inside this tenant's root.
    assert (
        tenant_scoped_storage_prefix("tenants/tenant-b/uploads", "tenant-a")
        == "tenants/tenant-a/tenants/tenant-b/uploads"
    )
    assert tenant_scoped_storage_prefix("tenants/tenant-ab", "tenant-a") == "tenants/tenant-a/tenants/tenant-ab"


def test_tenant_name_matching_legacy_folder_cannot_reach_legacy_keys():
    # A tenant called "uploads" must never write to the old top-level "uploads/" folder.
    assert tenant_scoped_storage_prefix("", "uploads") == "tenants/uploads"
    assert tenant_scoped_storage_prefix("uploads", "uploads") == "tenants/uploads/uploads"


def test_scoped_path_helpers():
    assert is_tenant_scoped_storage_path("tenants/tenant-a/uploads/x.csv", "tenant-a")
    assert not is_tenant_scoped_storage_path("tenant-a/uploads/x.csv", "tenant-a")
    assert not is_tenant_scoped_storage_path("tenants/tenant-ab/x.csv", "tenant-a")
    # S3 keys are exact: a leading slash or backslashes are not the tenant root.
    assert not is_tenant_scoped_storage_path("/tenants/tenant-a/x.csv", "tenant-a")
    assert not is_tenant_scoped_storage_path("tenants\\tenant-a\\x.csv", "tenant-a")
    assert path_relative_to_tenant_root("tenants/tenant-a/ml_models/x.pkl", "tenant-a") == "ml_models/x.pkl"
    assert path_relative_to_tenant_root("ml_models/x.pkl", "tenant-a") == "ml_models/x.pkl"


def test_clients_cannot_set_the_migration_legacy_key():
    assert strip_reserved_file_metadata({"legacy_s3_key": "x", "a": 1}) == {"a": 1}
    base = FileBase(
        name="x.csv",
        path="uploads",
        storage_path="bucket",
        file_metadata='{"legacy_s3_key": "victim.csv", "note": "hi"}',
    )
    assert base.file_metadata == {"note": "hi"}
    assert is_reserved_storage_path("tenants/other/x.csv")
    assert not is_reserved_storage_path("tenantsx/x.csv")


def test_tenant_scoped_storage_prefix_requires_explicit_context():
    with pytest.raises(TenantContextError, match="No tenant context"):
        Context().run(tenant_scoped_storage_prefix, "uploads")


def test_tenant_scoped_storage_prefix_rejects_invalid_tenant():
    with pytest.raises(ValueError, match="Invalid tenant identifier"):
        tenant_scoped_storage_prefix("uploads", "../tenant-a")

    with pytest.raises(ValueError, match="Invalid tenant identifier"):
        tenant_scoped_storage_prefix("uploads", "tenant_name")


@pytest.mark.asyncio
async def test_s3_file_upload_uses_tenant_scoped_key():
    repository = AsyncMock()
    repository.create_file.side_effect = lambda file_data: file_data
    provider = MagicMock()
    provider.name = "s3"
    provider.is_initialized.return_value = True
    provider.get_base_path.return_value = "shared-bucket"
    provider.upload_file_from_local_path = AsyncMock(return_value=True)

    service = FileManagerService(repository)
    service.storage_provider = provider
    upload = UploadFile(filename="model.pkl", file=io.BytesIO(b"model"))

    set_tenant_context("tenant-a")
    try:
        created = await service.create_file(
            upload,
            FileBase(
                name="model.pkl",
                original_filename="model.pkl",
                path="ml_models",
                storage_provider="s3",
                storage_path="shared-bucket",
            ),
            allowed_extensions=["pkl"],
        )
    finally:
        clear_tenant_context()

    assert created.path.startswith("tenants/tenant-a/ml_models/")
    uploaded_key = provider.upload_file_from_local_path.await_args.args[1]
    assert uploaded_key == created.path


@pytest.mark.asyncio
async def test_s3_local_model_registration_uses_tenant_scoped_key(tmp_path):
    repository = AsyncMock()
    repository.create_file.side_effect = lambda file_data: file_data
    provider = MagicMock()
    provider.name = "s3"
    provider.is_initialized.return_value = True
    provider.get_base_path.return_value = "shared-bucket"
    provider.upload_file_from_local_path = AsyncMock(return_value=True)

    service = FileManagerService(repository)
    service.storage_provider = provider
    model_path = tmp_path / "trained.pkl"
    model_path.write_bytes(b"model")

    set_tenant_context("tenant-a")
    try:
        created = await service.create_file_from_local_path(
            str(model_path),
            FileBase(
                name="trained.pkl",
                original_filename="trained.pkl",
                path="ml_models",
                storage_provider="s3",
                storage_path="shared-bucket",
            ),
            original_filename="trained.pkl",
            allowed_extensions=["pkl"],
            delete_source=False,
        )
    finally:
        clear_tenant_context()

    assert created.path.startswith("tenants/tenant-a/ml_models/")
    uploaded_key = provider.upload_file_from_local_path.await_args.args[1]
    assert uploaded_key == created.path
