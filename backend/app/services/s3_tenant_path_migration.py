"""Migration helpers for legacy, non-tenant-scoped S3 file records."""

from dataclasses import dataclass, field
from typing import Any

from app.core.utils.storage_path import tenant_scoped_storage_prefix


@dataclass
class TenantS3PathMigrationResult:
    examined: int = 0
    migrated: int = 0
    skipped: int = 0
    legacy_keys: set[str] = field(default_factory=set)


async def migrate_tenant_s3_file_paths(
    repository: Any,
    storage_provider: Any,
    tenant_id: str,
    *,
    dry_run: bool,
) -> TenantS3PathMigrationResult:
    """Copy legacy S3 objects and update file rows for one tenant database."""
    files = await repository.list_files(storage_provider="s3")
    result = TenantS3PathMigrationResult(examined=len(files))
    migrations: dict[str, tuple[str, list[Any]]] = {}

    for file in files:
        destination = tenant_scoped_storage_prefix(file.path, tenant_id)
        if destination == file.path:
            result.skipped += 1
            continue
        if file.path in migrations:
            migrations[file.path][1].append(file)
        else:
            migrations[file.path] = (destination, [file])

    for source, (destination, records) in migrations.items():
        if not dry_run:
            source_metadata = await storage_provider.head_object(source)
            if await storage_provider.file_exists(destination):
                destination_metadata = await storage_provider.head_object(destination)
            else:
                copied = await storage_provider.copy_file(source, destination)
                if not copied:
                    raise RuntimeError(f"Failed to copy S3 object {source} to {destination}.")
                destination_metadata = await storage_provider.head_object(destination)

            if source_metadata.get("size") != destination_metadata.get("size"):
                raise RuntimeError(f"Copied S3 object size mismatch for {source} -> {destination}.")

            for file in records:
                file.path = destination

        result.migrated += len(records)
        result.legacy_keys.add(source)

    if not dry_run and result.migrated:
        await repository.db.flush()

    return result
