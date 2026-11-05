"""keep ML pipeline configs and runs when a workflow row is deleted

Both foreign keys from the ML pipeline tables to `workflows` were ON DELETE
CASCADE, so removing a workflow row silently removed the model's pipeline
configuration and its whole run history. They become RESTRICT: a workflow
that a pipeline config or run still points at cannot be hard-deleted.

Revision ID: 5b7e2c91a4d3
Revises: d8f31a6b902e
Create Date: 2026-11-04 23:40:00.000000
"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

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


def _unschedule_orphaned_configs() -> None:
    """Stop the schedule of live configs already left on a deleted workflow.

    Deleting an agent before this fix retired its workflow versions under live
    pipeline configs, and every scheduled run of those configs failed with
    "workflow not found". Their cron schedule is cleared, so the model page no
    longer claims they run automatically; each one is logged with its old
    schedule. The config and its run history are kept: delete it, or create a
    new config on a live workflow, from the model's pipeline settings.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT c.id, c.model_id, c.workflow_id, c.cron_schedule "
            "FROM ml_model_pipeline_configs c JOIN workflows w ON w.id = c.workflow_id "
            "WHERE c.is_deleted = 0 AND w.is_deleted = 1"
        )
    ).fetchall()
    for config_id, model_id, workflow_id, cron_schedule in rows:
        logger.warning(
            "ML pipeline config %s (model %s) points at deleted workflow %s; "
            "cleared its schedule %r. Delete it or create a new config on a live workflow.",
            config_id, model_id, workflow_id, cron_schedule,
        )
    if rows:
        bind.execute(
            sa.text(
                "UPDATE ml_model_pipeline_configs SET cron_schedule = NULL "
                "WHERE id = ANY(:ids) AND cron_schedule IS NOT NULL"
            ),
            {"ids": [row[0] for row in rows]},
        )


def upgrade() -> None:
    _unschedule_orphaned_configs()
    _set_ondelete("RESTRICT")


def downgrade() -> None:
    _set_ondelete("CASCADE")
