"""mcp oauth2: discovery URL in auth_values + unique index on discovery + client hash

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-04-08 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_mcp_oauth_issuer_client;")

    op.execute(
        """
        UPDATE mcp_servers
        SET auth_values = auth_values || jsonb_build_object(
            'oauth2_discovery_url',
            rtrim(btrim(auth_values->>'oauth2_issuer_url'), '/') ||
            '/.well-known/openid-configuration'
        )
        WHERE auth_type = 'oauth2'
          AND coalesce(btrim(auth_values->>'oauth2_issuer_url'), '') <> ''
          AND coalesce(btrim(auth_values->>'oauth2_discovery_url'), '') = '';
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_oauth_discovery_client
        ON mcp_servers (
            (auth_values->>'oauth2_discovery_url'),
            (auth_values->>'oauth2_client_id_hash')
        )
        WHERE auth_type = 'oauth2' AND is_deleted = 0
          AND auth_values->>'oauth2_client_id_hash' IS NOT NULL
          AND coalesce(btrim(auth_values->>'oauth2_discovery_url'), '') <> '';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_mcp_oauth_discovery_client;")

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_oauth_issuer_client
        ON mcp_servers (
            (auth_values->>'oauth2_issuer_url'),
            (auth_values->>'oauth2_client_id_hash')
        )
        WHERE auth_type = 'oauth2' AND is_deleted = 0
          AND auth_values->>'oauth2_client_id_hash' IS NOT NULL;
        """
    )
