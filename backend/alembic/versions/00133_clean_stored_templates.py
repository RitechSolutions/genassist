"""clean stored templates

Template cleaning now blanks every connection a block can hold, drops uploaded
files and their previews, and removes secret-looking names at any depth.
Cleans every template already stored, deleted ones included.
Safe to run again: a second run finds nothing to change.

Revision ID: 128a3e3e9968
Revises: bc71d6b34aec
Create Date: 2026-11-25 14:11:52.018511

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "128a3e3e9968"
down_revision: Union[str, None] = "bc71d6b34aec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEMPLATES = sa.text("SELECT id, graph FROM templates ORDER BY id")

_UPDATE_GRAPH = sa.text("UPDATE templates SET graph = :graph WHERE id = :id").bindparams(
    sa.bindparam("graph", type_=postgresql.JSONB)
)


def upgrade() -> None:
    from app.services.template_sanitizer import sanitize_template_graph

    bind = op.get_bind()
    engine_logger = logging.getLogger("sqlalchemy.engine")
    previous_level = engine_logger.level
    # Statement and row logging would write the removed values to the logs.
    engine_logger.setLevel(logging.WARNING)
    try:
        cleaned = 0
        for row in bind.execute(_TEMPLATES).all():
            graph = sanitize_template_graph(row.graph)
            if graph != row.graph:
                bind.execute(_UPDATE_GRAPH, {"graph": graph, "id": row.id})
                cleaned += 1
        logger.info("Cleaned %s stored templates", cleaned)
    finally:
        engine_logger.setLevel(previous_level)


def downgrade() -> None:
    # Nothing to undo: removed values are not kept anywhere.
    pass
