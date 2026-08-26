"""Unit tests for chat read receipts.

Three units are covered, all without a live database (SQL behaviour that needs
Postgres is left to full-stack tests, per the convention in this suite):

- ``_infer_read_receipt_role`` maps the authenticated principal's ``auth_mode`` to
  the reader role (a logged-in staff JWT is a supervisor read; a guest token or
  agent API key is a customer read).
- ``ConversationReadReceiptRepository.advance_read_marker`` builds a Postgres
  ``INSERT ... ON CONFLICT DO UPDATE`` whose ``WHERE`` clause refuses to move a
  reader's marker backwards (monotonic). We assert the guard is present on the
  compiled statement rather than round-tripping through a database.
- ``ConversationService.mark_conversation_read`` clamps the requested sequence to
  the conversation's newest message and never writes a marker for an empty
  conversation — so a client can't mark past the end.
"""

import re
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from starlette_context import context, request_cycle_context

from app.api.v1.routes.conversations import _infer_read_receipt_role
from app.core.utils.enums.reader_role_enum import ReaderRole
from app.repositories.conversation_read_receipt import ConversationReadReceiptRepository
from app.repositories.transcript_message import TranscriptMessageRepository
from app.services.conversations import ConversationService


# --------------------------------------------------------------------------- #
# _infer_read_receipt_role — role derived from auth_mode, never trusted client-side
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "auth_mode, expected",
    [
        ("token", ReaderRole.SUPERVISOR.value),  # logged-in staff JWT (agent console)
        ("guest_token", ReaderRole.CUSTOMER.value),  # embedded widget visitor
        ("api_key", ReaderRole.CUSTOMER.value),  # legacy agent API key
        ("something_else", ReaderRole.CUSTOMER.value),  # unknown → customer (safe default)
    ],
)
def test_infer_read_receipt_role_per_auth_mode(auth_mode, expected):
    with request_cycle_context():
        context["auth_mode"] = auth_mode
        assert _infer_read_receipt_role() == expected


def test_infer_read_receipt_role_defaults_to_customer_without_context():
    # No starlette_context / no auth_mode set → treated as the visitor, never supervisor.
    assert _infer_read_receipt_role() == ReaderRole.CUSTOMER.value


def test_infer_read_receipt_role_only_token_is_supervisor():
    for auth_mode in ("guest_token", "api_key", "", None):
        with request_cycle_context():
            if auth_mode is not None:
                context["auth_mode"] = auth_mode
            assert _infer_read_receipt_role() != ReaderRole.SUPERVISOR.value


# --------------------------------------------------------------------------- #
# advance_read_marker — the upsert refuses to regress (monotonic WHERE guard)
# --------------------------------------------------------------------------- #
class _SpySession:
    """Captures executed statements without touching a database."""

    def __init__(self):
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)

    async def commit(self):
        pass

    async def flush(self):
        pass


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_advance_read_marker_upsert_refuses_to_regress():
    session = _SpySession()
    repo = ConversationReadReceiptRepository(session)

    await repo.advance_read_marker(
        conversation_id=uuid4(),
        reader_role=ReaderRole.SUPERVISOR.value,
        reader_user_id=uuid4(),
        last_read_sequence=7,
    )

    assert len(session.executed) == 1
    sql = _compile(session.executed[0])

    # Single atomic upsert keyed on the (conversation, reader_role) uniqueness.
    assert "ON CONFLICT" in sql.upper()
    assert "DO UPDATE" in sql.upper()
    assert "uq_conversation_read_receipts_conversation_role" in sql
    # The monotonic guard: only overwrite when the incoming sequence is greater,
    # so a stale/out-of-order read can never move the marker backwards.
    assert re.search(
        r"WHERE\s+conversation_read_receipts\.last_read_sequence\s*<", sql, re.IGNORECASE
    ), sql


@pytest.mark.asyncio
async def test_advance_read_marker_flushes_once():
    # Repositories flush; the request/task transaction boundary owns the commit.
    session = _SpySession()
    session.flush = AsyncMock()
    repo = ConversationReadReceiptRepository(session)

    await repo.advance_read_marker(
        conversation_id=uuid4(),
        reader_role=ReaderRole.CUSTOMER.value,
        reader_user_id=None,
        last_read_sequence=0,
    )

    session.flush.assert_awaited_once()


# --------------------------------------------------------------------------- #
# mark_conversation_read — clamp to the newest message; never mark past the end
# --------------------------------------------------------------------------- #
def _build_service(*, latest_sequence: int):
    """A ConversationService whose repos are mocked; only the read-receipt path
    is exercised. ``latest_sequence`` is what the transcript repo reports as the
    conversation's newest message sequence."""
    conversation_repo = AsyncMock()
    conversation_repo.fetch_conversation_by_id.return_value = MagicMock()  # truthy = exists

    transcript_repo = AsyncMock(spec=TranscriptMessageRepository)
    transcript_repo.get_latest_sequence_number.return_value = latest_sequence

    receipt_repo = AsyncMock(spec=ConversationReadReceiptRepository)
    receipt_repo.get_by_conversation.return_value = []  # empty aggregate state

    service = ConversationService(
        operator_statistics_service=MagicMock(),
        conversation_repo=conversation_repo,
        transcript_message_repo=transcript_repo,
        audit_log_repo=AsyncMock(),
        recordings_repo=AsyncMock(),
        conversation_read_receipt_repo=receipt_repo,
        thread_rag=MagicMock(),
        gpt_kpi_analyzer_service=MagicMock(),
        conversation_analysis_service=MagicMock(),
        llm_analyst_service=MagicMock(),
    )
    return service, receipt_repo


@pytest.mark.asyncio
async def test_mark_conversation_read_clamps_to_latest_sequence():
    service, receipt_repo = _build_service(latest_sequence=3)

    await service.mark_conversation_read(
        conversation_id=uuid4(),
        reader_role=ReaderRole.SUPERVISOR.value,
        reader_user_id=uuid4(),
        last_read_sequence=2_147_483_647,  # "read everything" sentinel
    )

    receipt_repo.advance_read_marker.assert_awaited_once()
    assert receipt_repo.advance_read_marker.await_args.kwargs["last_read_sequence"] == 3


@pytest.mark.asyncio
async def test_mark_conversation_read_keeps_lower_requested_sequence():
    service, receipt_repo = _build_service(latest_sequence=10)

    await service.mark_conversation_read(
        conversation_id=uuid4(),
        reader_role=ReaderRole.CUSTOMER.value,
        reader_user_id=None,
        last_read_sequence=4,
    )

    assert receipt_repo.advance_read_marker.await_args.kwargs["last_read_sequence"] == 4


@pytest.mark.asyncio
async def test_mark_conversation_read_skips_write_for_empty_conversation():
    # No messages yet → latest sequence is -1, so the clamped value is < 0 and no
    # marker is written (nothing to have "read").
    service, receipt_repo = _build_service(latest_sequence=-1)

    state = await service.mark_conversation_read(
        conversation_id=uuid4(),
        reader_role=ReaderRole.CUSTOMER.value,
        reader_user_id=None,
        last_read_sequence=5,
    )

    receipt_repo.advance_read_marker.assert_not_awaited()
    # Still returns an aggregate state (all markers unset) rather than raising.
    assert state.customer_last_read_sequence is None
    assert state.supervisor_last_read_sequence is None
