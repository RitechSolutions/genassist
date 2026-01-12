"""
Permission synchronization service.

Syncs discovered permissions to the database at application startup.
"""
import logging
from typing import Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.permission import PermissionModel

logger = logging.getLogger(__name__)


async def sync_permissions_to_db(
    session: AsyncSession,
    permissions: Set[str],
    update_existing: bool = False,
    verbose: bool = True
) -> dict:
    """
    Sync permissions to the database.

    This function:
    1. Gets all permissions from the database
    2. Compares with provided permissions
    3. Adds new permissions
    4. Optionally updates existing ones
    5. Logs orphaned permissions (in DB but not in code)

    Args:
        session: Database session
        permissions: Set of permission strings to sync
        update_existing: If True, update descriptions of existing permissions

    Returns:
        Dict with sync statistics
    """
    stats = {
        "total_in_code": len(permissions),
        "total_in_db": 0,
        "added": 0,
        "updated": 0,
        "orphaned": 0
    }

    # Get existing permissions from database
    result = await session.execute(select(PermissionModel))
    existing_perms = {perm.name: perm for perm in result.scalars().all()}
    db_permission_names = set(existing_perms.keys())
    stats["total_in_db"] = len(db_permission_names)

    # Find new permissions to add
    new_permissions = permissions - db_permission_names

    if new_permissions:
        logger.info(f"Adding {len(new_permissions)} new permissions to database")

        for perm_name in sorted(new_permissions):
            # Generate description from permission name
            description = _generate_permission_description(perm_name)

            permission = PermissionModel(
                name=perm_name,
                description=description,
                is_active=True
            )
            session.add(permission)
            stats["added"] += 1
            logger.debug(f"  + {perm_name}: {description}")

        await session.commit()
        logger.info(f"✓ Added {stats['added']} new permissions")
    else:
        logger.info("No new permissions to add")

    # Optional: Update descriptions of existing permissions
    if update_existing:
        logger.info("Checking for permission description updates...")

        for perm_name in permissions & db_permission_names:
            new_desc = _generate_permission_description(perm_name)
            existing_perm = existing_perms[perm_name]

            if existing_perm.description != new_desc:
                existing_perm.description = new_desc
                stats["updated"] += 1
                logger.debug(f"  ↻ {perm_name}: {new_desc}")

        if stats["updated"] > 0:
            await session.commit()
            logger.info(f"✓ Updated {stats['updated']} permission descriptions")

    # Check for orphaned permissions (in DB but not in code)
    orphaned_permissions = db_permission_names - permissions
    stats["orphaned"] = len(orphaned_permissions)

    if orphaned_permissions and verbose:
        logger.warning(
            f"Found {len(orphaned_permissions)} permissions in database but not in code:"
        )
        for orphan in sorted(orphaned_permissions):
            logger.warning(f"  ⚠ {orphan}")
        logger.warning(
            "These permissions may be obsolete. Consider removing them or "
            "adding them to permission constants if still needed."
        )

    # Log detailed summary only if verbose (for master database)
    if verbose:
        logger.info("=" * 60)
        logger.info("Permission Sync Summary:")
        logger.info(f"  Total in code:     {stats['total_in_code']}")
        logger.info(f"  Total in database: {stats['total_in_db']}")
        logger.info(f"  Added:             {stats['added']}")
        logger.info(f"  Updated:           {stats['updated']}")
        logger.info(f"  Orphaned:          {stats['orphaned']}")
        logger.info("=" * 60)

    return stats


def _generate_permission_description(permission_name: str) -> str:
    """
    Generate a human-readable description from a permission name.

    Examples:
        "create:api_key" -> "Allows create api key data"
        "read:llm_provider" -> "Allows read llm provider data"
        "takeover_in_progress_conversation" -> "Allows takeover in progress conversation"

    Args:
        permission_name: Permission string (e.g., "create:api_key")

    Returns:
        Human-readable description
    """
    if ':' in permission_name:
        # Standard format: action:resource
        action, resource = permission_name.split(':', 1)
        resource_readable = resource.replace('_', ' ').replace('-', ' ')
        return f"Allows {action} {resource_readable} data"
    else:
        # Custom format (e.g., "takeover_in_progress_conversation")
        readable = permission_name.replace('_', ' ').replace('-', ' ')
        return f"Allows {readable}"