import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.services.tenant import TenantService

from app.constants.data_residency import RESIDENCY_REGION_MAP

logger = logging.getLogger(__name__)


def _regions_satisfy_policy(allowed_regions: Optional[List[str]], data_residency: str) -> bool:
    required = RESIDENCY_REGION_MAP.get(data_residency)
    if required is None:
        return True  # unrecognised zone — don't block unknown future zones
    if not allowed_regions:
        return False
    return any(r in required for r in allowed_regions)


async def assert_provider_residency(
    allowed_regions: Optional[List[str]],
    tenant_service: "TenantService",
) -> None:
    """Raise AppException(403) if the provider violates the current tenant's residency policy."""
    from app.core.exceptions.error_messages import ErrorKey
    from app.core.exceptions.exception_classes import AppException

    data_residency = await tenant_service.get_current_tenant_data_residency()
    if not data_residency:
        return

    if not _regions_satisfy_policy(allowed_regions, data_residency):
        from app.core.tenant_scope import get_tenant_context
        logger.warning(
            "Residency violation blocked: tenant=%s policy=%s provider_regions=%s",
            get_tenant_context(), data_residency, allowed_regions,
        )
        raise AppException(
            error_key=ErrorKey.LLM_PROVIDER_RESIDENCY_VIOLATION,
            status_code=403,
        )