"""
Zendesk tool node implementation using the BaseNode class.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import HTTPException

from ..base_node import BaseNode
from ..node_result import input_rejection, node_failure
from app.core.utils.email_utils import is_valid_email_address
from app.core.utils.encryption_utils import decrypt_key
from app.modules.integration.zendesk import ZendeskAPIError, ZendeskConnector
from app.modules.workflow.engine.nodes.requester_pii import persist_requester_pii
from app.services.app_settings import AppSettingsService
from app.dependencies.injector import injector
logger = logging.getLogger(__name__)

REQUESTER_FIELD = "requester"
INVALID_REQUESTER_EMAIL = (
    "The requester email is not a valid email address. "
    "Use only an address the user gave, or leave it empty when there is none"
)
REFUSED_REQUESTER = (
    "Zendesk did not accept the requester's contact details. Ask the user for a different email address"
)


def _given_email(value: Any) -> Optional[str]:
    """The email without surrounding spaces, or None when none was given."""
    text = str(value).strip() if value is not None else ""
    return text or None


def _refused_ticket_failure(refusal: ZendeskAPIError) -> Dict[str, Any]:
    """Failure for a ticket Zendesk refused: names the refused field, never its value."""
    requester_refused = refusal.field == REQUESTER_FIELD
    if requester_refused:
        logger.warning("Zendesk tool: Zendesk refused the requester, ticket not created")
        return input_rejection(REFUSED_REQUESTER)
    error_msg = f"Zendesk ticket was not created: {refusal.detail}"
    logger.error(error_msg)
    return node_failure(error_msg, code=refusal.status_code)


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
        requester_email = _given_email(config.get("requester_email"))
        tags = config.get("tags")
        custom_fields = config.get("custom_fields")
        app_settings_id = config.get("app_settings_id")

        if not subject or not description:
            error_msg = "Zendesk tool: Missing required fields: subject or description"
            logger.error(error_msg)
            return node_failure(error_msg, code=400)

        has_unusable_email = requester_email is not None and not is_valid_email_address(requester_email)
        if has_unusable_email:
            logger.warning("Zendesk tool: requester email is not a valid address, ticket not sent")
            return input_rejection(INVALID_REQUESTER_EMAIL)

        try:
            # Get app settings from database
            app_settings_service = injector.get(AppSettingsService)
            app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

            # Extract credentials from app settings values. Zendesk supports two auth
            # methods: legacy API token (email + api_token) and OAuth client
            # credentials (client_id + client_secret). The client secret is stored
            # encrypted, so decrypt it before use.
            values = (
                app_settings.values if isinstance(app_settings.values, dict) else {}
            )
            subdomain = values.get("zendesk_subdomain")
            email = values.get("zendesk_email")
            api_token = values.get("zendesk_api_token")
            auth_method = values.get("zendesk_auth_method")
            client_id = values.get("zendesk_client_id")
            client_secret = values.get("zendesk_client_secret")
            if client_secret:
                client_secret = decrypt_key(client_secret)
            zendesk_connector = ZendeskConnector(
                subdomain=subdomain,
                email=email,
                api_token=api_token,
                auth_method=auth_method,
                client_id=client_id,
                client_secret=client_secret,
            )
            result = await zendesk_connector.submit_ticket(
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

        except ZendeskAPIError as refusal:
            return _refused_ticket_failure(refusal)
        except HTTPException:
            error_msg = "Zendesk ticket was not created: Zendesk could not be reached."
            logger.error(error_msg)
            return node_failure(error_msg, code=502)
        except Exception as e:
            error_msg = f"Error creating Zendesk ticket: {str(e)}"
            logger.error(error_msg)
            return node_failure(error_msg, code=500)

    async def _persist_pii_to_conversation(
        self,
        requester_email: Optional[str],
        requester_name: Optional[str],
    ) -> None:
        """Save the requester's email and name on the conversation for GDPR lookups."""
        await persist_requester_pii(
            self.state, requester_email, requester_name, node_label="Zendesk node"
        )
