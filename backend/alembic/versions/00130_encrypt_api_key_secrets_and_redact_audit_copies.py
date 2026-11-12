"""encrypt api key secrets and redact audit copies

API keys that were created, rotated or revealed were saved unencrypted, and the
audit log kept a copy. Encrypts every row that still stores its own raw secret
and replaces key_val in past api_keys Update audit entries with "[REDACTED]".
Safe to run again: a second run finds nothing to change.

Revision ID: 242b618b4766
Revises: 9c4e1f7a2b6d
Create Date: 2026-11-12 13:17:02.382745
"""

import hashlib
import json
import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "242b618b4766"
down_revision: Union[str, None] = "9c4e1f7a2b6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KEY_VAL_MAX_LENGTH = 255
_REDACTED_CHANGE = {"old": "[REDACTED]", "new": "[REDACTED]"}

_KEYS = sa.text(
    """
    SELECT id, key_val, hashed_value
    FROM api_keys
    WHERE key_val IS NOT NULL
      AND hashed_value IS NOT NULL
    ORDER BY id
    """
)

_ENCRYPT_KEY = sa.text(
    "UPDATE api_keys SET key_val = :encrypted WHERE id = :id AND hashed_value = :hashed_value"
)

_KEY_VAL_AUDIT_ROWS = sa.text(
    """
    SELECT audit.id, audit.json_changes
    FROM api_keys AS api_key
    JOIN audit_log AS audit
      ON audit.record_id = api_key.id
     AND audit.table_name = 'api_keys'
    WHERE audit.action_name = 'Update'
      AND audit.json_changes LIKE '%"key_val"%'
    ORDER BY audit.id
    """
)

_REDACT_AUDIT_ROW = sa.text("UPDATE audit_log SET json_changes = :json_changes WHERE id = :id")


def _encrypt_plaintext_keys(bind) -> None:
    from app.core.utils.encryption_utils import encrypt_key

    encrypted = changed_meanwhile = too_long = 0
    for row in bind.execute(_KEYS).all():
        # Same hash as hash_api_key: only a row that stores its own raw secret matches.
        if hashlib.sha256(row.key_val.encode()).hexdigest() != row.hashed_value:
            continue
        token = encrypt_key(row.key_val)
        if len(token) > _KEY_VAL_MAX_LENGTH:
            too_long += 1
            continue
        updated = bind.execute(
            _ENCRYPT_KEY, {"encrypted": token, "id": row.id, "hashed_value": row.hashed_value}
        ).rowcount
        if updated:
            encrypted += 1
        else:
            changed_meanwhile += 1

    logger.info(
        "Encrypted %s plaintext API key secrets (%s changed meanwhile, %s too long to encrypt)",
        encrypted,
        changed_meanwhile,
        too_long,
    )


def _redact_audit_key_values(bind) -> None:
    redacted = 0
    unreadable: list[int] = []
    for row in bind.execute(_KEY_VAL_AUDIT_ROWS).all():
        try:
            changes = json.loads(row.json_changes)
        except ValueError:
            unreadable.append(row.id)
            continue
        if not isinstance(changes, dict):
            unreadable.append(row.id)
            continue
        if changes.get("key_val", _REDACTED_CHANGE) == _REDACTED_CHANGE:
            continue
        changes["key_val"] = _REDACTED_CHANGE
        bind.execute(_REDACT_AUDIT_ROW, {"json_changes": json.dumps(changes), "id": row.id})
        redacted += 1

    logger.info("Redacted key_val in %s API key audit entries", redacted)
    if unreadable:
        logger.warning(
            "Left %s API key audit entries as they are, their changes could not be read: ids %s",
            len(unreadable),
            unreadable,
        )


def upgrade() -> None:
    bind = op.get_bind()
    engine_logger = logging.getLogger("sqlalchemy.engine")
    previous_level = engine_logger.level
    # Statement and row logging would write the raw secrets to the logs.
    engine_logger.setLevel(logging.WARNING)
    try:
        _encrypt_plaintext_keys(bind)
        _redact_audit_key_values(bind)
    finally:
        engine_logger.setLevel(previous_level)


def downgrade() -> None:
    # Nothing to undo: secrets never go back to plain text, and the old code reads encrypted values.
    pass
