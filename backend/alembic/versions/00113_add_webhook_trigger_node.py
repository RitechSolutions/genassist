"""add webhook trigger node

A Webhook Trigger node lets an external system start a workflow run through an
inbound HTTP request. Each trigger is a ``webhooks`` row of type
``workflow_trigger`` bound to an agent *and* a workflow node, so it survives
workflow versioning (node ids are copied across versions) and always executes
the agent's current workflow, like schedules do.

- ``webhooks.node_id``: the trigger node this endpoint belongs to
- ``webhooks.auth_mode``: ``bearer`` or ``hmac``
- ``webhooks.rate_limit_per_minute``: per-endpoint ingress limit
- ``workflow_trigger_runs``: run history (mirrors ``workflow_schedule_runs``)
  with an idempotency key so retried deliveries never start a second run
- feature flag ``workflow.webhookTrigger`` seeded hidden

The upgrade is idempotent: an earlier, unreleased draft of this feature left
``node_id`` / ``auth_mode``, an index and a ``workflow.showWebhookTrigger`` flag
on some development databases. Those are adopted or cleaned up rather than
failing the migration.

Revision ID: 3c9d1e7a5b2f
Revises: 8f3c2a91b7d4
Create Date: 2026-09-24 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "3c9d1e7a5b2f"
down_revision: Union[str, None] = "8f3c2a91b7d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEATURE_FLAG_KEY = "workflow.webhookTrigger"
LEGACY_FEATURE_FLAG_KEY = "workflow.showWebhookTrigger"
LEGACY_INDEX = "uq_webhooks_workflow_trigger_agent_node"

_RUNS_TABLE = "workflow_trigger_runs"
_AGENT_NODE_INDEX = "webhooks_workflow_trigger_agent_node_unique"


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    existing = _columns("webhooks")
    if "node_id" not in existing:
        op.add_column("webhooks", sa.Column("node_id", sa.String(length=255), nullable=True))
    if "auth_mode" not in existing:
        op.add_column(
            "webhooks",
            sa.Column("auth_mode", sa.String(length=20), nullable=False, server_default="bearer"),
        )
    if "rate_limit_per_minute" not in existing:
        op.add_column(
            "webhooks",
            sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        )
    # An adopted column from the earlier draft has no default; align it with the model.
    op.execute("UPDATE webhooks SET auth_mode = 'bearer' WHERE auth_mode IS NULL")
    op.execute("ALTER TABLE webhooks ALTER COLUMN auth_mode SET DEFAULT 'bearer'")
    op.execute("ALTER TABLE webhooks ALTER COLUMN auth_mode SET NOT NULL")

    # One trigger endpoint per (agent, node); soft-deleted rows release the slot.
    op.execute(f"DROP INDEX IF EXISTS {LEGACY_INDEX}")
    # The earlier draft's run table (never part of any released migration).
    op.execute("DROP TABLE IF EXISTS webhook_trigger_runs")
    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {_AGENT_NODE_INDEX}
        ON webhooks (agent_id, node_id)
        WHERE webhook_type = 'workflow_trigger' AND is_deleted = 0
        """
    )

    # Reuse the schedule-run status enum: both tables describe a queued workflow run.
    run_status_enum = postgresql.ENUM(
        "PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED",
        name="workflow_schedule_run_status_enum",
        create_type=False,
    )
    run_status_enum.create(op.get_bind(), checkfirst=True)

    if not _has_table(_RUNS_TABLE):
        op.create_table(
            _RUNS_TABLE,
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("webhook_id", sa.UUID(), nullable=False),
            sa.Column("agent_id", sa.UUID(), nullable=False),
            sa.Column("node_id", sa.String(length=255), nullable=False),
            sa.Column("workflow_id", sa.UUID(), nullable=True),
            sa.Column("thread_id", sa.String(length=255), nullable=True),
            sa.Column("status", run_status_enum, nullable=False, server_default="PENDING"),
            sa.Column("idempotency_key", sa.String(length=255), nullable=True),
            sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("execution_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("execution_id", sa.UUID(), nullable=True),
            sa.Column("created_by", sa.UUID(), nullable=True),
            sa.Column("updated_by", sa.UUID(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("is_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute(f"CREATE INDEX IF NOT EXISTS idx_workflow_trigger_runs_webhook_id ON {_RUNS_TABLE} (webhook_id)")
    op.execute(f"CREATE INDEX IF NOT EXISTS idx_workflow_trigger_runs_status ON {_RUNS_TABLE} (status)")
    op.execute(f"CREATE INDEX IF NOT EXISTS idx_workflow_trigger_runs_created_at ON {_RUNS_TABLE} (created_at)")
    # A retried delivery with the same key finds the first run instead of starting another.
    op.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS workflow_trigger_runs_idempotency_unique
        ON {_RUNS_TABLE} (webhook_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )

    # Seed the feature flag hidden by default (idempotent on the unique key);
    # drop the earlier draft's flag so Settings shows a single switch.
    op.execute(f"DELETE FROM feature_flags WHERE key = '{LEGACY_FEATURE_FLAG_KEY}'")
    op.execute(
        f"""
        INSERT INTO feature_flags (id, key, val, description, is_active, is_deleted)
        VALUES (gen_random_uuid(), '{FEATURE_FLAG_KEY}', 'false',
                'Webhook Trigger node (start a workflow from an inbound HTTP request)', 1, 0)
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM feature_flags WHERE key = '{FEATURE_FLAG_KEY}'")

    op.execute("DROP INDEX IF EXISTS workflow_trigger_runs_idempotency_unique")
    op.execute("DROP INDEX IF EXISTS idx_workflow_trigger_runs_created_at")
    op.execute("DROP INDEX IF EXISTS idx_workflow_trigger_runs_status")
    op.execute("DROP INDEX IF EXISTS idx_workflow_trigger_runs_webhook_id")
    op.execute(f"DROP TABLE IF EXISTS {_RUNS_TABLE}")
    # The status enum is owned by 00086 (workflow_schedule_runs); leave it in place.

    op.execute("DELETE FROM webhooks WHERE webhook_type = 'workflow_trigger'")
    op.execute(f"DROP INDEX IF EXISTS {_AGENT_NODE_INDEX}")
    existing = _columns("webhooks")
    for column in ("rate_limit_per_minute", "auth_mode", "node_id"):
        if column in existing:
            op.drop_column("webhooks", column)
