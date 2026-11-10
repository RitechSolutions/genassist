from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError

from app.core.utils.storage_path import LEGACY_S3_KEY_METADATA
from app.services.s3_tenant_path_migration import (
    S3KeyOwners,
    S3LegacyCleanupCandidate,
    S3ObjectLocation,
    collect_s3_key_owners,
    delete_unreferenced_legacy_s3_objects,
    migrate_tenant_s3_file_paths,
)

BUCKETS = {"bucket-a", "old-bucket-a", "old-bucket-b"}


class FakeS3:
    """In-memory bucket: key -> size."""

    def __init__(self, objects=None, copy_size_delta=0):
        self.objects = dict(objects or {})
        self.copy_size_delta = copy_size_delta
        self.copy_file = AsyncMock(side_effect=self._copy)
        self.delete_file = AsyncMock(side_effect=self._delete)
        self.head_object = AsyncMock(side_effect=self._head)
        self.file_exists = AsyncMock(side_effect=AssertionError("migration must not call file_exists"))

    async def _head(self, key):
        if key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "HeadObject")
        return {"size": self.objects[key]}

    async def _copy(self, source, destination):
        self.objects[destination] = self.objects[source] + self.copy_size_delta
        return True

    async def _delete(self, key):
        self.objects.pop(key, None)
        return True


def _row(path, bucket="bucket-a", is_deleted=0, file_metadata=None):
    return SimpleNamespace(path=path, storage_path=bucket, is_deleted=is_deleted, file_metadata=file_metadata)


def _repository(rows):
    repository = AsyncMock()
    repository.list_files.return_value = rows
    repository.db = MagicMock(flush=AsyncMock())
    return repository


async def _migrate(rows, tenant="tenant-a", s3=None, dry_run=False, key_owners=None, repository=None):
    s3 = s3 if s3 is not None else FakeS3({row.path: 42 for row in rows})
    result = await migrate_tenant_s3_file_paths(
        repository or _repository(rows),
        AsyncMock(return_value=s3),
        tenant,
        dry_run=dry_run,
        allowed_buckets=BUCKETS,
        key_owners=key_owners,
    )
    return result, s3


# ---------- migration ----------


@pytest.mark.asyncio
async def test_migration_copies_each_legacy_key_once_and_marks_rows():
    first = _row("uploads/shared.csv", file_metadata={"origin": "ui"})
    second = _row("uploads/shared.csv")
    scoped = _row("tenants/tenant-a/ml_models/model.pkl")
    repository = _repository([first, second, scoped])

    result, s3 = await _migrate([first, second, scoped], repository=repository)

    assert (result.examined, result.migrated, result.skipped, result.failed) == (3, 2, 1, 0)
    assert first.path == second.path == "tenants/tenant-a/uploads/shared.csv"
    assert first.file_metadata == {"origin": "ui", LEGACY_S3_KEY_METADATA: "uploads/shared.csv"}
    assert second.file_metadata == {LEGACY_S3_KEY_METADATA: "uploads/shared.csv"}
    s3.copy_file.assert_awaited_once_with("uploads/shared.csv", "tenants/tenant-a/uploads/shared.csv")
    repository.list_files.assert_awaited_once_with(storage_provider="s3", include_deleted=True)
    repository.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_source_key_is_used_exactly_as_stored():
    row = _row("/docs/x.pdf")

    result, s3 = await _migrate([row])

    assert result.migrated == 1
    s3.copy_file.assert_awaited_once_with("/docs/x.pdf", "tenants/tenant-a/docs/x.pdf")
    assert row.file_metadata[LEGACY_S3_KEY_METADATA] == "/docs/x.pdf"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["a/../b/x.csv", "tenants/other/x.csv", "/tenants/tenant-a/x.csv", "/"])
async def test_unusual_keys_are_left_for_manual_review(path):
    row = _row(path)

    result, s3 = await _migrate([row])

    assert result.failed == 0 and result.migrated == 0
    assert "manual review" in result.needs_review[0]
    assert row.path == path
    s3.copy_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_rows_in_buckets_the_operator_did_not_allow_are_not_touched():
    # storage_path comes from the client, so it must not pick the bucket the script works in.
    row = _row("uploads/x.csv", bucket="someone-elses-bucket")
    provider_factory = AsyncMock()

    result = await migrate_tenant_s3_file_paths(
        _repository([row]), provider_factory, "tenant-a", dry_run=False, allowed_buckets=BUCKETS
    )

    assert result.migrated == 0 and "--bucket" in result.needs_review[0]
    provider_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_folder_named_like_tenant_is_still_migrated():
    row = _row("training/x.csv")

    result, _ = await _migrate([row], tenant="training")

    assert result.migrated == 1
    assert row.path == "tenants/training/training/x.csv"


