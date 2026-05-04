"""add Security type to app_settings

Revision ID: f5e3ae54e989
Revises: f1a2b3c4d5e6
Create Date: 2026-04-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f5e3ae54e989"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_TYPES = "('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', 'FileManagerSettings', 'Other')"
_NEW_TYPES = "('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', 'FileManagerSettings', 'Other', 'Security')"


def upgrade() -> None:
    op.drop_constraint("app_settings_type_check", "app_settings", type_="check")
    op.create_check_constraint(
        "app_settings_type_check",
        "app_settings",
        f"type IN {_NEW_TYPES}",
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE type = 'Security'")
    op.drop_constraint("app_settings_type_check", "app_settings", type_="check")
    op.create_check_constraint(
        "app_settings_type_check",
        "app_settings",
        f"type IN {_OLD_TYPES}",
    )