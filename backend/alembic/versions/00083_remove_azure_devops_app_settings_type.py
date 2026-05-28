"""remove AzureDevOps from app_settings type (Help Center uses env vars)

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-05-26

"""

from typing import Sequence, Union

from alembic import op

revision: str = "n3o4p5q6r7s8"
down_revision: Union[str, None] = "m2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_TYPES = (
    "('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', "
    "'FileManagerSettings', 'Other', 'Security', 'AzureDevOps')"
)
_NEW_TYPES = (
    "('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', "
    "'FileManagerSettings', 'Other', 'Security')"
)


def upgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE type = 'AzureDevOps'")
    op.drop_constraint("app_settings_type_check", "app_settings", type_="check")
    op.create_check_constraint(
        "app_settings_type_check",
        "app_settings",
        f"type IN {_NEW_TYPES}",
    )


def downgrade() -> None:
    op.drop_constraint("app_settings_type_check", "app_settings", type_="check")
    op.create_check_constraint(
        "app_settings_type_check",
        "app_settings",
        f"type IN {_OLD_TYPES}",
    )
