"""add the Workflow Builder's own LLM provider and point the builder at it

New tenants get this provider from seed.py; this migration gives it to the tenant
databases seeded before it existed. The row reuses the encrypted OpenAI API key of
the seeded 'openai dev 1.0' provider (failing that, of the tenant's oldest active
OpenAI provider) with the gpt-6.1-terra model. It is NOT the tenant default: the
workflows the builder creates keep taking the existing default
(LlmProviderService.get_default, i.e. 'openai dev 1.0'). Only the Workflow Builder
agent's own agent node is re-pointed at it. A tenant without any OpenAI key is left
untouched. Re-running after a downgrade revives the soft-deleted row and refreshes
its name and model.

Revision ID: 3f8a1c6d9e24
Revises: 9c4e1f7a2b6d
Create Date: 2026-11-10 14:00:00.000000
"""

from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3f8a1c6d9e24"
down_revision: Union[str, None] = "9c4e1f7a2b6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors app/db/seed/seed_data_config.py; kept literal so a later rename there never
# changes what an already-written migration does (a unit test keeps the two in step).
PROVIDER_ID = "00000196-19d2-9c28-a2dd-566fff608fa0"
PROVIDER_NAME = "openai dev gpt-6.1-terra"
PROVIDER_MODEL = "gpt-6.1-terra"
SOURCE_PROVIDER_ID = "00000196-19d2-9c28-a2dd-561fff608fa0"  # 'openai dev 1.0'
SOURCE_PROVIDER_NAME = "openai dev 1.0"
AGENT_NAME = "Workflow Builder"

_KEY_OF = (
    "SELECT connection_data->>'api_key' FROM llm_providers "
    "WHERE {where} AND is_deleted = 0 ORDER BY created_at ASC LIMIT 1"
)
# In order of preference: the seeded provider by id, by name, then any active OpenAI provider.
_KEY_LOOKUPS = (
    ("id = CAST(:value AS uuid)", SOURCE_PROVIDER_ID),
    ("name = :value AND llm_model_provider = 'openai'", SOURCE_PROVIDER_NAME),
    ("llm_model_provider = :value AND is_active = 1", "openai"),
)


def _source_api_key(conn) -> Optional[str]:
    """The encrypted OpenAI key to reuse, or None when the tenant has none"""
    for where, value in _KEY_LOOKUPS:
        key = conn.execute(sa.text(_KEY_OF.format(where=where)), {"value": value}).scalar()
        if key:
            return key
    return None


def _point_builder_at(conn, provider_id: str) -> None:
    """Set providerId on the agent node(s) of the Workflow Builder agent's workflow"""
    conn.execute(
        sa.text(
            """
            UPDATE workflows w
            SET nodes = (
                    SELECT COALESCE(
                        jsonb_agg(
                            CASE WHEN n->>'type' = 'agentNode'
                                 THEN jsonb_set(n, '{data,providerId}', to_jsonb(CAST(:provider_id AS text)))
                                 ELSE n END
                            ORDER BY ord),
                        CAST('[]' AS jsonb))
                    FROM jsonb_array_elements(w.nodes) WITH ORDINALITY AS t(n, ord)
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE w.is_deleted = 0
              AND jsonb_typeof(w.nodes) = 'array'
              AND w.id IN (
                    SELECT a.workflow_id FROM agents a
                    WHERE a.name = :agent_name AND a.is_deleted = 0 AND a.workflow_id IS NOT NULL
              )
            """
        ),
        {"provider_id": provider_id, "agent_name": AGENT_NAME},
    )


def upgrade() -> None:
    conn = op.get_bind()

    state = conn.execute(
        sa.text("SELECT is_deleted FROM llm_providers WHERE id = CAST(:id AS uuid)"), {"id": PROVIDER_ID}
    ).scalar()
    if state is None:
        key = _source_api_key(conn)
        if key is None:
            return  # no OpenAI key to reuse: the builder keeps the provider it has
        conn.execute(
            sa.text(
                """
                INSERT INTO llm_providers
                    (id, name, llm_model_provider, llm_model, connection_data,
                     is_active, is_default, is_deleted, created_at, updated_at)
                VALUES
                    (CAST(:id AS uuid), :name, 'openai', :model, jsonb_build_object('api_key', CAST(:key AS text)),
                     1, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"id": PROVIDER_ID, "name": PROVIDER_NAME, "model": PROVIDER_MODEL, "key": key},
        )
    elif state:
        # A downgrade soft-deleted it; bring the same row back on the current name and model.
        conn.execute(
            sa.text(
                "UPDATE llm_providers SET is_deleted = 0, is_active = 1, is_default = 0, name = :name, "
                "llm_model = :model, updated_at = CURRENT_TIMESTAMP WHERE id = CAST(:id AS uuid)"
            ),
            {"id": PROVIDER_ID, "name": PROVIDER_NAME, "model": PROVIDER_MODEL},
        )

    _point_builder_at(conn, PROVIDER_ID)


def downgrade() -> None:
    conn = op.get_bind()

    present = conn.execute(
        sa.text("SELECT 1 FROM llm_providers WHERE id = CAST(:id AS uuid) AND is_deleted = 0"),
        {"id": PROVIDER_ID},
    ).scalar()
    if not present:
        return

    source = conn.execute(
        sa.text("SELECT 1 FROM llm_providers WHERE id = CAST(:id AS uuid) AND is_deleted = 0"),
        {"id": SOURCE_PROVIDER_ID},
    ).scalar()
    if source:
        _point_builder_at(conn, SOURCE_PROVIDER_ID)
    # Otherwise the builder keeps pointing here and needs a provider picked by hand.

    # Soft delete: knowledge bases or analysts may reference the row by now.
    conn.execute(
        sa.text(
            "UPDATE llm_providers SET is_deleted = 1, is_default = 0, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {"id": PROVIDER_ID},
    )
