"""
Jira node implementation using the BaseNode class.
"""

import logging
from typing import Dict, Any
from uuid import UUID

from ..base_node import BaseNode
from app.modules.integration.jira import JiraConnector
from app.services.app_settings import AppSettingsService
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


class JiraNode(BaseNode):
    """
    Processor for creating Jira tasks via the REST API using the BaseNode approach.
    Expects credentials and task metadata in the incoming configuration.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Jira task creation.

        Args:
            config: The resolved configuration for the node.

        Returns:
            Dictionary with Jira API response payload.
        """
        app_settings_id = config.get("app_settings_id")
        space_key = str(config.get("spaceKey"))
        task_name = str(config.get("taskName"))
        task_description = str(config.get("taskDescription"))

        params = {
            "configuration variables": app_settings_id,
            "space key": space_key,
            "task name": task_name,
            "task description": task_description,
        }

        missing_parameters = [key for key,
                              value in params.items() if not value]

        if missing_parameters:
            error_msg = f"Jira Task Creator node missing these parameters: {', '.join(missing_parameters)}"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        try:
            # Get app settings from database
            app_settings_service = injector.get(AppSettingsService)
            app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

            # Extract subdomain, email, and api_token from app settings values
            values = (
                app_settings.values if isinstance(
                    app_settings.values, dict) else {}
            )

            subdomain = str(values.get("jira_subdomain"))
            email = str(values.get("jira_email"))
            api_token = str(values.get("jira_api_token"))

            jira_connector = JiraConnector(
                subdomain=subdomain, email=email, api_token=api_token)
            result = await jira_connector.create_task(
                space_key=space_key,
                task_name=task_name,
                task_description=task_description,
            )
            return result
        except Exception as e:
            error_msg = f"Error creating Jira task: {str(e)}"
            logger.error(error_msg)
            return {"status": 500, "data": {"error": error_msg}}
