"""Add Jira as an app_settings type

Revision ID: 314b75ba8138
Revises: b9e655051a61
Create Date: 2025-11-19 13:44:53.435082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '314b75ba8138'
down_revision: Union[str, None] = 'b9e655051a61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('app_settings_type_check',
                       'app_settings', type_='check')
    op.create_check_constraint(
        'app_settings_type_check',
        'app_settings',
        "type IN ('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', 'Other')"
    )


def downgrade() -> None:
    op.drop_constraint('app_settings_type_check',
                       'app_settings', type_='check')
    op.create_check_constraint(
        'app_settings_type_check',
        'app_settings',
        "type IN ('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Other')"
    )
