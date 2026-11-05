"""Helpers for building tenant-scoped object-storage keys.

New objects live under a reserved root, ``tenants/<slug>/...``. Keys written before
tenant scoping sit at the top level of the bucket, so keeping new keys under their
own root means a tenant slug can never collide with an old folder name.
"""

import re
from typing import Any, Optional

from app.core.tenant_scope import require_tenant_context

TENANT_STORAGE_ROOT = "tenants"

# Set only by the tenant S3 path migration; never accepted from clients (see FileBase).
LEGACY_S3_KEY_METADATA = "legacy_s3_key"
RESERVED_FILE_METADATA_KEYS = frozenset({LEGACY_S3_KEY_METADATA})

_TENANT_STORAGE_SEGMENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _validated_tenant(tenant_id: Optional[str]) -> str:
    tenant = str(tenant_id if tenant_id is not None else require_tenant_context()).strip()
    if not _TENANT_STORAGE_SEGMENT.fullmatch(tenant):
        raise ValueError("Invalid tenant identifier for object storage.")
    return tenant


def normalize_storage_path(path: Optional[str]) -> str:
    """Normalize an object-storage path without assigning tenant ownership."""
    return (path or "").replace("\\", "/").strip("/")


def tenant_storage_root(tenant_id: Optional[str] = None) -> str:
    """Return the key prefix that holds every object of one tenant."""
    return f"{TENANT_STORAGE_ROOT}/{_validated_tenant(tenant_id)}"


def tenant_scoped_storage_prefix(path: Optional[str], tenant_id: Optional[str] = None) -> str:
    """Place a new object-storage path under the tenant's root.

    A folder that already starts with this tenant's own root (e.g. copied from a stored
    file path) is not nested again. Any other folder, including another tenant's root,
    stays inside this tenant's root.
    """
    root = tenant_storage_root(tenant_id)
    normalized_path = normalize_storage_path(path)
    if normalized_path == root or normalized_path.startswith(f"{root}/"):
        normalized_path = normalized_path[len(root) + 1 :]
    return f"{root}/{normalized_path}" if normalized_path else root


def is_tenant_scoped_storage_path(path: Optional[str], tenant_id: Optional[str] = None) -> bool:
    """Return whether a stored S3 key is under this tenant's root.

    S3 keys are exact, so the key is not cleaned up first: '/tenants/a/x' is not scoped.
    """
    root = tenant_storage_root(tenant_id)
    key = path or ""
    return key == root or key.startswith(f"{root}/")


def path_relative_to_tenant_root(path: Optional[str], tenant_id: Optional[str] = None) -> str:
    """Return a stored key without the tenant root, or unchanged when it has none."""
    key = path or ""
    root = f"{tenant_storage_root(tenant_id)}/"
    return key[len(root) :] if key.startswith(root) else key


def strip_reserved_file_metadata(metadata: Any) -> Any:
    """Drop keys that only the system may set from client-supplied file metadata."""
    if not isinstance(metadata, dict):
        return metadata
    return {key: value for key, value in metadata.items() if key not in RESERVED_FILE_METADATA_KEYS}


def is_reserved_storage_path(path: Optional[str]) -> bool:
    """Return whether a key is inside the reserved tenant root (any tenant)."""
    normalized_path = normalize_storage_path(path)
    return normalized_path == TENANT_STORAGE_ROOT or normalized_path.startswith(f"{TENANT_STORAGE_ROOT}/")
