"""
Zendesk tool node implementation using the BaseNode class.
"""

import logging
from typing import Dict, Any
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
            return result

        except Exception as e:
            error_msg = f"Error creating Zendesk ticket: {str(e)}"
            logger.error(error_msg)
            return {"status": 500, "data": {"error": error_msg}}
