"""keep ML pipeline configs and runs when a workflow row is deleted

Both foreign keys from the ML pipeline tables to `workflows` were ON DELETE
CASCADE, so removing a workflow row silently removed the model's pipeline
configuration and its whole run history. They become RESTRICT: a workflow
that a pipeline config or run still points at cannot be hard-deleted.

Revision ID: 5b7e2c91a4d3
Revises: d8f31a6b902e
Create Date: 2026-11-04 23:40:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b7e2c91a4d3"
down_revision: Union[str, None] = "d8f31a6b902e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FKS = (
    ("ml_model_pipeline_configs", "ml_model_pipeline_configs_workflow_id_fkey"),
    ("ml_model_pipeline_runs", "ml_model_pipeline_runs_workflow_id_fkey"),
)


def _set_ondelete(ondelete: str) -> None:
    for table, name in _FKS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, "workflows", ["workflow_id"], ["id"], ondelete=ondelete)


def upgrade() -> None:
    _set_ondelete("RESTRICT")


def downgrade() -> None:
    _set_ondelete("CASCADE")
