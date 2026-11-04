"""Migration helpers for legacy, non-tenant-scoped S3 file records.

Legacy objects are copied to ``tenants/<slug>/<old key>`` and the file rows are
repointed. Each migrated row keeps its exact old key in ``file_metadata`` so the
separate cleanup step only ever considers objects this migration copied, and deletes
one only when no file row in any tenant (active or soft-deleted) still references it.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from botocore.exceptions import ClientError

from app.core.utils.s3_utils import is_s3_not_found_error
from app.core.utils.storage_path import (
    LEGACY_S3_KEY_METADATA,
    is_reserved_storage_path,
    is_tenant_scoped_storage_path,
    tenant_scoped_storage_prefix,
)

S3ProviderFactory = Callable[[str], Awaitable[Any]]


@dataclass(frozen=True, order=True)
class S3ObjectLocation:
    bucket: str
    key: str


@dataclass(frozen=True)
class S3LegacyCleanupCandidate:
    source: S3ObjectLocation
    # None when the migrated row was deleted since: there is no copy left to verify.
    destination_key: Optional[str]


@dataclass
class S3KeyOwners:
    """Which tenants have a file row (active or soft-deleted) pointing at each S3 key.

    Keys are matched without their bucket: ``storage_path`` is client-supplied, so a
    row's bucket can't be trusted to tell two rows with the same key apart.
    """

    by_key: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_file(self, file: Any, tenant_id: str) -> None:
        self.by_key[str(file.path or "")].add(tenant_id)

    def update(self, other: "S3KeyOwners") -> None:
        for key, tenants in other.by_key.items():
            self.by_key[key].update(tenants)

    def tenants_for(self, location: S3ObjectLocation) -> set[str]:
        return set(self.by_key.get(location.key, ()))

    def __contains__(self, location: S3ObjectLocation) -> bool:
        return bool(self.tenants_for(location))


def collect_s3_key_owners(files: list[Any], tenant_id: str) -> S3KeyOwners:
    owners = S3KeyOwners()
    for file in files:
        owners.add_file(file, tenant_id)
    return owners


@dataclass
class TenantS3PathMigrationResult:
    examined: int = 0
    migrated: int = 0
    skipped: int = 0
    skipped_pending: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    # Rows left where they are because they need a person to decide (not counted as failed).
    needs_review: list[str] = field(default_factory=list)
    # Set when a commit failed: the remaining rows were not processed.
    aborted: bool = False
    cleanup_candidates: set[S3LegacyCleanupCandidate] = field(default_factory=set)
    references: S3KeyOwners = field(default_factory=S3KeyOwners)


@dataclass
class S3LegacyCleanupResult:
    examined: int = 0
    deleted: int = 0
    skipped_referenced: int = 0
    skipped_reserved: int = 0
    skipped_missing: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _bucket_for_file(file: Any) -> str:
    return str(getattr(file, "storage_path", "") or "").strip()


def _is_deleted(file: Any) -> bool:
    return bool(getattr(file, "is_deleted", 0))


def _metadata(file: Any) -> dict:
    metadata = getattr(file, "file_metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _is_pending_direct_upload(file: Any) -> bool:
    metadata = _metadata(file)
    return bool(metadata.get("direct_upload")) and metadata.get("status") == "pending"


async def _head_or_none(storage_provider: Any, key: str) -> Optional[dict]:
    """HEAD an object; None when it does not exist, any other error is raised."""
    try:
        return await storage_provider.head_object(key)
    except ClientError as error:
        if is_s3_not_found_error(error):
            return None
        raise


async def _remove_unused_copy(storage_provider: Any, key: str, result: TenantS3PathMigrationResult) -> None:
    """Delete a copy this run made but could not use, so a later run can retry the row."""
    try:
        if await storage_provider.delete_file(key):
            return
    except Exception:
        pass
    result.errors.append(f"Could not remove unused copy {key}; remove it before re-running.")


def _legacy_destination_suffix(source: str) -> tuple[Optional[str], Optional[str]]:
    """Return (suffix for the new key, problem). Unusual keys are left for manual review."""
    parts = [part for part in re.split(r"[\\/]+", source) if part not in ("", ".")]
    if not parts:
        return None, "empty S3 key; needs manual review."
    if ".." in parts:
        return None, "S3 key contains '..'; needs manual review."
    suffix = "/".join(parts)
    if is_reserved_storage_path(suffix):
        return None, "S3 key is inside the reserved 'tenants/' root; needs manual review."
    return suffix, None


def _record_current_paths(
    files: list[Any],
    tenant_id: str,
    result: TenantS3PathMigrationResult,
    allowed_buckets: set[str],
) -> None:
    result.references = collect_s3_key_owners(files, tenant_id)
    for file in files:
        bucket = _bucket_for_file(file)
        legacy_key = _metadata(file).get(LEGACY_S3_KEY_METADATA)
        if bucket not in allowed_buckets or not isinstance(legacy_key, str) or not legacy_key:
            continue
        # The row must still sit exactly where the migration put it for this legacy key.
        suffix, problem = _legacy_destination_suffix(legacy_key)
        if problem or file.path != tenant_scoped_storage_prefix(suffix, tenant_id):
            continue
        result.cleanup_candidates.add(
            S3LegacyCleanupCandidate(
                source=S3ObjectLocation(bucket=bucket, key=legacy_key),
                destination_key=None if _is_deleted(file) else file.path,
            )
        )


async def migrate_tenant_s3_file_paths(
    repository: Any,
    provider_factory: S3ProviderFactory,
    tenant_id: str,
    *,
    dry_run: bool,
    allowed_buckets: set[str],
    key_owners: Optional[S3KeyOwners] = None,
    commit: Optional[Callable[[], Awaitable[None]]] = None,
) -> TenantS3PathMigrationResult:
    """Copy legacy S3 objects and update active file rows for one tenant database.

    Only rows in ``allowed_buckets`` (chosen by the operator, since ``storage_path`` is
    client-supplied) are touched. ``key_owners`` should cover the rows of every tenant,
    so keys shared with another tenant and destinations another tenant already uses are
    reported, not copied. Soft-deleted rows and pending direct uploads are not migrated;
    they stay where they are and are recorded as references, so cleanup never deletes
    their objects. Anything left alone for a person to decide goes to ``needs_review``.

    With ``commit``, each repointed group of rows is committed right after its copy, so
    an interrupted run loses at most one copy's row update and can be resumed.
    """
    files = await repository.list_files(storage_provider="s3", include_deleted=True)
    owners = key_owners if key_owners is not None else collect_s3_key_owners(files, tenant_id)
    active_files = [file for file in files if not _is_deleted(file)]
    result = TenantS3PathMigrationResult(examined=len(active_files))
    migrations: dict[tuple[str, str], tuple[str, list[Any]]] = {}

    for file in active_files:
        bucket = _bucket_for_file(file)
        source = str(file.path or "")
        if is_tenant_scoped_storage_path(source, tenant_id):
            result.skipped += 1
            continue
        if not bucket:
            result.needs_review.append(f"S3 file row for {source!r} has no bucket in storage_path.")
            continue
        if bucket not in allowed_buckets:
            result.needs_review.append(
                f"s3://{bucket}/{source}: bucket is not in the allowed buckets (pass --bucket to include it)."
            )
            continue
        if _is_pending_direct_upload(file):
            result.skipped_pending += 1
            result.needs_review.append(f"s3://{bucket}/{source}: direct upload still pending; re-run once it finishes.")
            continue

        suffix, problem = _legacy_destination_suffix(source)
        if problem:
            result.needs_review.append(f"s3://{bucket}/{source}: {problem}")
            continue

        destination = tenant_scoped_storage_prefix(suffix, tenant_id)
        migration_key = (bucket, source)
        if migration_key in migrations:
            migrations[migration_key][1].append(file)
        else:
            migrations[migration_key] = (destination, [file])

    # Different legacy keys (e.g. 'a/x' and '/a/x') can clean up to the same new key.
    sources_by_destination: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (bucket, source), (destination, _records) in migrations.items():
        sources_by_destination[(bucket, destination)].add(source)

    for (bucket, source), (destination, records) in migrations.items():
        location = f"s3://{bucket}/{source}"
        other_tenants = owners.tenants_for(S3ObjectLocation(bucket=bucket, key=source)) - {tenant_id}
        if other_tenants:
            result.needs_review.append(
                f"{location}: key is also used by tenant(s) {', '.join(sorted(other_tenants))}; needs manual review."
            )
            continue
        if len(sources_by_destination[(bucket, destination)]) > 1:
            result.needs_review.append(
                f"{location}: another legacy key also maps to {destination}; needs manual review."
            )
            continue
        if S3ObjectLocation(bucket=bucket, key=destination) in owners:
            result.needs_review.append(f"{location}: destination {destination} is already used by a file row.")
            continue

        copied = False
        try:
            storage_provider = await provider_factory(bucket)
            source_metadata = await _head_or_none(storage_provider, source)
            if source_metadata is None:
                result.needs_review.append(f"{location}: legacy object is missing from S3.")
                continue
            # Never overwrite: an object may have been uploaded there after the owner scan.
            if await _head_or_none(storage_provider, destination) is not None:
                result.needs_review.append(f"{location}: an object already exists at {destination}.")
                continue
            if dry_run:
                result.migrated += len(records)
                continue

            copied = await storage_provider.copy_file(source, destination)
            if not copied:
                raise RuntimeError("S3 copy returned false.")
            destination_metadata = await storage_provider.head_object(destination)
            if source_metadata.get("size") != destination_metadata.get("size"):
                raise RuntimeError("copied object size mismatch.")
        except Exception as error:
            result.failed += len(records)
            result.errors.append(f"Failed to migrate s3://{bucket}/{source} to {destination}: {error}")
            if not dry_run and copied:
                await _remove_unused_copy(storage_provider, destination, result)
            continue

        previous = [(file.path, file.file_metadata) for file in records]
        for file in records:
            file.path = destination
            file.file_metadata = {**_metadata(file), LEGACY_S3_KEY_METADATA: source}
        if commit is not None:
            try:
                await commit()
            except Exception as error:
                # The rows were not saved: put them back, drop the copy, and stop this tenant.
                for file, (path, metadata) in zip(records, previous):
                    file.path, file.file_metadata = path, metadata
                result.failed += len(records)
                result.errors.append(f"Commit failed after copying s3://{bucket}/{source}: {error}")
                await _remove_unused_copy(storage_provider, destination, result)
                result.aborted = True
                break
        result.migrated += len(records)

    if not dry_run and result.migrated and commit is None:
        await repository.db.flush()

    _record_current_paths(files, tenant_id, result, allowed_buckets)
    return result


async def delete_unreferenced_legacy_s3_objects(
    candidates: set[S3LegacyCleanupCandidate],
    references: S3KeyOwners,
    provider_factory: S3ProviderFactory,
) -> S3LegacyCleanupResult:
    """Delete migrated legacy objects that no file row in any tenant references any more.

    ``references`` must cover every S3 file row of every tenant, active and
    soft-deleted, taken after the migration.
    """
    destinations_by_source: dict[S3ObjectLocation, set[Optional[str]]] = defaultdict(set)
    for candidate in candidates:
        destinations_by_source[candidate.source].add(candidate.destination_key)

    result = S3LegacyCleanupResult(examined=len(destinations_by_source))
    for source, destination_keys in sorted(destinations_by_source.items()):
        if is_reserved_storage_path(source.key):
            result.skipped_reserved += 1
            continue
        if source in references:
            result.skipped_referenced += 1
            continue
        destination_keys = {key for key in destination_keys if key is not None}

        try:
            storage_provider = await provider_factory(source.bucket)
            source_metadata = await storage_provider.head_object(source.key)
        except ClientError as error:
            if is_s3_not_found_error(error):
                result.skipped_missing += 1
                continue
            result.failed += 1
            result.errors.append(f"Failed to inspect s3://{source.bucket}/{source.key}: {error}")
            continue
        except Exception as error:
            result.failed += 1
            result.errors.append(f"Failed to inspect s3://{source.bucket}/{source.key}: {error}")
            continue

        try:
            for destination_key in sorted(destination_keys):
                destination_metadata = await storage_provider.head_object(destination_key)
                if source_metadata.get("size") != destination_metadata.get("size"):
                    raise RuntimeError(f"size mismatch with migrated object {destination_key}.")
            if not await storage_provider.delete_file(source.key):
                raise RuntimeError("S3 delete returned false.")
        except Exception as error:
            result.failed += 1
            result.errors.append(f"Failed to delete s3://{source.bucket}/{source.key}: {error}")
            continue

        result.deleted += 1

    return result
