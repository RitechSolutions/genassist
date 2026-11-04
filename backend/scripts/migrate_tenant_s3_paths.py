#!/usr/bin/env python3
"""Move legacy File Manager S3 objects under tenant-scoped key prefixes."""

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CleanupBucket:
    provider: object
    keys: set[str] = field(default_factory=set)


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


async def _migrate_tenant(tenant: str, *, dry_run: bool):
    from app.core.config.settings import file_storage_settings
    from app.core.project_path import DATA_VOLUME
    from app.core.tenant_scope import set_tenant_context
    from app.db.multi_tenant_session import multi_tenant_manager
    from app.repositories.app_settings import AppSettingsRepository
    from app.repositories.file_manager import FileManagerRepository
    from app.services.app_settings import AppSettingsService
    from app.services.file_manager import FileManagerService
    from app.services.s3_tenant_path_migration import migrate_tenant_s3_file_paths

    set_tenant_context(tenant)
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant)
    async with session_factory() as session:
        file_repository = FileManagerRepository(session)
        file_manager = FileManagerService(file_repository)
        app_settings = await AppSettingsService(AppSettingsRepository(session)).get_by_type_and_name(
            "FileManagerSettings",
            "File Manager Settings",
        )
        provider = await file_manager.initialize(
            base_url=(file_storage_settings.APP_URL or "http://localhost:8000").rstrip("/"),
            base_path=str(DATA_VOLUME),
            app_settings=app_settings,
        )
        if provider.name != "s3":
            logger.info("Tenant %s uses %s storage; skipping", tenant, provider.name)
            await session.rollback()
            return None, provider

        result = await migrate_tenant_s3_file_paths(
            file_repository,
            provider,
            tenant,
            dry_run=dry_run,
        )
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
        return result, provider


async def run(scope: str, *, apply: bool, delete_legacy: bool) -> int:
    from app.db.multi_tenant_session import multi_tenant_manager

    if delete_legacy and (not apply or scope != "all"):
        raise ValueError("--delete-legacy requires 'all --apply' to protect shared legacy keys.")

    await multi_tenant_manager.initialize()
    tenants = await _selected_tenants(scope)
    cleanup: dict[str, CleanupBucket] = {}
    total_examined = 0
    total_migrated = 0

    for tenant in tenants:
        result, provider = await _migrate_tenant(tenant, dry_run=not apply)
        if result is None:
            continue
        total_examined += result.examined
        total_migrated += result.migrated
        logger.info(
            "Tenant %s: examined=%s migrated=%s already_scoped=%s",
            tenant,
            result.examined,
            result.migrated,
            result.skipped,
        )
        if apply and delete_legacy and result.legacy_keys:
            bucket = provider.get_base_path()
            cleanup.setdefault(bucket, CleanupBucket(provider=provider)).keys.update(result.legacy_keys)

    if apply and delete_legacy:
        for bucket, pending in cleanup.items():
            for key in sorted(pending.keys):
                if not await pending.provider.delete_file(key):
                    raise RuntimeError(f"Failed to delete legacy S3 object s3://{bucket}/{key}.")
                logger.info("Deleted legacy S3 object s3://%s/%s", bucket, key)

    mode = "applied" if apply else "dry-run"
    logger.info(
        "Tenant S3 path migration %s: tenants=%s examined=%s migrated=%s",
        mode,
        len(tenants),
        total_examined,
        total_migrated,
    )
    return 0


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
        help="After a successful all-tenant apply, delete the old unscoped objects.",
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
