"""Platform Azure DevOps config for internal Help Center (env vars, not App Settings)."""

from __future__ import annotations

from app.core.config.azure_devops_defaults import DEFAULT_WORK_ITEM_TYPE
from app.core.config.settings import settings
from app.modules.integration.azure_devops import AzureDevOpsConnector


def help_center_ado_configured() -> bool:
    return bool(
        (settings.AZURE_DEVOPS_ORGANIZATION_URL or "").strip()
        and (settings.AZURE_DEVOPS_PROJECT or "").strip()
        and (settings.AZURE_DEVOPS_PAT or "").strip()
    )


def get_help_center_ado_connector() -> AzureDevOpsConnector:
    org_url = (settings.AZURE_DEVOPS_ORGANIZATION_URL or "").strip()
    project = (settings.AZURE_DEVOPS_PROJECT or "").strip()
    pat = (settings.AZURE_DEVOPS_PAT or "").strip()
    if not org_url or not project or not pat:
        raise RuntimeError(
            "Help Center Azure DevOps is not configured. Set AZURE_DEVOPS_ORGANIZATION_URL, "
            "AZURE_DEVOPS_PROJECT, and AZURE_DEVOPS_PAT in the deployment environment."
        )
    work_item_type = (settings.AZURE_DEVOPS_WORK_ITEM_TYPE or "").strip() or DEFAULT_WORK_ITEM_TYPE
    return AzureDevOpsConnector(
        organization_url=org_url,
        project=project,
        pat=pat,
        work_item_type=work_item_type,
    )


def get_help_center_default_area_path() -> str | None:
    value = (settings.AZURE_DEVOPS_DEFAULT_AREA_PATH or "").strip()
    return value or None


def get_help_center_public_base_url() -> str:
    return (settings.HELP_CENTER_PUBLIC_BASE_URL or "").strip().rstrip("/")


def get_help_center_webhook_secret() -> str | None:
    value = (settings.AZURE_DEVOPS_WEBHOOK_SECRET or "").strip()
    return value or None
