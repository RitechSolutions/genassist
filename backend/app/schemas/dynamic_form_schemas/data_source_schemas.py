"""
Data source connection schemas.

This module defines field schemas for data source connection types.
All schemas use the unified TypeSchema structure from base.py.
"""

from typing import Dict
from .base import FieldSchema, TypeSchema, ConditionalField, convert_typed_schemas_to_dict

# Define field schemas for each data source type
DATA_SOURCE_SCHEMAS: Dict[str, TypeSchema] = {
    "S3": TypeSchema(
        name="S3",
        fields=[
            FieldSchema(
                name="access_key",
                type="password",
                label="Access key",
                required=True,
                description="Enter access key",
            ),
            FieldSchema(
                name="secret_key",
                type="password",
                label="Secret key",
                required=True,
                description="Enter secret key",
            ),
            FieldSchema(
                name="region",
                type="text",
                label="Region",
                required=True,
                description="Enter region",
            ),
            FieldSchema(
                name="bucket_name",
                type="text",
                label="Bucket name",
                required=True,
                description="Enter bucket name",
            ),
            FieldSchema(
                name="prefix",
                type="text",
                label="Prefix",
                required=True,
                description="Enter prefix",
            ),
        ],
    ),
    "Database": TypeSchema(
        name="Database",
        fields=[
            FieldSchema(
                name="database_type",
                type="select",
                label="Database type",
                required=True,
                options=[
                    {"value": "postgresql", "label": "PostgreSQL"},
                    {"value": "mysql", "label": "MySQL"},
                    {"value": "mssql", "label": "MSSQL"},
                ],
            ),
            FieldSchema(
                name="database_host",
                type="text",
                label="Database host",
                required=True,
                description="Enter database host",
            ),
            FieldSchema(
                name="database_port",
                type="number",
                label="Database port",
                required=True,
                description="Enter database port",
            ),
            FieldSchema(
                name="database_name",
                type="text",
                label="Database name",
                required=True,
                description="Enter database name",
            ),
            FieldSchema(
                name="database_user",
                type="text",
                label="Database user",
                required=True,
                description="Enter database user",
            ),
            FieldSchema(
                name="database_password",
                type="password",
                label="Database password",
                required=True,
                description="Enter database password",
            ),
            FieldSchema(
                name="allowed_tables",
                type="text",
                label="Allowed tables",
                required=False,
                description="Enter allowed tables",
                placeholder="table1, table2",
            ),
            FieldSchema(
                name="ssh_tunnel_host",
                type="text",
                label="SSH tunnel host",
                required=False,
                description="Enter SSH tunnel host",
            ),
            FieldSchema(
                name="ssh_tunnel_port",
                type="number",
                label="SSH tunnel port",
                required=False,
                description="Enter SSH tunnel port",
            ),
            FieldSchema(
                name="ssh_tunnel_user",
                type="text",
                label="SSH tunnel user",
                required=False,
                description="Enter SSH tunnel user",
            ),
            FieldSchema(
                name="ssh_tunnel_private_key",
                type="password",
                label="SSH tunnel private key",
                required=False,
                description="Enter SSH tunnel private key",
            ),
        ],
    ),
    "URL": TypeSchema(
        name="URL",
        fields=[
            FieldSchema(
                name="url",
                type="text",
                label="Web page URL",
                required=True,
                description="https://example.com/your-doc",
            )
        ],
    ),
    "Snowflake": TypeSchema(
        name="Snowflake",
        fields=[
            FieldSchema(
                name="account",
                type="text",
                label="Account",
                required=True,
                description="Enter Snowflake account identifier",
            ),
            FieldSchema(
                name="database",
                type="text",
                label="Database",
                required=True,
                description="Enter Snowflake database name",
            ),
            FieldSchema(
                name="username",
                type="text",
                label="User",
                required=True,
                description="Enter Snowflake username",
            ),
            FieldSchema(
                name="warehouse",
                type="text",
                label="Warehouse",
                required=True,
                description="Enter Snowflake warehouse name",
            ),
            FieldSchema(
                name="auth_method",
                type="select",
                label="Authentication Method",
                required=True,
                options=[
                    {"value": "password", "label": "Password"},
                    {"value": "private_key", "label": "Private Key (Recommended)"},
                ],
                description="Choose authentication method for Snowflake connection",
            ),
            FieldSchema(
                name="password",
                type="password",
                label="Password",
                required=True,
                description="Enter Snowflake password",
                conditional=ConditionalField(field="auth_method", value="password"),
            ),
            FieldSchema(
                name="private_key",
                type="password",
                label="Private Key",
                required=True,
                description="Enter RSA private key for authentication",
                conditional=ConditionalField(field="auth_method", value="private_key"),
            ),
            FieldSchema(
                name="private_key_passphrase",
                type="password",
                label="Private Key Passphrase",
                required=False,
                description="Enter passphrase for encrypted private key (if applicable)",
                conditional=ConditionalField(field="auth_method", value="private_key"),
            ),
            FieldSchema(
                name="schema",
                type="text",
                label="Schema",
                required=False,
                description="Enter Snowflake schema name",
                placeholder="PUBLIC",
                advanced=True,
            ),
            FieldSchema(
                name="role",
                type="text",
                label="Role",
                required=False,
                description="Enter Snowflake role",
                advanced=True,
            ),
            FieldSchema(
                name="allowed_tables",
                type="text",
                label="Allowed tables",
                required=False,
                description="Comma-separated allowlist",
                placeholder="ORDERS, CUSTOMERS",
                advanced=True,
            ),
        ],
    ),
    "Zendesk": TypeSchema(
        name="Zendesk",
        fields=[
            FieldSchema(
                name="subdomain",
                type="text",
                label="Zendesk Subdomain",
                required=True,
                description="Your Zendesk subdomain (e.g., 'yourcompany' for yourcompany.zendesk.com)",
                placeholder="yourcompany",
            ),
            FieldSchema(
                name="email",
                type="text",
                label="Email",
                required=True,
                description="Zendesk account email address",
                placeholder="user@example.com",
            ),
            FieldSchema(
                name="api_token",
                type="password",
                label="API Token",
                required=True,
                description="Zendesk API token for authentication",
            ),
            FieldSchema(
                name="locale",
                type="text",
                label="Locale",
                required=False,
                description="Locale for articles (e.g., 'en-us'). Leave empty to sync all locales.",
                placeholder="en-us",
                advanced=True,
            ),
            FieldSchema(
                name="section_id",
                type="number",
                label="Section ID",
                required=False,
                description="Optional: Only sync articles from a specific section. Leave empty to sync all sections.",
                advanced=True,
            ),
        ],
    ),
}
DATA_SOURCE_SCHEMAS_DICT = convert_typed_schemas_to_dict(DATA_SOURCE_SCHEMAS)