"""keep ML pipeline configs and runs when a workflow row is deleted

Both foreign keys from the ML pipeline tables to `workflows` were ON DELETE
CASCADE, so removing a workflow row silently removed the model's pipeline
configuration and its whole run history. They become RESTRICT: a workflow
that a pipeline config or run still points at cannot be hard-deleted.

Runs while the old pods still serve traffic, so it takes all its locks first,
with a wait shorter than Postgres's deadlock check (see _lock_up_front),
and re-adds the keys NOT VALID so no table is scanned under those locks. Every
existing row already satisfies the keys (the old ones were valid);
00129 validates them in its own transaction without blocking writes.

Revision ID: 5b7e2c91a4d3
Revises: d8f31a6b902e
Create Date: 2026-11-04 23:40:00.000000
"""

import logging
import time
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
    ("ml_model_pipeline_runs", "ml_model_pipeline_runs_workflow_id_fkey"),
    ("ml_model_pipeline_configs", "ml_model_pipeline_configs_workflow_id_fkey"),
)

_LOCK_NOT_AVAILABLE = "55P03"
_LOCK_WAIT_MS = 500  # below Postgres's default deadlock_timeout (1s)
_LOCK_PAUSE_SECONDS = 0.2
_LOCK_PATIENCE_SECONDS = 45


def _lock_up_front() -> None:
    """Take every lock this migration needs up front, giving up before a deadlock can form.

    The app touches these tables in both orders (a run insert locks runs and then
    reads its config and workflow; run and config creation read the config and
    workflow first), so no fixed order is safe on its own. The wait is capped
    below Postgres's deadlock check (deadlock_timeout, 1s by default): if an app
    transaction holds a lock this migration needs, the attempt gives up and its
    savepoint releases whatever it took, so Postgres never has to kill an app
    request. Attempts repeat for _LOCK_PATIENCE_SECONDS to find a quiet moment;
    after that the 55P03 goes to the runner, which retries the whole migration.
    Once the locks are held no statement below waits for another. Dropping a
    foreign key needs ACCESS EXCLUSIVE on the referenced table too.
    """
    bind = op.get_bind()
    op.execute(f"SET LOCAL lock_timeout = '{_LOCK_WAIT_MS}ms'")
    deadline = time.monotonic() + _LOCK_PATIENCE_SECONDS
    while True:
        try:
            with bind.begin_nested():
                op.execute(
                    "LOCK TABLE ml_model_pipeline_runs, ml_model_pipeline_configs, workflows "
                    "IN ACCESS EXCLUSIVE MODE"
                )
            return
        except sa.exc.DBAPIError as error:
            if getattr(error.orig, "pgcode", None) != _LOCK_NOT_AVAILABLE or time.monotonic() >= deadline:
                raise
            time.sleep(_LOCK_PAUSE_SECONDS)


def _set_ondelete(ondelete: str, *, not_valid: bool) -> None:
    """Swap each key for one with the new ON DELETE rule.

    Postgres cannot change ON DELETE in place, so the key is dropped and added
    back in the same transaction; no write ever runs without it.
    """
    suffix = " NOT VALID" if not_valid else ""
    for table, name in _FKS:
        op.execute(
            f"-- squawk-ignore ban-drop-constraint\n"
            f"ALTER TABLE {table} DROP CONSTRAINT {name}"
        )
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY (workflow_id) "
            f"REFERENCES workflows (id) ON DELETE {ondelete}{suffix}"
        )


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
    _lock_up_front()
    _unschedule_orphaned_configs()
    _set_ondelete("RESTRICT", not_valid=True)


def downgrade() -> None:
    # A rollback restores the validated CASCADE keys exactly (00129's downgrade is a no-op).
    _lock_up_front()
    _set_ondelete("CASCADE", not_valid=False)
