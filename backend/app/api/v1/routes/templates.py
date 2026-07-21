from typing import List
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.core.tenant_scope import get_tenant_context
from app.schemas.template import (
    TemplateCreateFromAgent,
    TemplateInstallRequest,
    TemplateInstallResponse,
    TemplateListItem,
    TemplateRead,
    TemplateRejectRequest,
)
from app.services.template import TemplateService

router = APIRouter()


async def require_master_scope() -> None:
    """Approval actions run only in the master (control-plane) scope."""
    if get_tenant_context() != "master":
        raise AppException(
            status_code=403, error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE
        )


@router.get(
    "",
    response_model=List[TemplateListItem],
    dependencies=[Depends(auth), Depends(permissions(P.Template.READ))],
)
async def list_templates(
    request: Request,
    service: TemplateService = Injected(TemplateService),
):
    """Gallery listing: official + approved community + the user's own templates."""
    return await service.list_templates(request.state.user.id)


# NOTE: declared before "/{template_id}" so the literal path wins over the UUID param.
@router.get(
    "/review",
    response_model=List[TemplateListItem],
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Template.APPROVE)),
        Depends(require_master_scope),
    ],
)
async def list_review_queue(
    service: TemplateService = Injected(TemplateService),
):
    """Pending publish submissions awaiting master-admin review."""
    return await service.list_pending()


@router.get(
    "/{template_id}",
    response_model=TemplateRead,
    dependencies=[Depends(auth), Depends(permissions(P.Template.READ))],
)
async def get_template(
    template_id: UUID,
    request: Request,
    service: TemplateService = Injected(TemplateService),
):
    return await service.get_template(template_id, request.state.user.id)


@router.post(
    "/{template_id}/install",
    response_model=TemplateInstallResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Template.INSTALL))],
)
async def install_template(
    template_id: UUID,
    request: Request,
    body: TemplateInstallRequest = Body(default=TemplateInstallRequest()),
    service: TemplateService = Injected(TemplateService),
):
    """Instantiate a template into the current tenant as a new agent + workflow."""
    return await service.install(template_id, body.name, request.state.user.id)


@router.post(
    "/{template_id}/publish",
    response_model=TemplateRead,
    dependencies=[Depends(auth), Depends(permissions(P.Template.PUBLISH))],
)
async def publish_template(
    template_id: UUID,
    request: Request,
    service: TemplateService = Injected(TemplateService),
):
    """Submit one of the user's own templates to the global review queue."""
    return await service.publish(template_id, request.state.user.id)


@router.post(
    "/review/{template_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Template.APPROVE)),
        Depends(require_master_scope),
    ],
)
async def approve_template(
    template_id: UUID,
    request: Request,
    service: TemplateService = Injected(TemplateService),
):
    await service.approve(template_id, request.state.user.id)


@router.post(
    "/review/{template_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Template.APPROVE)),
        Depends(require_master_scope),
    ],
)
async def reject_template(
    template_id: UUID,
    request: Request,
    body: TemplateRejectRequest = Body(default=TemplateRejectRequest()),
    service: TemplateService = Injected(TemplateService),
):
    await service.reject(template_id, request.state.user.id, body.reason)


@router.delete(
    "/review/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Template.APPROVE)),
        Depends(require_master_scope),
    ],
)
async def remove_global_template(
    template_id: UUID,
    request: Request,
    service: TemplateService = Injected(TemplateService),
):
    """Master-admin removal of a published/community template from the library."""
    await service.remove_global(template_id, request.state.user.id)


@router.post(
    "/{template_id}/unpublish",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Template.PUBLISH))],
)
async def unpublish_template(
    template_id: UUID,
    request: Request,
    service: TemplateService = Injected(TemplateService),
):
    """Withdraw the caller's published copy of their own template."""
    await service.unpublish(template_id, request.state.user.id)


@router.post(
    "/from-agent",
    response_model=TemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Template.CREATE))],
)
async def create_template_from_agent(
    request: Request,
    data: TemplateCreateFromAgent = Body(...),
    service: TemplateService = Injected(TemplateService),
):
    """Save one of the user's own agents as a private, tenant-local template."""
    return await service.create_from_agent(data, request.state.user.id)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Template.DELETE))],
)
async def delete_template(
    template_id: UUID,
    request: Request,
    service: TemplateService = Injected(TemplateService),
):
    await service.delete_template(template_id, request.state.user.id)
