import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.services.app_settings import AppSettingsService

from app.constants.data_residency import RESIDENCY_REGION_MAP

logger = logging.getLogger(__name__)

_SECURITY_SETTING_TYPE = "Security"
_DATA_RESIDENCY_FIELD = "data_residency"


def bedrock_regions_from_connection_data(
    llm_model_provider: Optional[str],
    connection_data: Optional[dict],
) -> Optional[List[str]]:
    """Return [region] for Bedrock providers, None for all others."""
    if (llm_model_provider or "").lower() != "bedrock":
        return None
    from app.constants.embedding_models import DEFAULT_BEDROCK_REGION
    region = (connection_data or {}).get("region_name") or DEFAULT_BEDROCK_REGION
    return [region]


def _region_in_any_zone(region: str, zones: List[str]) -> bool:
    for zone in zones:
        required = RESIDENCY_REGION_MAP.get(zone)
        if required and region in required:
            return True
    return False


def _regions_satisfy_policy(allowed_regions: Optional[List[str]], zones: List[str]) -> bool:
    if not allowed_regions:
        return True  # provider has no region concept (e.g. OpenAI) — not subject to residency policy
    return any(_region_in_any_zone(r, zones) for r in allowed_regions)


async def get_data_residency_zones(app_settings_service: "AppSettingsService") -> List[str]:
    """Return the configured list of allowed data residency zones, empty if unrestricted."""
    value = await app_settings_service.get_value_by_type_and_field(
        _SECURITY_SETTING_TYPE, _DATA_RESIDENCY_FIELD
    )
    if not value:
        return []
    if isinstance(value, list):
        return [z for z in value if z]
    if isinstance(value, str):
        return [value]  # backwards compat with single-value rows
    return []


async def assert_provider_residency(
    allowed_regions: Optional[List[str]],
    app_settings_service: "AppSettingsService",
) -> None:
    """Raise AppException(403) if the provider violates the configured residency policy."""
    from app.core.exceptions.error_messages import ErrorKey
    from app.core.exceptions.exception_classes import AppException

    zones = await get_data_residency_zones(app_settings_service)
    if not zones:
        return

    if not _regions_satisfy_policy(allowed_regions, zones):
        logger.warning(
            "Residency violation blocked: policy_zones=%s provider_regions=%s",
            zones, allowed_regions,
        )
        raise AppException(
            error_key=ErrorKey.LLM_PROVIDER_RESIDENCY_VIOLATION,
            status_code=403,
        )