@pytest.mark.asyncio
async def test_key_shared_with_another_tenant_is_not_copied_even_with_a_different_bucket():
    row = _row("uploads/report.pdf")
    owners = S3KeyOwners()
    owners.update(collect_s3_key_owners([row], "tenant-a"))
    owners.update(collect_s3_key_owners([_row("uploads/report.pdf", bucket="fake-bucket")], "tenant-b"))

    result, s3 = await _migrate([row], key_owners=owners)

    assert result.migrated == 0
    assert "tenant-b" in result.needs_review[0]
    s3.copy_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_destination_used_by_another_tenant_is_not_overwritten():
    # Before scoping, tenant beta picked the folder "tenants/acme".
    row = _row("x.csv")
    owners = S3KeyOwners()
    owners.update(collect_s3_key_owners([row], "acme"))
    owners.update(collect_s3_key_owners([_row("tenants/acme/x.csv")], "beta"))

    result, s3 = await _migrate([row], tenant="acme", key_owners=owners)

    assert result.migrated == 0
    assert "already used by a file row" in result.needs_review[0]
    s3.copy_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_object_at_destination_is_never_overwritten():
    row = _row("uploads/report.csv")
    s3 = FakeS3({"uploads/report.csv": 5, "tenants/tenant-a/uploads/report.csv": 9})

    result, _ = await _migrate([row], s3=s3)

    assert result.migrated == 0 and "already exists" in result.needs_review[0]
    assert s3.objects["tenants/tenant-a/uploads/report.csv"] == 9
    s3.copy_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_two_legacy_keys_mapping_to_one_destination_are_both_left_alone():
    plain = _row("uploads/a.pdf")
    slashed = _row("/uploads/a.pdf")

    result, s3 = await _migrate([plain, slashed])

    assert result.migrated == 0 and len(result.needs_review) == 2
    assert (plain.path, slashed.path) == ("uploads/a.pdf", "/uploads/a.pdf")
    s3.copy_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_direct_upload_is_reported_not_failed():
    row = _row("uploads/pending.csv", file_metadata={"direct_upload": True, "status": "pending"})

    result, s3 = await _migrate([row])

    assert (result.skipped_pending, result.failed, result.migrated) == (1, 0, 0)
    assert "pending" in result.needs_review[0]
    assert S3ObjectLocation("bucket-a", "uploads/pending.csv") in result.references
    s3.copy_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_dry_run_checks_sources_but_changes_nothing():
    present = _row("ml_models/model.pkl")
    missing = _row("ml_models/missing.pkl")
    repository = _repository([present, missing])

    result, s3 = await _migrate(
        [present, missing], s3=FakeS3({"ml_models/model.pkl": 5}), dry_run=True, repository=repository
    )

    assert result.migrated == 1 and result.failed == 0
    assert "missing" in result.needs_review[0]
    assert present.path == "ml_models/model.pkl" and present.file_metadata is None
    s3.copy_file.assert_not_awaited()
    repository.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_migration_records_copy_size_mismatch_and_keeps_row_unchanged():
    row = _row("uploads/source.csv")

    result, _ = await _migrate([row], s3=FakeS3({"uploads/source.csv": 42}, copy_size_delta=-1))

    assert result.failed == 1 and result.migrated == 0
    assert "size mismatch" in result.errors[0]
    assert row.path == "uploads/source.csv"


@pytest.mark.asyncio
async def test_migration_uses_each_file_rows_saved_bucket():
    first = _row("uploads/first.csv", bucket="old-bucket-a")
    second = _row("uploads/second.csv", bucket="old-bucket-b")
    stores = {"old-bucket-a": FakeS3({"uploads/first.csv": 1}), "old-bucket-b": FakeS3({"uploads/second.csv": 2})}

    async def provider_factory(bucket):
        return stores[bucket]

    result = await migrate_tenant_s3_file_paths(
        _repository([first, second]), provider_factory, "tenant-a", dry_run=False, allowed_buckets=BUCKETS
    )

    assert result.migrated == 2
    stores["old-bucket-a"].copy_file.assert_awaited_once_with("uploads/first.csv", "tenants/tenant-a/uploads/first.csv")
    stores["old-bucket-b"].copy_file.assert_awaited_once_with(
        "uploads/second.csv", "tenants/tenant-a/uploads/second.csv"
    )


@pytest.mark.asyncio
async def test_missing_source_does_not_stop_other_migrations():
    missing = _row("uploads/missing.csv")
    available = _row("uploads/available.csv")

    result, _ = await _migrate([missing, available], s3=FakeS3({"uploads/available.csv": 7}))

    assert result.failed == 0 and result.migrated == 1 and len(result.needs_review) == 1
    assert missing.path == "uploads/missing.csv"
    assert available.path == "tenants/tenant-a/uploads/available.csv"


