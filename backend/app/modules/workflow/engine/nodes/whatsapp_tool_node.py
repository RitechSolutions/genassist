"""
WhatsApp tool node implementation using the BaseNode class.
"""

import logging
from typing import Dict, Any, cast
from uuid import UUID

from ..base_node import BaseNode
from app.modules.integration.whatsapp import WhatsAppConnector
from app.services.app_settings import AppSettingsService
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


class WhatsAppToolNode(BaseNode):
    """
    Processor that sends a text message with the WhatsApp Cloud API using the BaseNode approach.

    Expected input format:
    {
        "app_settings_id": "<app-settings-uuid>",
        "recipient_number": "<recipient_phone_number_in_E164_format>",
        "message": "Hello world!"
    }
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process WhatsApp message sending.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with WhatsApp API response
        """
        # Get configuration values (already resolved by BaseNode)
        app_settings_id = config.get("app_settings_id")
        to = config.get("recipient_number")
        text = config.get("message")

        # Validate required parameters
        if not all([app_settings_id, to, text]):
            error_msg = "WhatsApp tool: app_settings_id, recipient_number and message are required"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        try:
            # Get app settings from database
            app_settings_service = injector.get(AppSettingsService)
            app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

            # Extract token and phone_number_id from app settings values
            values = (
                app_settings.values if isinstance(app_settings.values, dict) else {}
            )
            token = values.get("whatsapp_token")
            phone_number_id = values.get("phone_number_id")

            # Validate that we have the required values and they are strings
            if not token or not isinstance(token, str):
                error_msg = (
                    "WhatsApp tool: whatsapp_token not found or invalid in app settings"
                )
                logger.error(error_msg)
                return {"status": 400, "data": {"error": error_msg}}

            if not phone_number_id or not isinstance(phone_number_id, str):
                error_msg = "WhatsApp tool: phone_number_id not found or invalid in app settings"
                logger.error(error_msg)
                return {"status": 400, "data": {"error": error_msg}}

            # Validate recipient_number and message are strings
            if not isinstance(to, str):
                error_msg = "WhatsApp tool: recipient_number must be a string"
                logger.error(error_msg)
                return {"status": 400, "data": {"error": error_msg}}

            if not isinstance(text, str):
                error_msg = "WhatsApp tool: message must be a string"
                logger.error(error_msg)
                return {"status": 400, "data": {"error": error_msg}}

            # At this point, we know to and text are strings
            recipient_number: str = cast(str, to)
            message_text: str = cast(str, text)

            # Send the WhatsApp message
            whatsapp_connector = WhatsAppConnector(
                token=token, phone_number_id=phone_number_id
            )
            result = await whatsapp_connector.send_text_message(
                recipient_number=recipient_number, text=message_text
            )
            return result

        except Exception as e:
            error_msg = f"Error sending WhatsApp message: {str(e)}"
            logger.error(error_msg)
            return {"status": 500, "data": {"error": error_msg}}
