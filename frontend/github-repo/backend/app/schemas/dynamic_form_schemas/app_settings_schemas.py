"""
App settings integration schemas.

This module defines field schemas for AppSettings integration types.
All schemas use the unified TypeSchema structure from base.py.
"""

from typing import List, Dict, Optional
from .base import FieldSchema, TypeSchema, convert_typed_schemas_to_dict

# Define field schemas for each integration type
APP_SETTINGS_SCHEMAS: Dict[str, TypeSchema] = {
    "Zendesk": TypeSchema(
        name="Zendesk",
        fields=[
            FieldSchema(
                name="zendesk_subdomain",
                label="Zendesk Subdomain",
                type="text",
                required=True,
                placeholder="example.zendesk.com",
                description="Your Zendesk subdomain",
                encrypted=False,
            ),
            FieldSchema(
                name="zendesk_email",
                label="Zendesk Email",
                type="text",
                required=True,
                placeholder="admin@example.com",
                description="Email address for API authentication",
                encrypted=False,
            ),
            FieldSchema(
                name="zendesk_api_token",
                label="Zendesk API Token",
                type="password",
                required=True,
                placeholder="Enter API token",
                description="Zendesk API token for authentication",
                encrypted=False,
            ),
        ],
    ),
    "WhatsApp": TypeSchema(
        name="WhatsApp",
        fields=[
            FieldSchema(
                name="whatsapp_token",
                label="WhatsApp Token",
                type="password",
                required=True,
                placeholder="Enter WhatsApp token",
                description="WhatsApp API token",
                encrypted=False,
            ),
            FieldSchema(
                name="phone_number_id",
                label="Phone Number ID",
                type="text",
                required=True,
                placeholder="Enter Phone Number ID",
                description="WhatsApp Phone Number ID",
                encrypted=False,
            ),
        ],
    ),
    "Gmail": TypeSchema(
        name="Gmail",
        fields=[
            FieldSchema(
                name="gmail_client_id",
                label="Gmail Client ID",
                type="text",
                required=True,
                placeholder="Enter Gmail Client ID",
                description="Google OAuth Client ID",
                encrypted=False,
            ),
            FieldSchema(
                name="gmail_client_secret",
                label="Gmail Client Secret",
                type="password",
                required=True,
                placeholder="Enter Gmail Client Secret",
                description="Google OAuth Client Secret",
                encrypted=False,
            ),
        ],
    ),
    "Microsoft": TypeSchema(
        name="Microsoft",
        fields=[
            FieldSchema(
                name="microsoft_client_id",
                label="Microsoft Client ID",
                type="text",
                required=True,
                placeholder="Enter Microsoft Client ID",
                description="Microsoft OAuth Client ID",
                encrypted=False,
            ),
            FieldSchema(
                name="microsoft_client_secret",
                label="Microsoft Client Secret",
                type="password",
                required=True,
                placeholder="Enter Microsoft Client Secret",
                description="Microsoft OAuth Client Secret",
                encrypted=False,
            ),
            FieldSchema(
                name="microsoft_tenant_id",
                label="Microsoft Tenant ID",
                type="text",
                required=True,
                placeholder="Enter Microsoft Tenant ID",
                description="Microsoft Azure Tenant ID",
                encrypted=False,
            ),
        ],
    ),
    "Slack": TypeSchema(
        name="Slack",
        fields=[
            FieldSchema(
                name="slack_bot_token",
                label="Slack Bot Token",
                type="text",
                required=True,
                placeholder="Enter Slack Bot Token",
                description="Slack Bot Token for authentication",
                encrypted=False,
            ),
            FieldSchema(
                name="slack_signing_secret",
                label="Slack Signing Secret",
                type="text",
                required=True,
                placeholder="Enter Slack Signing Secret",
                description="Slack Signing Secret for webhook verification",
                encrypted=False,
            ),
        ],
    ),
    "Jira": TypeSchema(
        name="Jira",
        fields=[
            FieldSchema(
                name="jira_subdomain",
                label="Jira Subdomain",
                type="text",
                required=True,
                placeholder="example.atlassian.net",
                description="Your Jira subdomain",
                encrypted=False,
            ),
            FieldSchema(
                name="jira_email",
                label="Jira Email",
                type="text",
                required=True,
                placeholder="admin@example.com",
                description="Email address for API authentication",
                encrypted=False,
            ),
            FieldSchema(
                name="jira_api_token",
                label="Jira API Token",
                type="password",
                required=True,
                placeholder="Enter API token",
                description="Jira API token for authentication",
                encrypted=False,
            ),
        ],
    )
}

APP_SETTINGS_SCHEMAS_DICT = convert_typed_schemas_to_dict(APP_SETTINGS_SCHEMAS)


def get_schema_for_type(type_name: str) -> Optional[TypeSchema]:
    """Get the schema for a given type."""
    return APP_SETTINGS_SCHEMAS.get(type_name)


def get_all_schemas() -> Dict[str, TypeSchema]:
    """Get all schemas."""
    return APP_SETTINGS_SCHEMAS


def get_encrypted_fields_for_type(type_name: str) -> List[str]:
    """Get list of encrypted field names for a given type."""
    schema = get_schema_for_type(type_name)
    if not schema or not schema.fields:
        return []
    return [field.name for field in schema.fields if field.encrypted]
