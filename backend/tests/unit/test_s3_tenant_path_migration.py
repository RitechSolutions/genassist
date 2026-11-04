from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.s3_tenant_path_migration import migrate_tenant_s3_file_paths


@pytest.mark.asyncio
async def test_migration_copies_each_legacy_key_once_and_updates_all_records():
    first = SimpleNamespace(path="uploads/shared.csv")
    second = SimpleNamespace(path="uploads/shared.csv")
    scoped = SimpleNamespace(path="tenant-a/ml_models/model.pkl")
    repository = AsyncMock()
    repository.list_files.return_value = [first, second, scoped]
    repository.db = MagicMock(flush=AsyncMock())

    provider = MagicMock()
    provider.head_object = AsyncMock(return_value={"size": 42})
    provider.file_exists = AsyncMock(return_value=False)
    provider.copy_file = AsyncMock(return_value=True)

    result = await migrate_tenant_s3_file_paths(
        repository,
        provider,
        "tenant-a",
        dry_run=False,
    )

    assert result.examined == 3
    assert result.migrated == 2
    assert result.skipped == 1
    assert result.legacy_keys == {"uploads/shared.csv"}
    assert first.path == "tenant-a/uploads/shared.csv"
    assert second.path == "tenant-a/uploads/shared.csv"
    provider.copy_file.assert_awaited_once_with(
        "uploads/shared.csv",
        "tenant-a/uploads/shared.csv",
    )
    repository.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_migration_dry_run_does_not_touch_s3_or_database_rows():
    file = SimpleNamespace(path="ml_models/model.pkl")
    repository = AsyncMock()
    repository.list_files.return_value = [file]
    repository.db = MagicMock(flush=AsyncMock())
    provider = MagicMock(
        head_object=AsyncMock(),
        file_exists=AsyncMock(),
        copy_file=AsyncMock(),
    )

    result = await migrate_tenant_s3_file_paths(
        repository,
        provider,
        "tenant-a",
        dry_run=True,
    )

    assert result.migrated == 1
    assert result.legacy_keys == {"ml_models/model.pkl"}
    assert file.path == "ml_models/model.pkl"
    provider.head_object.assert_not_awaited()
    provider.copy_file.assert_not_awaited()
    repository.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_rejects_copy_size_mismatch():
    file = SimpleNamespace(path="uploads/source.csv")
    repository = AsyncMock()
    repository.list_files.return_value = [file]
    repository.db = MagicMock(flush=AsyncMock())
    provider = MagicMock()
    provider.file_exists = AsyncMock(return_value=False)
    provider.copy_file = AsyncMock(return_value=True)
    provider.head_object = AsyncMock(side_effect=[{"size": 42}, {"size": 41}])

    with pytest.raises(RuntimeError, match="size mismatch"):
        await migrate_tenant_s3_file_paths(
            repository,
            provider,
            "tenant-a",
            dry_run=False,
        )

    assert file.path == "uploads/source.csv"
    repository.db.flush.assert_not_awaited()
