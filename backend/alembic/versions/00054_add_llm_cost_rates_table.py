"""add llm_cost_rates table and seed default pricing

Revision ID: ccaa77b2b8e3
Revises: f4a5b6c7d8e9
Create Date: 2026-03-24 12:00:00.000000

"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "ccaa77b2b8e3"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (provider_key, model_key, input_per_1k, output_per_1k) — mirrors former llm_pricing.py
_SEED_ROWS: list[tuple[str, str, float, float]] = [
    ("openai", "gpt-4o", 0.0025, 0.01),
    ("openai", "gpt-4o-mini", 0.00015, 0.0006),
    ("openai", "gpt-4-turbo", 0.01, 0.03),
    ("openai", "gpt-4", 0.03, 0.06),
    ("openai", "gpt-3.5-turbo", 0.0005, 0.0015),
    ("openai", "gpt-3.5-turbo-16k", 0.003, 0.004),
    ("openai", "o1", 0.015, 0.06),
    ("openai", "o1-mini", 0.003, 0.012),
    ("anthropic", "claude-3-5-sonnet", 0.003, 0.015),
    ("anthropic", "claude-3-5-haiku", 0.0008, 0.004),
    ("anthropic", "claude-3-sonnet", 0.003, 0.015),
    ("anthropic", "claude-3-opus", 0.015, 0.075),
    ("anthropic", "claude-3-haiku", 0.00025, 0.00125),
    ("anthropic", "eu.anthropic.claude-3-haiku-20240307-v1:0", 0.00025, 0.00125),
    ("google_genai", "gemini-1.5-pro", 0.00125, 0.005),
    ("google_genai", "gemini-1.5-flash", 0.000075, 0.0003),
    ("google_genai", "gemini-1.0-pro", 0.0005, 0.0015),
    ("openrouter", "_default", 0.001, 0.002),
    ("vllm", "_default", 0.0, 0.0),
    ("ollama", "_default", 0.0, 0.0),
    ("bedrock", "eu.amazon.nova-2-lite-v1:0", 0.0001, 0.0004),
    ("bedrock", "ca.amazon.nova-2-lite-v1:0", 0.0001, 0.0004),
    ("bedrock", "us.amazon.nova-2-lite-v1:0", 0.0001, 0.0004),
    ("bedrock", "us.amazon.nova-2-pro-v1:0", 0.0002, 0.0008),
    ("bedrock", "us.amazon.nova-2-flash-v1:0", 0.0004, 0.0016),
]


def upgrade() -> None:
    op.create_table(
        "llm_cost_rates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("model_key", sa.String(length=512), nullable=False),
        sa.Column("input_per_1k", sa.Numeric(precision=18, scale=10), nullable=False),
        sa.Column("output_per_1k", sa.Numeric(precision=18, scale=10), nullable=False),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="llm_cost_rates_pk"),
    )
    op.create_index(
        "ix_llm_cost_rates_provider_model",
        "llm_cost_rates",
        ["provider_key", "model_key"],
        unique=False,
    )

    conn = op.get_bind()
    insert_sql = sa.text(
        """
        INSERT INTO llm_cost_rates (
            id, provider_key, model_key, input_per_1k, output_per_1k,
            created_by, updated_by, created_at, updated_at, is_deleted
        ) VALUES (
            :id, :provider_key, :model_key, :input_per_1k, :output_per_1k,
            NULL, NULL, NOW(), NOW(), 0
        )
        """
    )
    for prov, mod, inp, out in _SEED_ROWS:
        conn.execute(
            insert_sql,
            {
                "id": uuid.uuid4(),
                "provider_key": prov,
                "model_key": mod,
                "input_per_1k": inp,
                "output_per_1k": out,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_llm_cost_rates_provider_model", table_name="llm_cost_rates")
    op.drop_table("llm_cost_rates")
