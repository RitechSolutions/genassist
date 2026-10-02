"""Tracks whether a session's current transaction has written anything."""

from sqlalchemy import event
from sqlalchemy.orm import Session

WROTE_IN_TRANSACTION = "wrote_in_transaction"


def session_has_writes(session) -> bool:
    """True when the current transaction flushed or executed a write, or holds pending changes."""
    if session.info.get(WROTE_IN_TRANSACTION):
        return True
    return bool(session.new or session.dirty or session.deleted)


def _takes_or_holds_a_lock(orm_execute_state) -> bool:
    # Raw text() statements cannot be inspected, so they count as writes; a locking
    # SELECT counts too, because ending the transaction would drop its row locks.
    if not orm_execute_state.is_select:
        return True
    return getattr(orm_execute_state.statement, "_for_update_arg", None) is not None


@event.listens_for(Session, "after_flush")
def _mark_flushed(session, flush_context):
    session.info[WROTE_IN_TRANSACTION] = True


@event.listens_for(Session, "do_orm_execute")
def _mark_statement_writes(orm_execute_state):
    if _takes_or_holds_a_lock(orm_execute_state):
        orm_execute_state.session.info[WROTE_IN_TRANSACTION] = True


@event.listens_for(Session, "after_transaction_end")
def _clear_when_transaction_ends(session, transaction):
    # The flag lives for the whole root transaction; a rolled-back savepoint keeps it,
    # which only errs towards holding the connection.
    if transaction.parent is None:
        session.info.pop(WROTE_IN_TRANSACTION, None)
