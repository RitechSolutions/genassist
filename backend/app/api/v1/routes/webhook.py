from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID, uuid4
from app.schemas.webhook import WebhookCreate, WebhookUpdate, WebhookResponse
from app.services.webhook import WebhookService
from app.auth.dependencies import auth
from app.core.utils.webhook_urls import build_public_url
from fastapi_injector import Injected

router = APIRouter(tags=["Webhooks"], dependencies=[Depends(auth)])

@router.get("", response_model=list[WebhookResponse], dependencies=[Depends(auth)])
async def list_webhooks(service: WebhookService = Injected(WebhookService)):
    return await service.get_all_webhooks()


@router.post("", response_model=WebhookResponse)
async def create_webhook(
    data: WebhookCreate,
    request: Request,
    service: WebhookService = Injected(WebhookService),
):
    # Generate webhook ID
    generated_id = uuid4()

    # Execution URL with the tenant as a query parameter, so middleware can detect it
    execution_url = build_public_url(data.base_url, request, generated_id)

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
