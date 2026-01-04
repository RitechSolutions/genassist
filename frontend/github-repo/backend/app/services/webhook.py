import uuid
from datetime import datetime
from fastapi import Request, HTTPException
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)
from uuid import UUID
from app.core.tenant_scope import get_tenant_context
from app.core.utils.indentifiers import get_customer_id
from app.db.models.webhook import WebhookModel
from app.modules.integration.slack import SlackConnector, verify_slack_request
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.conversation_transcript import (
    InProgConvTranscrUpdate,
    TranscriptSegmentInput,
)
from app.schemas.webhook import WebhookCreate, WebhookUpdate, WebhookBase
from injector import inject
from app.core.utils.encryption_utils import decrypt_key, encrypt_key
from typing import Optional
import logging
import json

from app.modules.integration.whatsapp import WhatsAppConnector

from app.schemas.dynamic_form_schemas import (
    get_encrypted_fields_for_type,
)

from app.use_cases.chat_as_client_use_case import (
    get_or_create_conversation,
    process_conversation_update_with_agent,
)


logger = logging.getLogger(__name__)


@inject
class WebhookService:
    """Service for managing webhooks."""

    def __init__(self, repo: WebhookRepository):
        self.repo = repo

    async def create_webhook(
        self, data: WebhookCreate, webhook_url: str, webhook_id: Optional[UUID] = None
    ):
        """Create a new webhook."""
        if data.secret:
            data.secret = encrypt_key(data.secret)

        # Create WebhookBase with auto-generated URL

        webhook_data = WebhookBase(
            name=data.name,
            url=webhook_url,
            method=data.method,
            headers=data.headers,
            secret=data.secret,
            description=data.description,
            is_active=data.is_active,
            webhook_type=data.webhook_type,
            agent_id=data.agent_id,
            app_settings_id=data.app_settings_id,
        )

        return await self.repo.create(webhook_data, webhook_id)

    async def get_webhook_by_id(
        self, webhook_id: UUID, decrypt_sensitive: Optional[bool] = False
    ):
        data = await self.repo.get_by_id(webhook_id)
        if data and decrypt_sensitive:
            if data.secret:
                data.secret = decrypt_key(str(data.secret))
        return data

    async def get_webhook_by_id_full(self, webhook_id: UUID):
        data = await self.repo.get_by_id_full(webhook_id)
        return data

    async def get_all_webhooks(self):
        webhooks = await self.repo.get_all()
        return webhooks

    async def update_webhook(self, webhook_id: UUID, data: WebhookUpdate):
        webhook = await self.repo.get_by_id(webhook_id)

        if data.secret and data.secret != webhook.secret:
            data.secret = encrypt_key(data.secret)

        data = await self.repo.update(webhook_id, data)
        return data

    async def delete_webhook(self, webhook_id: UUID) -> bool:
        return await self.repo.delete(webhook_id)

    async def validate_webhook_request_and_execute(
        self,
        webhook_id: UUID,
        request: Request,
        payload: str,
        tenant_id: Optional[str] = None,
        hub_mode: Optional[str] = None,
        hub_verify_token: Optional[str] = None,
        hub_challenge: Optional[str] = None,
        x_slack_signature: Optional[str] = None,
        x_slack_request_timestamp: Optional[str] = None,
    ):
        # Lookup webhook by ID
        webhook = await self.get_webhook_by_id_full(webhook_id)

        if not webhook:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Webhook not found"
            )

        # Route to type-specific handler
        webhook_type = webhook.webhook_type or "generic"

        if webhook_type == "slack":
            return await self._handle_slack_webhook(
                webhook,
                request,
                payload,
                tenant_id,
                x_slack_signature,
                x_slack_request_timestamp,
            )
        elif webhook_type == "whatsapp":
            return await self._handle_whatsapp_webhook(
                webhook,
                request,
                payload,
                tenant_id,
                hub_mode,
                hub_verify_token,
                hub_challenge,
            )
        else:
            return await self._handle_generic_webhook(
                webhook, request, payload, tenant_id
            )

    async def _handle_generic_webhook(
        self,
        webhook: WebhookModel,
        request: Request,
        payload: str,
        tenant_id: Optional[str],
    ):
        """Handle generic webhook execution."""

        agent = webhook.agent

        # Validate HTTP method
        if webhook.method != request.method:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST, detail="Invalid HTTP method"
            )

        # Validate secret, if defined
        if webhook.secret:
            decrypted_secret = (
                decrypt_key(str(webhook.secret)) if str(webhook.secret) else None
            )
            auth_header = request.headers.get("authorization")
            expected = f"Bearer {decrypted_secret}"
            if not auth_header or auth_header != expected:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing authorization token",
                )

        # Validate headers
        if webhook.headers:
            for key, expected_value in webhook.headers.items():
                actual_value = request.headers.get(key)
                if actual_value != expected_value:
                    raise HTTPException(
                        status_code=HTTP_400_BAD_REQUEST,
                        detail=f"Header mismatch for '{key}': expected '{expected_value}', got '{actual_value}'",
                    )

        if not agent:
            raise HTTPException(
                status_code=400, detail="Agent ID not configured for webhook"
            )

        # Parse JSON body
        json_body = {}
        try:
            json_body = json.loads(payload)
        except Exception as e:
            logger.error(f"JSON parse error: {e}")
            # If payload is not JSON, treat it as plain text
            json_body = {"message": payload, "text": payload, "body": payload}

        # Extract message text from common fields
        user_message = (
            json_body.get("message")
            or json_body.get("text")
            or json_body.get("body")
            or json_body.get("content")
            or payload
        )

        if not user_message or not str(user_message).strip():
            return {"ok": True}

        # Extract customer identifier from payload or use webhook ID
        customer_identifier = (
            json_body.get("user_id")
            or json_body.get("customer_id")
            or json_body.get("from")
            or json_body.get("sender")
            or str(webhook.id)
        )

        customer_id = uuid.UUID(get_customer_id(str(customer_identifier)))

        conversation = await get_or_create_conversation(
            customer_id=customer_id,
            operator_id=agent.operator_id,
        )

        model = InProgConvTranscrUpdate(
            messages=[
                TranscriptSegmentInput(
                    text=str(user_message),
                    speaker="user",
                    start_time=0,
                    end_time=0,
                    create_time=datetime.now(),
                )
            ],
        )
        tenant_id = tenant_id or get_tenant_context() or "master"

        response = await process_conversation_update_with_agent(
            conversation_id=UUID(str(conversation.id)),
            model=model,
            tenant_id=tenant_id,
            current_user_id=agent.operator.user_id,
        )
        message = (
            response.messages[-1].text
            if response.messages
            else "Hm, smth went wrong on processing your request"
        )

        return {"ok": True, "message": message}

    async def _handle_slack_webhook(
        self,
        webhook: WebhookModel,
        request: Request,
        payload: str,
        tenant_id: Optional[str],
        x_slack_signature: Optional[str],
        x_slack_request_timestamp: Optional[str],
    ):
        """Handle Slack webhook execution."""

        app_settings = webhook.app_settings
        agent = webhook.agent
        # Handle Slack retry
        if request.headers.get("X-Slack-Retry-Num"):
            return {"ok": True}

        # Parse JSON body
        json_body = {}
        try:
            json_body = json.loads(payload)
            if json_body.get("type") == "url_verification":
                return json_body["challenge"]
        except Exception as e:
            logger.error(f"JSON parse error: {e}")

        if not app_settings:
            raise HTTPException(
                status_code=500,
                detail="Slack signing secret not configured in app settings",
            )

        app_settings_values = (
            app_settings.values if isinstance(app_settings.values, dict) else {}
        )
        if (
            not app_settings_values
            or not app_settings_values.get("slack_signing_secret")
            or not app_settings_values.get("slack_bot_token")
        ):
            raise HTTPException(
                status_code=500,
                detail="Slack parameters incorrect or not set! Integrations->variables",
            )
        slack_signing_secret = str(app_settings_values.get("slack_signing_secret", ""))
        slack_bot_token = str(app_settings_values.get("slack_bot_token", ""))

        if not verify_slack_request(
            payload, x_slack_signature, x_slack_request_timestamp, slack_signing_secret
        ):
            raise HTTPException(status_code=403, detail="Invalid request signature")

        # Extract event data
        event = json_body.get("event", {})
        text = event.get("text") or ""
        bot_id = event.get("bot_id")
        channel_id = event.get("channel")

        if not text.strip():
            return {"ok": True}
        if bot_id:
            return {"ok": True}

        customer_id = uuid.UUID(get_customer_id(channel_id))

        conversation = await get_or_create_conversation(
            customer_id=customer_id,
            operator_id=agent.operator_id,
        )

        model = InProgConvTranscrUpdate(
            messages=[
                TranscriptSegmentInput(
                    text=text,
                    speaker="user",
                    start_time=0,
                    end_time=0,
                )
            ],
        )
        tenant_id = tenant_id or get_tenant_context() or "master"

        response = await process_conversation_update_with_agent(
            conversation_id=UUID(str(conversation.id)),
            model=model,
            tenant_id=tenant_id,
            current_user_id=agent.operator.user_id,
        )
        message = (
            response.messages[-1].text
            if response.messages
            else "Hm, smth went wrong on processing your request"
        )

        slack_connector = SlackConnector(token=slack_bot_token, channel=channel_id)
        await slack_connector.sanitize_channel()

        _ = await slack_connector.send_slack_message(text=message)

        return {"ok": True}

    async def _handle_whatsapp_webhook(
        self,
        webhook: WebhookModel,
        request: Request,
        payload: str,
        tenant_id: Optional[str],
        hub_mode: Optional[str],
        hub_verify_token: Optional[str],
        hub_challenge: Optional[str],
    ):
        """Handle WhatsApp webhook execution."""

        app_settings = webhook.app_settings
        agent = webhook.agent

        # Handle WhatsApp verification (GET/POST request)
        if hub_mode == "subscribe":
            if not app_settings:
                raise HTTPException(
                    status_code=500,
                    detail="WhatsApp token not configured in app settings",
                )

            app_settings_values = (
                app_settings.values if isinstance(app_settings.values, dict) else {}
            )
            if not app_settings_values:
                raise HTTPException(
                    status_code=500,
                    detail="WhatsApp parameters incorrect or not set! Integrations->variables",
                )

            verify_token = str(app_settings_values.get("whatsapp_token", ""))
            if verify_token:
                encrypted_fields = get_encrypted_fields_for_type("WhatsApp")
                if "whatsapp_token" in encrypted_fields:
                    verify_token = decrypt_key(verify_token)

            if hub_verify_token == verify_token:
                logger.info("WhatsApp token verified successfully!")
                return int(hub_challenge) if hub_challenge else 200

        # Parse JSON body
        json_body = {}
        try:
            json_body = json.loads(payload)
        except Exception as e:
            logger.error(f"JSON parse error: {e}")

        # Parse WhatsApp message
        entry = json_body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return {"ok": True}

        message_data = messages[0]
        user_phone = message_data.get("from")
        text_data = message_data.get("text", {})
        user_message = text_data.get("body", "")

        if not user_message.strip() or not user_phone:
            return {"ok": True}

        if not app_settings:
            raise HTTPException(
                status_code=500,
                detail="WhatsApp token not configured in app settings",
            )

        app_settings_values = (
            app_settings.values if isinstance(app_settings.values, dict) else {}
        )
        if not app_settings_values:
            raise HTTPException(
                status_code=500,
                detail="WhatsApp parameters incorrect or not set! Integrations->variables",
            )

        if not agent:
            raise HTTPException(
                status_code=400, detail="Agent ID not configured for webhook"
            )

        customer_id = uuid.UUID(get_customer_id(user_phone))

        conversation = await get_or_create_conversation(
            customer_id=customer_id,
            operator_id=agent.operator_id,
        )

        model = InProgConvTranscrUpdate(
            messages=[
                TranscriptSegmentInput(
                    text=user_message,
                    speaker="user",
                    start_time=0,
                    end_time=0,
                    create_time=datetime.now(),
                )
            ],
        )
        tenant_id = tenant_id or get_tenant_context() or "master"

        response = await process_conversation_update_with_agent(
            conversation_id=UUID(str(conversation.id)),
            model=model,
            tenant_id=tenant_id,
            current_user_id=agent.operator.user_id,
        )
        message = (
            response.messages[-1].text
            if response.messages
            else "Hm, smth went wrong on processing your request"
        )

        whatsapp_token = str(app_settings_values.get("whatsapp_token", ""))
        if whatsapp_token:

            encrypted_fields = get_encrypted_fields_for_type("WhatsApp")
            if "whatsapp_token" in encrypted_fields:
                whatsapp_token = decrypt_key(whatsapp_token)

        phone_number_id = str(app_settings_values.get("phone_number_id", ""))
        if not phone_number_id:
            # Try to extract from webhook payload
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")

        if not whatsapp_token or not phone_number_id:
            logger.error("WhatsApp token or phone_number_id not configured")
            return {"ok": True}

        whatsapp_connector = WhatsAppConnector(
            token=whatsapp_token, phone_number_id=phone_number_id
        )
        await whatsapp_connector.send_text_message(
            recipient_number=user_phone, text=message
        )

        return {"ok": True}
