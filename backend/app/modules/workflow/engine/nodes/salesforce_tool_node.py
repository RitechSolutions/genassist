"""
SalesForce tool node implementation using the BaseNode class.
"""

import logging
from typing import Any, Dict
from uuid import UUID

from app.core.utils.encryption_utils import decrypt_key
from app.dependencies.injector import injector
from app.modules.integration.salesforce import SalesforceConnector
from app.schemas.dynamic_form_schemas.app_settings_schemas import (
    get_encrypted_fields_for_type,
)
from app.services.app_settings import AppSettingsService

from ..base_node import BaseNode

logger = logging.getLogger(__name__)


class SalesforceToolNode(BaseNode):
    """
    Processor for creating a SalesForce Case via the REST API using the BaseNode approach.
    Reads credentials from App Settings; only subject/description are required in input_data.
    Additional Case fields are set via ``custom_fields``; ``labels`` are assigned to the
    created Case as SalesForce Topics.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process SalesForce Case creation.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with the SalesForce API result envelope.
        """

        # Validate required fields
        subject = config.get("subject")
        description = config.get("description")
        labels = config.get("labels")
        custom_fields = config.get("custom_fields")
        app_settings_id = config.get("app_settings_id")

        if not subject or not description:
            error_msg = "Salesforce tool: Missing required fields: subject or description"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        try:
            # Get app settings from database
            app_settings_service = injector.get(AppSettingsService)
            app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

            values = (
                app_settings.values if isinstance(app_settings.values, dict) else {}
            )

            # The client secret is stored encrypted at rest (encrypted=True in the
            # Salesforce app-settings schema). get_by_id returns it still encrypted, so
            # decrypt the encrypted fields here before use — otherwise SalesForce rejects
            # the ciphertext with "invalid_client". Non-encrypted fields (instance_url,
            # client_id) pass through unchanged.
            encrypted_fields = set(get_encrypted_fields_for_type(app_settings.type))
            values = {
                key: (
                    decrypt_key(value)
                    if key in encrypted_fields and isinstance(value, str) and value
                    else value
                )
                for key, value in values.items()
            }

            # Pass the raw values (not str(...)) so missing fields stay None and the
            # connector's "credentials required" guards fire — str(None) would send the
            # literal "None" as a URL/secret and produce a confusing network error.
            salesforce_connector = SalesforceConnector(
                instance_url=values.get("salesforce_instance_url"),
                client_id=values.get("salesforce_client_id"),
                client_secret=values.get("salesforce_client_secret"),
            )

            # Create the SalesForce Case (labels are assigned as Topics afterward).
            result = await salesforce_connector.create_case(
                subject=subject,
                description=description,
                custom_fields=custom_fields,
                labels=labels,
            )

            # The connector returns None on failure; the node owns the 500 envelope.
            if result is None:
                error_msg = "Salesforce tool: failed to create Case"
                logger.error(error_msg)
                return {"status": 500, "data": {"error": error_msg}}

            return result

        except Exception as e:
            error_msg = f"Error creating Salesforce Case: {str(e)}"
            logger.error(error_msg)
            return {"status": 500, "data": {"error": error_msg}}
