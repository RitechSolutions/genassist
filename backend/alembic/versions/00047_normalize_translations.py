"""normalize_translations

Revision ID: d2e3f4a5b6c7
Revises: 00044_disclaimer
Create Date: 2026-03-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "00044_disclaimer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create languages table
    op.create_table(
        "languages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint("id", name="languages_pk"),
        sa.UniqueConstraint("code"),
    )

    # 2. Create translation_keys table
    op.create_table(
        "translation_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint("id", name="translation_keys_pk"),
        sa.UniqueConstraint("key"),
    )

    # 3. Create translation_values table
    op.create_table(
        "translation_values",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("translation_key_id", sa.UUID(), nullable=False),
        sa.Column("language_id", sa.UUID(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint("id", name="translation_values_pk"),
        sa.ForeignKeyConstraint(
            ["translation_key_id"],
            ["translation_keys.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["language_id"],
            ["languages.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "translation_key_id", "language_id", name="uq_translation_key_language"
        ),
    )
    op.create_index("ix_translation_values_key_id", "translation_values", ["translation_key_id"])
    op.create_index("ix_translation_values_language_id", "translation_values", ["language_id"])

    # 4. Seed languages
    op.execute("""
        INSERT INTO languages (id, code, name, is_active, is_deleted, created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'en', 'English',    true, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'es', 'Spanish',    true, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'fr', 'French',     true, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'de', 'German',     true, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'pt', 'Portuguese', true, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (gen_random_uuid(), 'zh', 'Chinese',    true, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)

    # 5. Migrate data from old translations table to translation_keys
    op.execute("""
        INSERT INTO translation_keys (id, key, default_value, created_by, updated_by, created_at, updated_at, is_deleted)
        SELECT id, key, "default", created_by, updated_by, created_at, updated_at, is_deleted
        FROM translations
    """)

    # 6. Migrate language values for each language column
    for lang_code in ("en", "es", "fr", "de", "pt", "zh"):
        op.execute(f"""
            INSERT INTO translation_values (id, translation_key_id, language_id, value, created_at, updated_at, is_deleted)
            SELECT
                gen_random_uuid(),
                tk.id,
                lang.id,
                t.{lang_code},
                t.created_at,
                t.updated_at,
                t.is_deleted
            FROM translations t
            JOIN translation_keys tk ON tk.key = t.key
            JOIN languages lang ON lang.code = '{lang_code}'
            WHERE t.{lang_code} IS NOT NULL AND t.{lang_code} != ''
        """)

    # 7. Drop old translations table
    op.drop_table("translations")


def downgrade() -> None:
    # Recreate old translations table
    op.create_table(
        "translations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("default", sa.String(), nullable=True),
        sa.Column("en", sa.String(), nullable=True),
        sa.Column("es", sa.String(), nullable=True),
        sa.Column("fr", sa.String(), nullable=True),
        sa.Column("de", sa.String(), nullable=True),
        sa.Column("pt", sa.String(), nullable=True),
        sa.Column("zh", sa.String(), nullable=True),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint("id", name="translations_pk"),
        sa.UniqueConstraint("key"),
    )

    # Migrate data back: build flat rows from normalized tables
    op.execute("""
        INSERT INTO translations (id, key, "default", created_by, updated_by, created_at, updated_at, is_deleted)
        SELECT id, key, default_value, created_by, updated_by, created_at, updated_at, is_deleted
        FROM translation_keys
    """)

    for lang_code in ("en", "es", "fr", "de", "pt", "zh"):
        op.execute(f"""
            UPDATE translations t
            SET {lang_code} = tv.value
            FROM translation_values tv
            JOIN languages lang ON lang.id = tv.language_id
            WHERE tv.translation_key_id = t.id
              AND lang.code = '{lang_code}'
        """)

    # Drop normalized tables
    op.drop_table("translation_values")
    op.drop_table("translation_keys")
    op.drop_table("languages")
