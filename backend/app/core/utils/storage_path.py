"""Helpers for building tenant-scoped object-storage keys."""

import re
from typing import Optional

from app.core.tenant_scope import get_tenant_context

_TENANT_STORAGE_SEGMENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,127})$")


def tenant_scoped_storage_prefix(path: Optional[str], tenant_id: Optional[str] = None) -> str:
    """Prefix an object-storage path with the active tenant exactly once."""
    tenant = str(tenant_id if tenant_id is not None else get_tenant_context()).strip()
    if not _TENANT_STORAGE_SEGMENT.fullmatch(tenant):
        raise ValueError("Invalid tenant identifier for object storage.")

    normalized_path = (path or "").replace("\\", "/").strip("/")
    if normalized_path == tenant or normalized_path.startswith(f"{tenant}/"):
        return normalized_path
    if normalized_path:
        return f"{tenant}/{normalized_path}"
    return tenant
