"""
Read-replica availability tracking.

A replica fault would otherwise turn every dashboard, analytics and conversation
list request into a 500 until someone unsets DB_READ_HOST and restarts. Instead the
first fault opens a short circuit, during which every read is served by the writer.
State is per process and clears by itself when the cooldown ends.

The failing query itself is not retried. Rerunning it on the request's own write
session would flush that request's pending writes early, hand ORM rows owned by the
write session to code that mutates them, and mask the replica fault behind whatever
the writer then raised.
"""

import logging
import time

from sqlalchemy.exc import DisconnectionError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# Connect-time faults. OSError covers refused connections, DNS failures and socket
# timeouts, which asyncpg raises without a SQLAlchemy wrapper; the rest are here for
# drivers that do wrap them.
FAILOVER_ERRORS = (InterfaceError, OperationalError, DisconnectionError, OSError)


def _is_replica_fault(error: BaseException) -> bool:
    """True when the replica is unusable, not when a query was merely slow or wrong.

    Load conditions must not divert traffic to the writer, because that is how a busy
    replica turns into writer overload. Verified against asyncpg: a mid-query
    disconnect sets ``connection_invalidated``, while a statement timeout, a bad
    statement and read pool exhaustion all leave it false.
    """
    if isinstance(error, FAILOVER_ERRORS):
        return True
    return bool(getattr(error, "connection_invalidated", False))


class ReplicaHealth:
    """Circuit breaker around the read replica, one per process."""

    def __init__(self):
        self._unavailable_until = 0.0

    def is_available(self) -> bool:
        return time.monotonic() >= self._unavailable_until

    def mark_failure(self, error: BaseException) -> None:
        cooldown = settings.DB_READ_FAILURE_COOLDOWN_SECONDS
        if cooldown <= 0:
            return
        was_available = self.is_available()
        self._unavailable_until = time.monotonic() + cooldown
        if was_available:
            logger.warning(
                "Read replica unavailable, serving reads from the writer for %ss: %s",
                cooldown,
                error,
            )

    def reset(self) -> None:
        self._unavailable_until = 0.0


replica_health = ReplicaHealth()


class ReplicaSession(AsyncSession):
    """Read session that reports replica faults so the next requests use the writer."""

    async def execute(self, *args, **kwargs):
        try:
            return await super().execute(*args, **kwargs)
        except Exception as error:
            if _is_replica_fault(error):
                replica_health.mark_failure(error)
            raise