@pytest.mark.asyncio
async def test_soft_deleted_rows_are_references_but_not_migrated():
    deleted = _row("uploads/old.csv", is_deleted=1)

    result, s3 = await _migrate([deleted])

    assert result.examined == 0 and result.migrated == 0
    assert deleted.path == "uploads/old.csv"
    assert S3ObjectLocation("bucket-a", "uploads/old.csv") in result.references
    s3.copy_file.assert_not_awaited()


# ---------- cleanup ----------


@pytest.mark.asyncio
async def test_cleanup_only_considers_rows_the_migration_copied():
    migrated = _row("tenants/tenant-a/uploads/shared.csv", file_metadata={LEGACY_S3_KEY_METADATA: "uploads/shared.csv"})
    # Uploaded after scoping: must never make "uploads/other.csv" a candidate.
    new_upload = _row("tenants/tenant-a/uploads/other.csv")
    migration, _ = await _migrate([migrated, new_upload], dry_run=True)
    s3 = FakeS3(
        {
            "uploads/shared.csv": 4,
            "uploads/other.csv": 4,
            "tenants/tenant-a/uploads/shared.csv": 4,
            "tenants/tenant-a/uploads/other.csv": 4,
        }
    )

    cleanup = await delete_unreferenced_legacy_s3_objects(
        migration.cleanup_candidates, migration.references, AsyncMock(return_value=s3)
    )

    assert cleanup.examined == 1 and cleanup.deleted == 1
    s3.delete_file.assert_awaited_once_with("uploads/shared.csv")


@pytest.mark.asyncio
async def test_cleanup_ignores_a_marker_that_does_not_match_the_row_path():
    forged = _row("tenants/tenant-a/uploads/mine.csv", file_metadata={LEGACY_S3_KEY_METADATA: "other/victim.csv"})

    migration, _ = await _migrate([forged], dry_run=True)

    assert migration.cleanup_candidates == set()


@pytest.mark.asyncio
async def test_cleanup_removes_legacy_copy_of_a_migrated_file_deleted_since():
    deleted = _row(
        "tenants/tenant-a/uploads/gone.csv",
        is_deleted=1,
        file_metadata={LEGACY_S3_KEY_METADATA: "uploads/gone.csv"},
    )
    migration, _ = await _migrate([deleted], dry_run=True)
    s3 = FakeS3({"uploads/gone.csv": 3})

    cleanup = await delete_unreferenced_legacy_s3_objects(
        migration.cleanup_candidates, migration.references, AsyncMock(return_value=s3)
    )

    assert cleanup.deleted == 1
    s3.delete_file.assert_awaited_once_with("uploads/gone.csv")


@pytest.mark.asyncio
async def test_cleanup_keeps_object_referenced_by_any_row_of_any_tenant():
    tenant_a, _ = await _migrate(
        [_row("tenants/a/b/reports/q1.csv", file_metadata={LEGACY_S3_KEY_METADATA: "b/reports/q1.csv"})],
        tenant="a",
        dry_run=True,
    )
    # Tenant b's row names no bucket at all; the key still matches, so it protects the object.
    tenant_b, _ = await _migrate([_row("b/reports/q1.csv", bucket="", is_deleted=1)], tenant="b", dry_run=True)
    references = S3KeyOwners()
    references.update(tenant_a.references)
    references.update(tenant_b.references)
    provider_factory = AsyncMock()

    cleanup = await delete_unreferenced_legacy_s3_objects(tenant_a.cleanup_candidates, references, provider_factory)

    assert cleanup.skipped_referenced == 1 and cleanup.deleted == 0
    provider_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_never_deletes_inside_the_reserved_tenant_root():
    candidates = {
        S3LegacyCleanupCandidate(
            source=S3ObjectLocation("bucket-a", "tenants/b/x.csv"),
            destination_key="tenants/a/tenants/b/x.csv",
        )
    }
    provider_factory = AsyncMock()

    cleanup = await delete_unreferenced_legacy_s3_objects(candidates, S3KeyOwners(), provider_factory)

    assert cleanup.skipped_reserved == 1
    provider_factory.assert_not_awaited()


