"""Helpers for building tenant-scoped object-storage keys."""

import re
from typing import Optional

from app.core.tenant_scope import require_tenant_context

_TENANT_STORAGE_SEGMENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _validated_tenant(tenant_id: Optional[str]) -> str:
    tenant = str(tenant_id if tenant_id is not None else require_tenant_context()).strip()
    if not _TENANT_STORAGE_SEGMENT.fullmatch(tenant):
        raise ValueError("Invalid tenant identifier for object storage.")
    return tenant


def normalize_storage_path(path: Optional[str]) -> str:
    """Normalize an object-storage path without assigning tenant ownership."""
    return (path or "").replace("\\", "/").strip("/")


def tenant_scoped_storage_prefix(path: Optional[str], tenant_id: Optional[str] = None) -> str:
    """Always prefix a new object-storage path with the active tenant."""
    tenant = _validated_tenant(tenant_id)
    normalized_path = normalize_storage_path(path)
    if normalized_path:
        return f"{tenant}/{normalized_path}"
    return tenant


def is_tenant_scoped_storage_path(path: Optional[str], tenant_id: str) -> bool:
    """Return whether an existing path already has the tenant prefix."""
    tenant = _validated_tenant(tenant_id)
    normalized_path = normalize_storage_path(path)
    return normalized_path == tenant or normalized_path.startswith(f"{tenant}/")


def strip_tenant_storage_prefix(path: Optional[str], tenant_id: str) -> str:
    """Return the legacy path represented by a tenant-scoped path."""
    tenant = _validated_tenant(tenant_id)
    normalized_path = normalize_storage_path(path)
    prefix = f"{tenant}/"
    if normalized_path.startswith(prefix):
        return normalized_path[len(prefix) :]
    if normalized_path == tenant:
        return ""
    raise ValueError("Storage path does not have the expected tenant prefix.")
