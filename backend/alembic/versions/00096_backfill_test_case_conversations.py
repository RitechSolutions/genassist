"""backfill_test_case_conversations

Recovers the source conversation of previously imported test cases.

A suite's imported cases are treated as one cluster and linked only when exactly
one live conversation yields precisely the same ordered question/answer exchanges,
rebuilt with the same speaker roles and message order the importer used. Anything
ambiguous, partial or unmatched stays null and is logged for manual review; no
synthetic conversation id is ever stored.

Revision ID: 8b2f5c31d740
Revises: 4e1c7a9d2b05
Create Date: 2026-07-20 10:30:00.000000

"""

import logging
from typing import Any, List, Sequence, Tuple, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b2f5c31d740"
down_revision: Union[str, None] = "4e1c7a9d2b05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Frozen copies of the importer's speaker roles: this migration must keep matching
# the data as it was written, even if the application constants later change.
_CUSTOMER_SPEAKERS = {"customer", "user"}
_AGENT_SPEAKERS = {"agent", "assistant", "bot"}

_IMPORTED_CASES = sa.text(
    """
    SELECT id,
           input_data->>'message' AS message,
           expected_output->>'value' AS answer
    FROM test_cases
    WHERE suite_id = :suite_id
      AND is_deleted = 0
      AND tags @> '["imported"]'::jsonb
    ORDER BY created_at, id
    """
)

# Live conversations whose live messages include this text from a customer.
_CANDIDATE_CONVERSATIONS = sa.text(
    """
    SELECT DISTINCT message.conversation_id
    FROM transcript_messages AS message
    JOIN conversations AS conversation
      ON conversation.id = message.conversation_id
     AND conversation.is_deleted = 0
    WHERE message.is_deleted = 0
      AND message.text = :question
      AND lower(message.speaker) = ANY(:customer_speakers)
    """
)

_CONVERSATION_MESSAGES = sa.text(
    """
    SELECT speaker, text
    FROM transcript_messages
    WHERE conversation_id = :conversation_id
      AND is_deleted = 0
    ORDER BY sequence_number
    """
)


def _exchanges_of(bind, conversation_id: Any) -> List[Tuple[str, str]]:
    """Rebuild a conversation's ordered question/answer pairs, as the importer did."""
    rows = bind.execute(
        _CONVERSATION_MESSAGES, {"conversation_id": conversation_id}
    ).all()

    exchanges: List[Tuple[str, str]] = []
    pending_question: str | None = None
    for row in rows:
        speaker = (row.speaker or "").lower()
        if speaker in _CUSTOMER_SPEAKERS:
            pending_question = row.text
        elif speaker in _AGENT_SPEAKERS and pending_question is not None:
            exchanges.append((pending_question, row.text))
            pending_question = None
    return exchanges


def upgrade() -> None:
    bind = op.get_bind()

    suite_ids = bind.execute(
        sa.text(
            """
            SELECT DISTINCT suite_id
            FROM test_cases
            WHERE is_deleted = 0
              AND source_conversation_id IS NULL
              AND tags @> '["imported"]'::jsonb
            """
        )
    ).scalars().all()

    linked = 0
    skipped: list[tuple[str, str]] = []

    for suite_id in suite_ids:
        cases = bind.execute(_IMPORTED_CASES, {"suite_id": suite_id}).all()
        cluster = [(case.message, case.answer) for case in cases]

        if not cluster or not all(question and answer for question, answer in cluster):
            skipped.append((str(suite_id), "cluster has an incomplete exchange"))
            continue

        candidate_ids = bind.execute(
            _CANDIDATE_CONVERSATIONS,
            {"question": cluster[0][0], "customer_speakers": list(_CUSTOMER_SPEAKERS)},
        ).scalars().all()

        matches = [
            candidate_id
            for candidate_id in candidate_ids
            if _exchanges_of(bind, candidate_id) == cluster
        ]

        if len(matches) != 1:
            skipped.append(
                (
                    str(suite_id),
                    f"{len(matches)} conversations reproduce the cluster exactly",
                )
            )
            continue

        # Turn order comes from the transcript rebuild, not from row creation order.
        for turn_index, case in enumerate(cases):
            bind.execute(
                sa.text(
                    """
                    UPDATE test_cases
                    SET source_conversation_id = :conversation_id, turn_index = :turn_index
                    WHERE id = :case_id
                    """
                ),
                {
                    "conversation_id": matches[0],
                    "turn_index": turn_index,
                    "case_id": case.id,
                },
            )
        linked += len(cases)

    logger.info("Linked %s imported cases to their source conversation", linked)
    for suite_id, reason in skipped:
        logger.warning(
            "Suite %s left unlinked for manual review: %s", suite_id, reason
        )


def downgrade() -> None:
    """Deliberately a no-op.

    Clearing the columns cannot distinguish values recovered here from those the
    importer set for real imports, and the latter are unrecoverable. The preceding
    migration drops both columns, so nothing is left behind either way.
    """