def _load_migration_script():
    import importlib.util
    import pathlib

    script = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "migrate_tenant_s3_paths.py"
    spec = importlib.util.spec_from_file_location("migrate_tenant_s3_paths", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_delete_legacy_requires_apply():
    module = _load_migration_script()

    with pytest.raises(ValueError, match="requires --apply"):
        await module.run("all", apply=False, delete_legacy=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confirm",
    [
        (),
        ("bucket-a",),
        ("bucket-a", "old-bucket-a", "someone-elses-bucket"),
        ("Bucket-A", "old-bucket-a"),
    ],
)
async def test_delete_legacy_requires_every_bucket_confirmed(monkeypatch, confirm):
    from app.core.config.settings import file_storage_settings
    from app.db.multi_tenant_session import multi_tenant_manager

    module = _load_migration_script()
    monkeypatch.setattr(file_storage_settings, "AWS_BUCKET_NAME", "bucket-a")
    initialize = AsyncMock()
    monkeypatch.setattr(multi_tenant_manager, "initialize", initialize)

    with pytest.raises(ValueError, match="--confirm-bucket"):
        await module.run(
            "all",
            apply=True,
            delete_legacy=True,
            extra_buckets=("old-bucket-a",),
            confirm_buckets=confirm,
        )
    # Refused before touching any database or bucket.
    initialize.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_legacy_runs_once_every_bucket_is_confirmed(monkeypatch):
    from app.core.config.settings import file_storage_settings
    from app.db.multi_tenant_session import multi_tenant_manager

    module = _load_migration_script()
    monkeypatch.setattr(file_storage_settings, "AWS_BUCKET_NAME", "bucket-a")
    # Stop right after the guard; reaching initialize means the confirmation was accepted.
    monkeypatch.setattr(multi_tenant_manager, "initialize", AsyncMock(side_effect=RuntimeError("past the guard")))

    with pytest.raises(RuntimeError, match="past the guard"):
        await module.run(
            "all",
            apply=True,
            delete_legacy=True,
            extra_buckets=("old-bucket-a",),
            confirm_buckets=("old-bucket-a", "bucket-a"),
        )


@pytest.mark.asyncio
async def test_each_copied_group_is_committed_right_away():
    first = _row("uploads/a.csv")
    second = _row("uploads/b.csv")
    paths_at_commit = []

    async def commit():
        paths_at_commit.append((first.path, second.path))

    await migrate_tenant_s3_file_paths(
        _repository([first, second]),
        AsyncMock(return_value=FakeS3({"uploads/a.csv": 1, "uploads/b.csv": 2})),
        "tenant-a",
        dry_run=False,
        allowed_buckets=BUCKETS,
        commit=commit,
    )

    assert paths_at_commit == [
        ("tenants/tenant-a/uploads/a.csv", "uploads/b.csv"),
        ("tenants/tenant-a/uploads/a.csv", "tenants/tenant-a/uploads/b.csv"),
    ]


@pytest.mark.asyncio
async def test_cleanup_skips_buckets_not_allowed_in_this_run():
    row = _row(
        "tenants/tenant-a/uploads/x.csv",
        bucket="no-longer-allowed",
        is_deleted=1,
        file_metadata={LEGACY_S3_KEY_METADATA: "uploads/x.csv"},
    )

    migration, _ = await _migrate([row], dry_run=True)

    assert migration.cleanup_candidates == set()


@pytest.mark.asyncio
async def test_scoped_row_without_bucket_is_not_reported_for_review():
    row = _row("tenants/tenant-a/uploads/x.csv", bucket="")

    result, _ = await _migrate([row])

    assert result.skipped == 1 and result.needs_review == []


@pytest.mark.asyncio
async def test_failed_check_after_copy_removes_the_copy_so_a_rerun_can_retry():
    row = _row("uploads/source.csv")
    s3 = FakeS3({"uploads/source.csv": 42}, copy_size_delta=-1)

    result, _ = await _migrate([row], s3=s3)

    assert result.failed == 1
    assert "tenants/tenant-a/uploads/source.csv" not in s3.objects
    assert row.path == "uploads/source.csv"


@pytest.mark.asyncio
async def test_failed_commit_restores_rows_removes_copy_and_stops_the_tenant():
    first = _row("uploads/a.csv")
    second = _row("uploads/b.csv")
    s3 = FakeS3({"uploads/a.csv": 1, "uploads/b.csv": 2})

    result = await migrate_tenant_s3_file_paths(
        _repository([first, second]),
        AsyncMock(return_value=s3),
        "tenant-a",
        dry_run=False,
        allowed_buckets=BUCKETS,
        commit=AsyncMock(side_effect=RuntimeError("connection lost")),
    )

    assert result.aborted and result.failed == 1 and result.migrated == 0
    assert "Commit failed" in result.errors[0]
    assert first.path == "uploads/a.csv" and first.file_metadata is None
    assert second.path == "uploads/b.csv"
    assert "tenants/tenant-a/uploads/a.csv" not in s3.objects
    s3.copy_file.assert_awaited_once()
