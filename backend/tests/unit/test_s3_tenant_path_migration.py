from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.s3_tenant_path_migration import (
    S3LegacyCleanupCandidate,
    S3ObjectLocation,
    delete_unreferenced_legacy_s3_objects,
    migrate_tenant_s3_file_paths,
)


@pytest.mark.asyncio
async def test_migration_copies_each_legacy_key_once_and_updates_all_records():
    first = SimpleNamespace(path="uploads/shared.csv", storage_path="bucket-a")
    second = SimpleNamespace(path="uploads/shared.csv", storage_path="bucket-a")
    scoped = SimpleNamespace(path="tenant-a/ml_models/model.pkl", storage_path="bucket-a")
    repository = AsyncMock()
    repository.list_files.return_value = [first, second, scoped]
    repository.db = MagicMock(flush=AsyncMock())

    provider = MagicMock()
    provider.head_object = AsyncMock(return_value={"size": 42})
    provider.file_exists = AsyncMock(return_value=False)
    provider.copy_file = AsyncMock(return_value=True)
    provider_factory = AsyncMock(return_value=provider)

    result = await migrate_tenant_s3_file_paths(
        repository,
        provider_factory,
        "tenant-a",
        dry_run=False,
    )

    assert result.examined == 3
    assert result.migrated == 2
    assert result.skipped == 1
    assert result.failed == 0
    assert first.path == "tenant-a/uploads/shared.csv"
    assert second.path == "tenant-a/uploads/shared.csv"
    provider_factory.assert_awaited_once_with("bucket-a")
    provider.copy_file.assert_awaited_once_with(
        "uploads/shared.csv",
        "tenant-a/uploads/shared.csv",
    )
    repository.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_migration_dry_run_does_not_touch_s3_or_database_rows():
    file = SimpleNamespace(path="ml_models/model.pkl", storage_path="bucket-a")
    repository = AsyncMock()
    repository.list_files.return_value = [file]
    repository.db = MagicMock(flush=AsyncMock())
    provider_factory = AsyncMock()

    result = await migrate_tenant_s3_file_paths(
        repository,
        provider_factory,
        "tenant-a",
        dry_run=True,
    )

    assert result.migrated == 1
    assert result.legacy_references == {S3ObjectLocation(bucket="bucket-a", key="ml_models/model.pkl")}
    assert file.path == "ml_models/model.pkl"
    provider_factory.assert_not_awaited()
    repository.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_records_copy_size_mismatch_and_keeps_row_unchanged():
    file = SimpleNamespace(path="uploads/source.csv", storage_path="bucket-a")
    repository = AsyncMock()
    repository.list_files.return_value = [file]
    repository.db = MagicMock(flush=AsyncMock())
    provider = MagicMock()
    provider.file_exists = AsyncMock(return_value=False)
    provider.copy_file = AsyncMock(return_value=True)
    provider.head_object = AsyncMock(side_effect=[{"size": 42}, {"size": 41}])
    provider_factory = AsyncMock(return_value=provider)

    result = await migrate_tenant_s3_file_paths(
        repository,
        provider_factory,
        "tenant-a",
        dry_run=False,
    )

    assert result.failed == 1
    assert result.migrated == 0
    assert "size mismatch" in result.errors[0]
    assert file.path == "uploads/source.csv"
    repository.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_uses_each_file_rows_saved_bucket():
    first = SimpleNamespace(path="uploads/first.csv", storage_path="old-bucket-a")
    second = SimpleNamespace(path="uploads/second.csv", storage_path="old-bucket-b")
    repository = AsyncMock()
    repository.list_files.return_value = [first, second]
    repository.db = MagicMock(flush=AsyncMock())

    first_provider = MagicMock(
        head_object=AsyncMock(return_value={"size": 10}),
        file_exists=AsyncMock(return_value=False),
        copy_file=AsyncMock(return_value=True),
    )
    second_provider = MagicMock(
        head_object=AsyncMock(return_value={"size": 20}),
        file_exists=AsyncMock(return_value=False),
        copy_file=AsyncMock(return_value=True),
    )
    providers = {
        "old-bucket-a": first_provider,
        "old-bucket-b": second_provider,
    }

    async def provider_factory(bucket):
        return providers[bucket]

    result = await migrate_tenant_s3_file_paths(
        repository,
        provider_factory,
        "tenant-a",
        dry_run=False,
    )

    assert result.migrated == 2
    first_provider.copy_file.assert_awaited_once_with("uploads/first.csv", "tenant-a/uploads/first.csv")
    second_provider.copy_file.assert_awaited_once_with("uploads/second.csv", "tenant-a/uploads/second.csv")


@pytest.mark.asyncio
async def test_missing_source_does_not_stop_other_migrations():
    missing = SimpleNamespace(path="uploads/missing.csv", storage_path="bucket-a")
    available = SimpleNamespace(path="uploads/available.csv", storage_path="bucket-a")
    repository = AsyncMock()
    repository.list_files.return_value = [missing, available]
    repository.db = MagicMock(flush=AsyncMock())

    provider = MagicMock()
    provider.head_object = AsyncMock(side_effect=[FileNotFoundError("missing"), {"size": 7}, {"size": 7}])
    provider.file_exists = AsyncMock(return_value=False)
    provider.copy_file = AsyncMock(return_value=True)

    result = await migrate_tenant_s3_file_paths(
        repository,
        AsyncMock(return_value=provider),
        "tenant-a",
        dry_run=False,
    )

    assert result.failed == 1
    assert result.migrated == 1
    assert missing.path == "uploads/missing.csv"
    assert available.path == "tenant-a/uploads/available.csv"
    repository.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_can_run_later_from_existing_scoped_rows():
    file = SimpleNamespace(path="tenant-a/uploads/shared.csv", storage_path="bucket-a")
    repository = AsyncMock()
    repository.list_files.return_value = [file]
    repository.db = MagicMock(flush=AsyncMock())

    migration = await migrate_tenant_s3_file_paths(
        repository,
        AsyncMock(),
        "tenant-a",
        dry_run=True,
    )
    provider = MagicMock()
    provider.head_object = AsyncMock(return_value={"size": 42})
    provider.delete_file = AsyncMock(return_value=True)

    cleanup = await delete_unreferenced_legacy_s3_objects(
        migration.cleanup_candidates,
        migration.legacy_references,
        AsyncMock(return_value=provider),
    )

    assert cleanup.deleted == 1
    provider.delete_file.assert_awaited_once_with("uploads/shared.csv")


@pytest.mark.asyncio
async def test_cleanup_keeps_legacy_object_referenced_by_another_tenant():
    source = S3ObjectLocation(bucket="bucket-a", key="uploads/shared.csv")
    candidates = {
        S3LegacyCleanupCandidate(
            source=source,
            destination_key="tenant-a/uploads/shared.csv",
        )
    }
    provider_factory = AsyncMock()

    cleanup = await delete_unreferenced_legacy_s3_objects(
        candidates,
        {source},
        provider_factory,
    )

    assert cleanup.skipped_referenced == 1
    assert cleanup.deleted == 0
    provider_factory.assert_not_awaited()
