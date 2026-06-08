"""
Zendesk tool node implementation using the BaseNode class.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from ..base_node import BaseNode
from app.modules.integration.zendesk import ZendeskConnector
from app.services.app_settings import AppSettingsService
from app.dependencies.injector import injector
logger = logging.getLogger(__name__)


class ZendeskToolNode(BaseNode):
    """
    Processor for creating a Zendesk ticket via the REST API using the BaseNode approach.
    Reads credentials from settings, only subject/description are required in input_data.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Zendesk ticket creation.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with Zendesk API response
        """

        # Validate required fields
        subject = config.get("subject")
        description = config.get("description")
        requester_name = config.get("requester_name")
        requester_email = config.get("requester_email")
        tags = config.get("tags")
        custom_fields = config.get("custom_fields")
        app_settings_id = config.get("app_settings_id")

        if not subject or not description:
            error_msg = "Zendesk tool: Missing required fields: subject or description"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        try:
            # Get app settings from database
            app_settings_service = injector.get(AppSettingsService)
            app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

            # Extract subdomain, email, and api_token from app settings values
            values = (
                app_settings.values if isinstance(app_settings.values, dict) else {}
            )
            subdomain = str(values.get("zendesk_subdomain"))
            email = str(values.get("zendesk_email"))
            api_token = str(values.get("zendesk_api_token"))
            zendesk_connector = ZendeskConnector(
                subdomain=subdomain, email=email, api_token=api_token)
            # Create the Zendesk ticket
            result = await zendesk_connector.create_ticket(
                subject=subject,
                description=description,
                requester_name=requester_name,
                requester_email=requester_email,
                tags=tags,
                custom_fields=custom_fields,
            )

            await self._persist_pii_to_conversation(
                requester_email=requester_email,
                requester_name=requester_name,
            )

            return result

        except Exception as e:
            error_msg = f"Error creating Zendesk ticket: {str(e)}"
            logger.error(error_msg)
            return {"status": 500, "data": {"error": error_msg}}

    async def _persist_pii_to_conversation(
        self,
        requester_email: Optional[str],
        requester_name: Optional[str],
    ) -> None:
        """Persist PII captured by the Zendesk node into the active conversation's
        ``custom_attributes.pii`` payload so that admins can later locate the
        conversation by email and fulfil GDPR Right-to-Erasure requests.

        This method is intentionally defensive: any failure here is logged and
        swallowed because Zendesk ticket creation has already succeeded and must
        not be undone by an unrelated persistence error (legacy-safe behavior).
        """

        if not requester_email and not requester_name:
            return

        try:
            from app.repositories.conversations import ConversationRepository

            thread_id = getattr(self.state, "thread_id", None)
            if not thread_id:
                return

            try:
                conversation_uuid = UUID(str(thread_id))
            except (ValueError, TypeError):
                return

            conversation_repo = injector.get(ConversationRepository)
            conversation = await conversation_repo.fetch_conversation_by_id(
                conversation_uuid
            )
            if conversation is None:
                return

            existing_attrs = dict(conversation.custom_attributes or {})
            existing_pii = dict(existing_attrs.get("pii") or {})
            if requester_email:
                existing_pii["requester_email"] = str(requester_email).strip().lower()
            if requester_name:
                existing_pii["requester_name"] = str(requester_name).strip()
            existing_attrs["pii"] = existing_pii

            await conversation_repo.update_custom_attributes(
                conversation_uuid, existing_attrs
            )
        except Exception as exc:
            logger.warning(
                "Zendesk node: failed to persist PII to conversation custom_attributes: %s",
                exc,
            )
