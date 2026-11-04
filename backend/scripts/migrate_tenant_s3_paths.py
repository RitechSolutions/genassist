#!/usr/bin/env python3
"""Move legacy File Manager S3 objects under tenant-scoped keys (tenants/<slug>/...).

Only run it against a bucket that belongs to this one deployment. The script sees only
the file rows in the databases it is connected to, so --delete-legacy deletes an old
object once none of those rows reference it. On a shared bucket, such as a dev bucket
used by several developers' local stacks, that can delete objects another stack still
needs. A staging copy of production data whose AWS_BUCKET_NAME (or --bucket) is the
production bucket would make --apply and --delete-legacy change production objects.
Check AWS_BUCKET_NAME and every --bucket before running. --delete-legacy refuses to run
unless each of those buckets is typed back with --confirm-bucket.

Run it during a maintenance window: rows are read at the start of each tenant and
written at the end, so file changes made by the live app meanwhile could be overwritten.
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Awaitable, Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _all_tenants() -> list[str]:
    from sqlalchemy import select

    from app.core.config.settings import settings
    from app.db.models.tenant import TenantModel
    from app.db.multi_tenant_session import multi_tenant_manager

    if not settings.MULTI_TENANT_ENABLED:
        return ["master"]

    session_factory = multi_tenant_manager.get_tenant_session_factory("master")
    async with session_factory() as session:
        rows = await session.execute(
            select(TenantModel.slug).where(TenantModel.slug != "master").order_by(TenantModel.slug)
        )
        return ["master", *rows.scalars().all()]


async def _scan_key_owners(tenant: str):
    """Read-only pass: which S3 keys this tenant's file rows point at."""
    from app.core.tenant_scope import set_tenant_context
    from app.db.multi_tenant_session import multi_tenant_manager
    from app.repositories.file_manager import FileManagerRepository
    from app.services.s3_tenant_path_migration import collect_s3_key_owners

    set_tenant_context(tenant)
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant)
    async with session_factory() as session:
        files = await FileManagerRepository(session).list_files(storage_provider="s3", include_deleted=True)
        owners = collect_s3_key_owners(files, tenant)
        await session.rollback()
        return owners


async def _migrate_tenant(
    tenant: str,
    provider_factory: Callable[[str], Awaitable[object]],
    *,
    dry_run: bool,
    allowed_buckets: set[str],
    key_owners,
):
    from app.core.tenant_scope import set_tenant_context
    from app.db.multi_tenant_session import multi_tenant_manager
    from app.repositories.file_manager import FileManagerRepository
    from app.services.s3_tenant_path_migration import migrate_tenant_s3_file_paths

    set_tenant_context(tenant)
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant)
    async with session_factory() as session:

        async def commit() -> None:
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        file_repository = FileManagerRepository(session)
        result = await migrate_tenant_s3_file_paths(
            file_repository,
            provider_factory,
            tenant,
            dry_run=dry_run,
            allowed_buckets=allowed_buckets,
            key_owners=key_owners,
            commit=None if dry_run else commit,
        )
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
        return result


