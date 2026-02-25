"""add FileManagerSettings to app_settings type constraint

Revision ID: c9e0f1234567
Revises: 5b024671c309
Create Date: 2026-02-17

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e0f1234567"
down_revision: Union[str, None] = "5b024671c309"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('app_settings_type_check',
                       'app_settings', type_='check')
    op.create_check_constraint(
        'app_settings_type_check',
        'app_settings',
        "type IN ('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', 'FileManagerSettings', 'Other')"
    )


def downgrade() -> None:
    op.drop_constraint('app_settings_type_check',
                       'app_settings', type_='check')
    op.create_check_constraint(
        'app_settings_type_check',
        'app_settings',
        "type IN ('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', 'Other')"
    )
