from dataclasses import dataclass
from uuid import UUID
from app.schemas.api_key import ApiKeyInternal
from app.schemas.user import UserReadAuth


@dataclass(slots=True)
class SocketPrincipal:
    """Return value of the auth dependency."""

    principal: ApiKeyInternal | UserReadAuth
    user_id: UUID
    permissions: list[str]
    tenant_id: str | None = None  # Tenant identifier for multi-tenant support