async def run(
    scope: str,
    *,
    apply: bool,
    delete_legacy: bool,
    extra_buckets: tuple[str, ...] = (),
    confirm_buckets: tuple[str, ...] = (),
) -> int:
    from app.core.config.settings import file_storage_settings
    from app.db.multi_tenant_session import multi_tenant_manager
    from app.modules.filemanager.providers.s3.provider import S3StorageProvider
    from app.services.s3_tenant_path_migration import (
        S3KeyOwners,
        S3LegacyCleanupCandidate,
        delete_unreferenced_legacy_s3_objects,
    )

    if delete_legacy and not apply:
        raise ValueError("--delete-legacy deletes objects, so it requires --apply.")
    if delete_legacy and scope != "all":
        raise ValueError("--delete-legacy requires scope 'all' to scan every tenant reference.")

    allowed_buckets = {bucket for bucket in (file_storage_settings.AWS_BUCKET_NAME, *extra_buckets) if bucket}
    if not allowed_buckets:
        raise ValueError("No S3 bucket configured; set AWS_BUCKET_NAME or pass --bucket.")
    if delete_legacy and set(confirm_buckets) != allowed_buckets:
        # Cleanup trusts that no other deployment uses these buckets, so the operator types each one back.
        raise ValueError(
            f"--delete-legacy deletes objects in: {', '.join(sorted(allowed_buckets))}. Only run it if "
            "these buckets belong to this deployment alone, and pass --confirm-bucket <name> once "
            "for each of them (no others)."
        )
    logger.info("Allowed buckets: %s", ", ".join(sorted(allowed_buckets)))

    await multi_tenant_manager.initialize()
    all_tenants = await _all_tenants()
    if scope != "all" and scope not in all_tenants:
        raise ValueError(f"Unknown tenant {scope!r}.")
    tenants = all_tenants if scope == "all" else [scope]

    # Every tenant is scanned, even for a single-tenant run, so keys shared between
    # tenants and destinations another tenant already uses are caught.
    key_owners = S3KeyOwners()
    for tenant in all_tenants:
        key_owners.update(await _scan_key_owners(tenant))
    providers: dict[str, S3StorageProvider] = {}
    cleanup_candidates: set[S3LegacyCleanupCandidate] = set()
    references = S3KeyOwners()
    total_examined = 0
    total_migrated = 0
    total_failed = 0
    total_needs_review = 0
    crashed_tenants: list[str] = []

    async def provider_for_bucket(bucket: str) -> S3StorageProvider:
        if bucket not in providers:
            config = file_storage_settings.model_dump()
            config["AWS_BUCKET_NAME"] = bucket
            provider = S3StorageProvider(config=config)
            await provider.initialize()
            providers[bucket] = provider
        return providers[bucket]

    for tenant in tenants:
        try:
            result = await _migrate_tenant(
                tenant,
                provider_for_bucket,
                dry_run=not apply,
                allowed_buckets=allowed_buckets,
                key_owners=key_owners,
            )
        except Exception:
            logger.exception("Tenant %s: migration aborted", tenant)
            crashed_tenants.append(tenant)
            total_failed += 1
            continue
        total_examined += result.examined
        total_migrated += result.migrated
        total_failed += result.failed
        total_needs_review += len(result.needs_review)
        if result.aborted:
            crashed_tenants.append(tenant)
        cleanup_candidates.update(result.cleanup_candidates)
        references.update(result.references)
        logger.info(
            "Tenant %s: examined=%s migrated=%s already_scoped=%s pending_upload=%s needs_review=%s failed=%s",
            tenant,
            result.examined,
            result.migrated,
            result.skipped,
            result.skipped_pending,
            len(result.needs_review),
            result.failed,
        )
        for error in result.errors:
            logger.error("Tenant %s: %s", tenant, error)
        for item in result.needs_review:
            logger.warning("Tenant %s: %s", tenant, item)

    if delete_legacy and crashed_tenants:
        # Without every tenant's references, cleanup could delete an object still in use.
        logger.error("Legacy cleanup skipped: migration aborted for tenant(s) %s.", ", ".join(crashed_tenants))
    elif delete_legacy:
        cleanup = await delete_unreferenced_legacy_s3_objects(
            cleanup_candidates,
            references,
            provider_for_bucket,
        )
        total_failed += cleanup.failed
        logger.info(
            "Legacy cleanup: examined=%s deleted=%s referenced=%s reserved=%s missing=%s failed=%s",
            cleanup.examined,
            cleanup.deleted,
            cleanup.skipped_referenced,
            cleanup.skipped_reserved,
            cleanup.skipped_missing,
            cleanup.failed,
        )
        for error in cleanup.errors:
            logger.error("Legacy cleanup: %s", error)

    mode = "applied" if apply else "dry-run"
    logger.info(
        "Tenant S3 path migration %s: tenants=%s examined=%s migrated=%s needs_review=%s failed=%s",
        mode,
        len(tenants),
        total_examined,
        total_migrated,
        total_needs_review,
        total_failed,
    )
    if total_failed:
        return 1
    # Rows were left for a person to decide, so the migration is not complete yet.
    return 2 if total_needs_review else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.epilog = "Exit codes: 0 done, 1 errors, 2 some rows need review (see the warnings)."
    parser.add_argument("scope", help="Tenant slug, 'master', or 'all'.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy objects and update database rows. Without this flag, only report changes.",
    )
    parser.add_argument(
        "--delete-legacy",
        action="store_true",
        help=(
            "Requires 'all --apply'. Delete old objects this migration copied, once no file row "
            "in any tenant (active or soft-deleted) still references them. Can be repeated later. "
            "Only rows in the connected databases are checked, so never use it on a bucket "
            "another deployment or developer stack also uses. Needs --confirm-bucket."
        ),
    )
    parser.add_argument(
        "--confirm-bucket",
        action="append",
        default=[],
        metavar="BUCKET",
        help=(
            "Required with --delete-legacy, once for each bucket the run uses (AWS_BUCKET_NAME and "
            "every --bucket). Confirms these buckets belong to this deployment alone."
        ),
    )
    parser.add_argument(
        "--bucket",
        action="append",
        default=[],
        help=(
            "Also migrate rows saved in this bucket (repeatable). AWS_BUCKET_NAME is always included. "
            "Only name buckets that belong to this deployment."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(
        asyncio.run(
            run(
                args.scope,
                apply=args.apply,
                delete_legacy=args.delete_legacy,
                extra_buckets=tuple(args.bucket),
                confirm_buckets=tuple(args.confirm_bucket),
            )
        )
    )
