"""Request-scoped switches that decide whether a read may be served by the replica."""

from contextvars import ContextVar, Token

# Only HTTP request scopes are eligible. A websocket scope lives for the whole
# connection, so a session resolved there would hold a replica connection until
# the client disconnects. Defaults to False so anything unmarked uses the writer.
_replica_eligible: ContextVar[bool] = ContextVar("replica_reads_eligible", default=False)

# Set for a client that has just written, so it reads its own change back.
_pinned_to_writer: ContextVar[bool] = ContextVar("reads_pinned_to_writer", default=False)


def allow_replica_reads() -> Token:
    return _replica_eligible.set(True)


def reset_replica_reads(token: Token) -> None:
    _replica_eligible.reset(token)


def replica_reads_allowed() -> bool:
    return _replica_eligible.get()


def pin_reads_to_writer() -> Token:
    return _pinned_to_writer.set(True)


def unpin_reads(token: Token) -> None:
    _pinned_to_writer.reset(token)


def reads_pinned_to_writer() -> bool:
    return _pinned_to_writer.get()
