"""add_smtp_app_setting_type

Adds 'SMTP' to the allowed values of the app_settings.type check constraint so
tenants can store per-tenant SMTP/email credentials via App Settings.

Revision ID: a1f2c3d4e5b6
Revises: 494257fd515b
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9f1df080dab5'
down_revision: Union[str, None] = '494257fd515b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "app_settings_type_check"
_TABLE = "app_settings"

_OLD_TYPES = (
    "'Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', "
    "'FileManagerSettings', 'Other', 'Security'"
)
_NEW_TYPES = (
    "'Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', 'SMTP', "
    "'FileManagerSettings', 'Other', 'Security'"
)


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(
        _CONSTRAINT, _TABLE, f"type IN ({_NEW_TYPES})"
    )


def downgrade() -> None:
    # Drop any SMTP rows first so the narrower constraint can be re-applied.
    op.execute(f"DELETE FROM {_TABLE} WHERE type = 'SMTP'")
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(
        _CONSTRAINT, _TABLE, f"type IN ({_OLD_TYPES})"
    )