"""UUID coercion helpers for values arriving from untrusted or loosely-typed sources"""

from typing import Any, Optional
from uuid import UUID


def coerce_uuid(value: Any) -> Optional[UUID]:
    """Return ``value`` as a UUID, or None when it isn't one"""
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None
