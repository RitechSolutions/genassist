"""Migration helpers for legacy, non-tenant-scoped S3 file records."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from botocore.exceptions import ClientError

from app.core.utils.s3_utils import is_s3_not_found_error
from app.core.utils.storage_path import (
    is_tenant_scoped_storage_path,
    normalize_storage_path,
    strip_tenant_storage_prefix,
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
    destination_key: str


@dataclass
class TenantS3PathMigrationResult:
    examined: int = 0
    migrated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    cleanup_candidates: set[S3LegacyCleanupCandidate] = field(default_factory=set)
    legacy_references: set[S3ObjectLocation] = field(default_factory=set)


@dataclass
class S3LegacyCleanupResult:
    examined: int = 0
    deleted: int = 0
    skipped_referenced: int = 0
    skipped_missing: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def _bucket_for_file(file: Any) -> str:
    return str(getattr(file, "storage_path", "") or "").strip()


def _record_current_paths(
    files: list[Any],
    tenant_id: str,
    result: TenantS3PathMigrationResult,
) -> None:
    for file in files:
        bucket = _bucket_for_file(file)
        if not bucket:
            continue
        path = normalize_storage_path(file.path)
        location = S3ObjectLocation(bucket=bucket, key=path)
        if not is_tenant_scoped_storage_path(path, tenant_id):
            result.legacy_references.add(location)
            continue

        legacy_key = strip_tenant_storage_prefix(path, tenant_id)
        if legacy_key:
            result.cleanup_candidates.add(
                S3LegacyCleanupCandidate(
                    source=S3ObjectLocation(bucket=bucket, key=legacy_key),
                    destination_key=path,
                )
            )


async def migrate_tenant_s3_file_paths(
    repository: Any,
    provider_factory: S3ProviderFactory,
    tenant_id: str,
    *,
    dry_run: bool,
) -> TenantS3PathMigrationResult:
    """Copy legacy S3 objects and update file rows for one tenant database."""
    files = await repository.list_files(storage_provider="s3")
    result = TenantS3PathMigrationResult(examined=len(files))
    migrations: dict[tuple[str, str], tuple[str, list[Any]]] = {}

    for file in files:
        bucket = _bucket_for_file(file)
        source = normalize_storage_path(file.path)
        if not bucket:
            result.failed += 1
            result.errors.append(f"S3 file row for {source!r} has no bucket in storage_path.")
            continue
        if is_tenant_scoped_storage_path(source, tenant_id):
            result.skipped += 1
            continue

        destination = tenant_scoped_storage_prefix(source, tenant_id)
        migration_key = (bucket, source)
        if migration_key in migrations:
            migrations[migration_key][1].append(file)
        else:
            migrations[migration_key] = (destination, [file])

    for (bucket, source), (destination, records) in migrations.items():
        if dry_run:
            result.migrated += len(records)
            continue

        try:
            storage_provider = await provider_factory(bucket)
            source_metadata = await storage_provider.head_object(source)
            if await storage_provider.file_exists(destination):
                destination_metadata = await storage_provider.head_object(destination)
            else:
                copied = await storage_provider.copy_file(source, destination)
                if not copied:
                    raise RuntimeError("S3 copy returned false.")
                destination_metadata = await storage_provider.head_object(destination)

            if source_metadata.get("size") != destination_metadata.get("size"):
                raise RuntimeError("copied object size mismatch.")
        except Exception as error:
            result.failed += len(records)
            result.errors.append(f"Failed to migrate s3://{bucket}/{source} to {destination}: {error}")
            continue

        for file in records:
            file.path = destination
        result.migrated += len(records)

    if not dry_run and result.migrated:
        await repository.db.flush()

    _record_current_paths(files, tenant_id, result)
    return result


async def delete_unreferenced_legacy_s3_objects(
    candidates: set[S3LegacyCleanupCandidate],
    legacy_references: set[S3ObjectLocation],
    provider_factory: S3ProviderFactory,
) -> S3LegacyCleanupResult:
    """Delete verified legacy objects that no active S3 file row still references."""
    destinations_by_source: dict[S3ObjectLocation, set[str]] = defaultdict(set)
    for candidate in candidates:
        destinations_by_source[candidate.source].add(candidate.destination_key)

    result = S3LegacyCleanupResult(examined=len(destinations_by_source))
    for source, destination_keys in destinations_by_source.items():
        if source in legacy_references:
            result.skipped_referenced += 1
            continue

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
            for destination_key in destination_keys:
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
