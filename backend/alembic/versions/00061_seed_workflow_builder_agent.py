"""seed_workflow_builder_agent

Revision ID: b3c4d5e6f7a8
Revises: e8f9a0b1c2d3
Create Date: 2026-03-11 12:00:00.000000

"""

import hashlib
import json
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AGENT_NAME = "Workflow Builder"
KB_NAME = "Workflow Node Specifications"
KB_EXAMPLES_NAME = "Workflow Examples"
API_KEY_RAW = "workflow_builder_123"


def upgrade() -> None:
    conn = op.get_bind()

    # ── Guard: skip if agent already exists ──
    existing = conn.execute(
        sa.text("SELECT id FROM agents WHERE name = :name"),
        {"name": AGENT_NAME},
    ).fetchone()
    if existing:
        return

    # ── 1. Create Knowledge Base ──
    seed_dir = Path(__file__).resolve().parent.parent.parent / "app" / "db" / "seed"
    specs_path = seed_dir / "knowledge" / "node_specs.md"
    kb_content = specs_path.read_text(encoding="utf-8") if specs_path.exists() else ""

    conn.execute(sa.text("""
        INSERT INTO knowledge_bases (id, name, description, type, source, content, file_type, files, rag_config, extra_metadata, is_deleted, created_at, updated_at)
        VALUES (
            gen_random_uuid(), :name, :description, 'text', 'internal', :content,
            'text', CAST('[]' AS jsonb), CAST('{}' AS jsonb), CAST('{}' AS jsonb), 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """), {
        "name": KB_NAME,
        "description": "Comprehensive documentation of all GenAssist workflow node types, their configurations, handlers, and usage patterns.",
        "content": kb_content,
    })

    kb_id = conn.execute(
        sa.text("SELECT id FROM knowledge_bases WHERE name = :name"),
        {"name": KB_NAME},
    ).scalar()

    # ── 1b. Create Workflow Examples Knowledge Base ──
    examples_path = seed_dir / "knowledge" / "workflow_examples.md"
    examples_content = examples_path.read_text(encoding="utf-8") if examples_path.exists() else ""

    conn.execute(sa.text("""
        INSERT INTO knowledge_bases (id, name, description, type, source, content, file_type, files, rag_config, extra_metadata, is_deleted, created_at, updated_at)
        VALUES (
            gen_random_uuid(), :name, :description, 'text', 'internal', :content,
            'text', CAST('[]' AS jsonb), CAST('{}' AS jsonb), CAST('{}' AS jsonb), 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """), {
        "name": KB_EXAMPLES_NAME,
        "description": "Curated correct workflow examples for common use cases including chatbots, KB integrations, routing, guardrails, and multi-tool agents.",
        "content": examples_content,
    })

    kb_examples_id = conn.execute(
        sa.text("SELECT id FROM knowledge_bases WHERE name = :name"),
        {"name": KB_EXAMPLES_NAME},
    ).scalar()

    # ── 2. Create Workflow ──
    wf_json_path = seed_dir / "workflow_builder_wf_data.json"
    wf_raw = wf_json_path.read_text(encoding="utf-8")

    # Replace placeholders
    wf_raw = wf_raw.replace("KB_ID_LIST", f'"{kb_id}"')
    wf_raw = wf_raw.replace("WORKFLOW_EXAMPLES_KB_ID", f'"{kb_examples_id}"')
    wf_raw = wf_raw.replace('"LLM_PROVIDER_ID"', "null")

    wf_data = json.loads(wf_raw)
    wf_nodes = json.dumps(wf_data["nodes"])
    wf_edges = json.dumps(wf_data["edges"])
    wf_exec_state = json.dumps(wf_data.get("executionState", {"source": "", "session": {"message": ""}, "nodeOutputs": {}}))

    conn.execute(sa.text("""
        INSERT INTO workflows (id, name, description, nodes, edges, "executionState", "testInput", version, is_deleted, created_at, updated_at)
        VALUES (
            gen_random_uuid(), :name, :description, CAST(:nodes AS jsonb), CAST(:edges AS jsonb),
            CAST(:exec_state AS jsonb), CAST('{}' AS jsonb), '1.0', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """), {
        "name": "Workflow Builder Agent",
        "description": "AI agent that creates workflows from natural language descriptions",
        "nodes": wf_nodes,
        "edges": wf_edges,
        "exec_state": wf_exec_state,
    })

    workflow_id = conn.execute(
        sa.text("SELECT id FROM workflows WHERE name = 'Workflow Builder Agent' ORDER BY created_at DESC LIMIT 1")
    ).scalar()

    # ── 3. Create User for Operator ──
    console_type_id = conn.execute(
        sa.text("SELECT id FROM user_types WHERE name = 'console'")
    ).scalar()

    if not console_type_id:
        # Fallback: use any existing user type
        console_type_id = conn.execute(
            sa.text("SELECT id FROM user_types LIMIT 1")
        ).scalar()

    conn.execute(sa.text("""
        INSERT INTO users (id, username, email, hashed_password, is_active, user_type_id, force_upd_pass_date, is_deleted, created_at, updated_at)
        VALUES (
            gen_random_uuid(), :username, :email,
            '$2b$12$placeholder_hash_workflow_builder_agent_00000000',
            1, :user_type_id, CURRENT_TIMESTAMP + INTERVAL '3 years', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """), {
        "username": "workflow_builder_agent",
        "email": "workflow_builder@genassist.ritech.io",
        "user_type_id": console_type_id,
    })

    user_id = conn.execute(
        sa.text("SELECT id FROM users WHERE username = 'workflow_builder_agent'")
    ).scalar()

    # ── 4. Create Operator Statistics ──
    conn.execute(sa.text("""
        INSERT INTO operator_statistics (id, avg_positive_sentiment, avg_negative_sentiment, avg_neutral_sentiment, call_count, total_duration, score, is_deleted, created_at, updated_at)
        VALUES (gen_random_uuid(), 0, 0, 0, 0, 0, 0.0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """))

    stats_id = conn.execute(
        sa.text("SELECT id FROM operator_statistics ORDER BY created_at DESC LIMIT 1")
    ).scalar()

    # ── 5. Create Operator ──
    conn.execute(sa.text("""
        INSERT INTO operators (id, first_name, last_name, is_active, statistics_id, user_id, is_deleted, created_at, updated_at)
        VALUES (gen_random_uuid(), :first_name, 'ai_agent', 1, :stats_id, :user_id, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {
        "first_name": AGENT_NAME,
        "stats_id": stats_id,
        "user_id": user_id,
    })

    operator_id = conn.execute(
        sa.text("SELECT id FROM operators WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).scalar()

    # ── 6. Create Agent ──
    thinking_phrases = ";".join([
        "Understanding your use case...",
        "Thinking about the best architecture...",
        "Researching the right nodes...",
        "Designing your workflow...",
        "Putting the pieces together...",
        "Almost there, fine-tuning the details...",
    ])

    conn.execute(sa.text("""
        INSERT INTO agents (id, name, description, is_active, operator_id, workflow_id, welcome_message, welcome_title, possible_queries, thinking_phrases, is_deleted, created_at, updated_at)
        VALUES (
            gen_random_uuid(), :name, :description, 1, :operator_id, :workflow_id,
            :welcome_message, :welcome_title, :possible_queries, :thinking_phrases, 0,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """), {
        "name": AGENT_NAME,
        "description": "Conversational AI agent that understands user needs and creates GenAssist workflows",
        "operator_id": operator_id,
        "workflow_id": workflow_id,
        "welcome_message": "Hi! I'm your workflow architect. Tell me what you'd like to build and I'll design the perfect agent for you.",
        "welcome_title": "What would you like your agent to do?",
        "possible_queries": "Build a customer support chatbot;Create an email automation workflow;Design a data pipeline with Jira integration",
        "thinking_phrases": thinking_phrases,
    })

    agent_id = conn.execute(
        sa.text("SELECT id FROM agents WHERE name = :name"),
        {"name": AGENT_NAME},
    ).scalar()

    # ── 7. Link workflow back to agent ──
    conn.execute(sa.text("""
        UPDATE workflows SET agent_id = :agent_id, user_id = (SELECT id FROM users WHERE username = 'admin' LIMIT 1)
        WHERE id = :workflow_id
    """), {"agent_id": agent_id, "workflow_id": workflow_id})

    # ── 8. Create security settings (defaults) ──
    conn.execute(sa.text("""
        INSERT INTO agent_security_settings (id, agent_id, token_based_auth, is_deleted, created_at, updated_at)
        VALUES (gen_random_uuid(), :agent_id, false, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {"agent_id": agent_id})

    # ── 9. Assign 'ai agent' role to operator user ──
    agent_role_id = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'ai agent'")
    ).scalar()

    if agent_role_id:
        conn.execute(sa.text("""
            INSERT INTO user_roles (id, user_id, role_id, is_deleted, created_at, updated_at)
            VALUES (gen_random_uuid(), :user_id, :role_id, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {"user_id": user_id, "role_id": agent_role_id})

    # ── 10. Create API key ──
    try:
        from app.core.utils.encryption_utils import encrypt_key
        encrypted_key = encrypt_key(API_KEY_RAW)
    except Exception:
        encrypted_key = API_KEY_RAW  # fallback if encryption not available

    hashed_key = hashlib.sha256(API_KEY_RAW.encode()).hexdigest()

    conn.execute(sa.text("""
        INSERT INTO api_keys (id, name, key_val, hashed_value, is_active, user_id, is_deleted, created_at, updated_at)
        VALUES (gen_random_uuid(), :name, :key_val, :hashed_value, 1, :user_id, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {
        "name": "workflow-builder default key",
        "key_val": encrypted_key,
        "hashed_value": hashed_key,
        "user_id": user_id,
    })

    api_key_id = conn.execute(
        sa.text("SELECT id FROM api_keys WHERE name = 'workflow-builder default key'")
    ).scalar()

    if agent_role_id and api_key_id:
        conn.execute(sa.text("""
            INSERT INTO api_key_roles (id, api_key_id, role_id, is_deleted, created_at, updated_at)
            VALUES (gen_random_uuid(), :api_key_id, :role_id, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {"api_key_id": api_key_id, "role_id": agent_role_id})


def downgrade() -> None:
    conn = op.get_bind()

    agent_id = conn.execute(
        sa.text("SELECT id FROM agents WHERE name = :name"),
        {"name": AGENT_NAME},
    ).scalar()

    if not agent_id:
        return

    # Get related IDs
    row = conn.execute(sa.text("""
        SELECT a.operator_id, a.workflow_id, o.user_id
        FROM agents a JOIN operators o ON o.id = a.operator_id
        WHERE a.id = :agent_id
    """), {"agent_id": agent_id}).fetchone()

    if not row:
        return

    operator_id, workflow_id, user_id = row

    # Fetch statistics_id before deleting operator
    stats_id = conn.execute(
        sa.text("SELECT statistics_id FROM operators WHERE id = :operator_id"),
        {"operator_id": operator_id},
    ).scalar()

    # Delete in reverse order (children before parents)
    conn.execute(sa.text("DELETE FROM api_key_roles WHERE api_key_id IN (SELECT id FROM api_keys WHERE name = 'workflow-builder default key')"))
    conn.execute(sa.text("DELETE FROM api_keys WHERE name = 'workflow-builder default key'"))
    conn.execute(sa.text("DELETE FROM user_roles WHERE user_id = :user_id"), {"user_id": user_id})
    conn.execute(sa.text("DELETE FROM agent_security_settings WHERE agent_id = :agent_id"), {"agent_id": agent_id})
    conn.execute(sa.text("DELETE FROM conversation_analysis WHERE conversation_id IN (SELECT id FROM conversations WHERE operator_id = :operator_id)"), {"operator_id": operator_id})
    conn.execute(sa.text("DELETE FROM conversations WHERE operator_id = :operator_id"), {"operator_id": operator_id})
    conn.execute(sa.text("DELETE FROM agents WHERE id = :agent_id"), {"agent_id": agent_id})
    conn.execute(sa.text("DELETE FROM operators WHERE id = :operator_id"), {"operator_id": operator_id})
    if stats_id:
        conn.execute(sa.text("DELETE FROM operator_statistics WHERE id = :stats_id"), {"stats_id": stats_id})
    conn.execute(sa.text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
    conn.execute(sa.text("DELETE FROM workflows WHERE id = :workflow_id"), {"workflow_id": workflow_id})
    conn.execute(sa.text("DELETE FROM knowledge_bases WHERE name = :name"), {"name": KB_NAME})
    conn.execute(sa.text("DELETE FROM knowledge_bases WHERE name = :name"), {"name": KB_EXAMPLES_NAME})
