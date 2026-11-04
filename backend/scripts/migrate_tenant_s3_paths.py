#!/usr/bin/env python3
"""Move legacy File Manager S3 objects under tenant-scoped key prefixes."""

import argparse
import asyncio
import logging
import os
import sys
from typing import Awaitable, Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _selected_tenants(scope: str) -> list[str]:
    from sqlalchemy import select

    from app.core.config.settings import settings
    from app.db.models.tenant import TenantModel
    from app.db.multi_tenant_session import multi_tenant_manager

    if scope != "all":
        return [scope]
    if not settings.MULTI_TENANT_ENABLED:
        return ["master"]

    session_factory = multi_tenant_manager.get_tenant_session_factory("master")
    async with session_factory() as session:
        rows = await session.execute(select(TenantModel.slug).order_by(TenantModel.slug))
        return ["master", *rows.scalars().all()]


async def _migrate_tenant(
    tenant: str,
    provider_factory: Callable[[str], Awaitable[object]],
    *,
    dry_run: bool,
):
    from app.core.tenant_scope import set_tenant_context
    from app.db.multi_tenant_session import multi_tenant_manager
    from app.repositories.file_manager import FileManagerRepository
    from app.services.s3_tenant_path_migration import migrate_tenant_s3_file_paths

    set_tenant_context(tenant)
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant)
    async with session_factory() as session:
        file_repository = FileManagerRepository(session)
        result = await migrate_tenant_s3_file_paths(
            file_repository,
            provider_factory,
            tenant,
            dry_run=dry_run,
        )
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
        return result


async def run(scope: str, *, apply: bool, delete_legacy: bool) -> int:
    from app.core.config.settings import file_storage_settings
    from app.db.multi_tenant_session import multi_tenant_manager
    from app.modules.filemanager.providers.s3.provider import S3StorageProvider
    from app.services.s3_tenant_path_migration import (
        S3LegacyCleanupCandidate,
        S3ObjectLocation,
        delete_unreferenced_legacy_s3_objects,
    )

    if delete_legacy and scope != "all":
        raise ValueError("--delete-legacy requires scope 'all' to scan every tenant reference.")

    await multi_tenant_manager.initialize()
    tenants = await _selected_tenants(scope)
    providers: dict[str, S3StorageProvider] = {}
    cleanup_candidates: set[S3LegacyCleanupCandidate] = set()
    legacy_references: set[S3ObjectLocation] = set()
    total_examined = 0
    total_migrated = 0
    total_failed = 0

    async def provider_for_bucket(bucket: str) -> S3StorageProvider:
        if bucket not in providers:
            config = file_storage_settings.model_dump()
            config["AWS_BUCKET_NAME"] = bucket
            provider = S3StorageProvider(config=config)
            await provider.initialize()
            providers[bucket] = provider
        return providers[bucket]

    for tenant in tenants:
        result = await _migrate_tenant(
            tenant,
            provider_for_bucket,
            dry_run=not apply,
        )
        total_examined += result.examined
        total_migrated += result.migrated
        total_failed += result.failed
        cleanup_candidates.update(result.cleanup_candidates)
        legacy_references.update(result.legacy_references)
        logger.info(
            "Tenant %s: examined=%s migrated=%s already_scoped=%s failed=%s",
            tenant,
            result.examined,
            result.migrated,
            result.skipped,
            result.failed,
        )
        for error in result.errors:
            logger.error("Tenant %s: %s", tenant, error)

    if delete_legacy:
        cleanup = await delete_unreferenced_legacy_s3_objects(
            cleanup_candidates,
            legacy_references,
            provider_for_bucket,
        )
        total_failed += cleanup.failed
        logger.info(
            "Legacy cleanup: examined=%s deleted=%s referenced=%s missing=%s failed=%s",
            cleanup.examined,
            cleanup.deleted,
            cleanup.skipped_referenced,
            cleanup.skipped_missing,
            cleanup.failed,
        )
        for error in cleanup.errors:
            logger.error("Legacy cleanup: %s", error)

    mode = "applied" if apply else "dry-run"
    logger.info(
        "Tenant S3 path migration %s: tenants=%s examined=%s migrated=%s",
        mode,
        len(tenants),
        total_examined,
        total_migrated,
    )
    return 1 if total_failed else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
            "With scope 'all', delete verified old unscoped objects no active file row "
            "references. May be run separately after --apply."
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
            )
        )
    )
