"""
Slack tool node implementation using the BaseNode class.
"""

import logging
from typing import Dict, Any, cast
from uuid import UUID

from ..base_node import BaseNode
from app.modules.integration.slack import SlackConnector
from app.services.app_settings import AppSettingsService
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


class SlackToolNode(BaseNode):
    """Processor for sending Slack messages to users/channels using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a Slack message node.

        Expected input format:
        {
            "app_settings_id": "<app-settings-uuid>",
            "channel": "<slack-channel>",
            "message": "hello world"
        }

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with Slack API response
        """
        # Get configuration values (already resolved by BaseNode)
        app_settings_id = config.get("app_settings_id")
        channel = config.get("channel", "")
        message = config.get("message", "")

        # Validate required parameters
        if not all([app_settings_id, channel, message]):
            error_msg = "Slack tool: app_settings_id, channel and message are required"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        try:
            # Get app settings from database
            app_settings_service = injector.get(AppSettingsService)
            app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

            # Extract token from app settings values
            values = app_settings.values if isinstance(app_settings.values, dict) else {}
            token = values.get("slack_bot_token")

            # Validate that we have the required values and they are strings
            if not token or not isinstance(token, str):
                error_msg = (
                    "Slack tool: slack_bot_token not found or invalid in app settings"
                )
                logger.error(error_msg)
                return {"status": 400, "data": {"error": error_msg}}

            # Validate channel and message are strings
            if not isinstance(channel, str):
                error_msg = "Slack tool: channel must be a string"
                logger.error(error_msg)
                return {"status": 400, "data": {"error": error_msg}}

            if not isinstance(message, str):
                error_msg = "Slack tool: message must be a string"
                logger.error(error_msg)
                return {"status": 400, "data": {"error": error_msg}}

            # At this point, we know channel and message are strings
            slack_channel: str = cast(str, channel)
            message_text: str = cast(str, message)

            # Send the Slack message
            slack_connector = SlackConnector(token=token, channel=slack_channel)
            await slack_connector.sanitize_channel()
            result = await slack_connector.send_slack_message(text=message_text)
            return result

        except Exception as e:
            error_msg = f"Error sending Slack message: {str(e)}"
            logger.error(error_msg)
            return {"status": 500, "data": {"error": error_msg}}
