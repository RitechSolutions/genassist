"""validate the ML pipeline foreign keys to workflows

00128 re-added both keys NOT VALID, so it never scanned a table while holding
its locks. VALIDATE CONSTRAINT scans each table under SHARE UPDATE EXCLUSIVE
(and ROW SHARE on workflows), which does not block reads or writes. Runs in its
own migration transaction, so it stays under the migration lock timeout. Tables
go in the app's lock order: runs, then configs.

Revision ID: 9c4e1f7a2b6d
Revises: 5b7e2c91a4d3
Create Date: 2026-11-05 15:30:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c4e1f7a2b6d"
down_revision: Union[str, None] = "5b7e2c91a4d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FKS = (
    ("ml_model_pipeline_runs", "ml_model_pipeline_runs_workflow_id_fkey"),
    ("ml_model_pipeline_configs", "ml_model_pipeline_configs_workflow_id_fkey"),
)


def upgrade() -> None:
    for table, name in _FKS:
        op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}")


def downgrade() -> None:
    # Nothing to undo: a validated key is the same key. 00128's downgrade swaps
    # both keys back to validated CASCADE ones.
    pass
