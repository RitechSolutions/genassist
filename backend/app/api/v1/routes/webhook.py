from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID, uuid4
from urllib.parse import urlencode
from app.schemas.webhook import WebhookCreate, WebhookUpdate, WebhookResponse
from app.services.webhook import WebhookService
from app.auth.dependencies import auth
from app.core.tenant_scope import get_tenant_context
from app.core.config.settings import settings
from fastapi_injector import Injected

router = APIRouter(tags=["Webhooks"], dependencies=[Depends(auth)])


@router.post("/", response_model=WebhookResponse)
async def create_webhook(
    data: WebhookCreate,
    request: Request,
    service: WebhookService = Injected(WebhookService),
):
    # Generate webhook ID
    generated_id = uuid4()

    # Get tenant from request context
    tenant_id = get_tenant_context()

    # Build the base execution URL

    if data.base_url:
        url = f"{data.base_url}webhook/execute/{str(generated_id)}"
    else:
        url = str(
            request.url_for(
                (
                    "webhook_handler_post"
                    if data.method == "POST"
                    else "webhook_handler_get"
                ),
                webhook_id=str(generated_id),
            )
        )

    # lowercase the tenant header name to make the check case-insensitive
    looking_tenant_header = settings.TENANT_HEADER_NAME.lower()

    # Add tenant ID as query parameter so middleware can detect it
    query_params = {f"{looking_tenant_header}": tenant_id}
    execution_url = f"{url}?{urlencode(query_params)}"

    # Create webhook with auto-generated URL
    return await service.create_webhook(data, execution_url, webhook_id=generated_id)


@router.get(
    "/{webhook_id}", response_model=WebhookResponse, dependencies=[Depends(auth)]
)
async def read_webhook(
    webhook_id: UUID, service: WebhookService = Injected(WebhookService)
):
    webhook = await service.get_webhook_by_id(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@router.get("/", response_model=list[WebhookResponse], dependencies=[Depends(auth)])
async def list_webhooks(service: WebhookService = Injected(WebhookService)):
    return await service.get_all_webhooks()


@router.put(
    "/{webhook_id}", response_model=WebhookResponse, dependencies=[Depends(auth)]
)
async def update_webhook(
    webhook_id: UUID,
    data: WebhookUpdate,
    service: WebhookService = Injected(WebhookService),
):
    webhook = await service.update_webhook(webhook_id, data)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth)],
)
async def delete_webhook(
    webhook_id: UUID, service: WebhookService = Injected(WebhookService)
):
    if not await service.delete_webhook(webhook_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
