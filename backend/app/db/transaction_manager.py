"""
Service-layer transaction management.

Repositories now `flush()` instead of `commit()`, so the transaction boundary is
owned above them:

* HTTP requests  -> `TransactionMiddleware` commits on success / rolls back on error.
* Background/Celery/seeding -> the request-scope helpers commit/roll back around the
  task body (see `app/core/utils/db_connection_utils.py`).

`TransactionManager` is the injectable, request-scoped handle to that boundary. The
middleware / task boundary call :meth:`commit` and :meth:`rollback`; services that need
an *explicit* unit of work (e.g. a multi-write operation that must persist immediately,
or that wants its own partial-rollback scope) use the :meth:`transaction` context
manager. When a transaction is already open on the session, :meth:`transaction` uses a
SAVEPOINT (``begin_nested``) so it composes with the outer request boundary instead of
committing the whole request early.
"""

import logging
from contextlib import asynccontextmanager

from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@inject
class TransactionManager:
    """Owns the commit/rollback boundary for the shared request-scoped session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def commit(self) -> None:
        """Commit the current transaction if one is in progress."""
        if self.db.in_transaction():
            await self.db.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction if one is in progress."""
        if self.db.in_transaction():
            await self.db.rollback()

    @asynccontextmanager
    async def transaction(self):
        """
        Explicit unit of work.

        * If no transaction is active, open one and commit it on success.
        * If a transaction is already active (the common case inside an HTTP request),
          open a SAVEPOINT so this block can roll back on its own without discarding
          the surrounding request's pending writes; the outer boundary still owns the
          final commit.

        On any exception the (nested) transaction is rolled back and the error re-raised.
        """
        if self.db.in_transaction():
            # Nested unit of work -> SAVEPOINT. begin_nested() manages
            # release/rollback of the savepoint on block exit.
            async with self.db.begin_nested():
                yield
        else:
            # Top-level unit of work (e.g. a background task that opts in explicitly).
            async with self.db.begin():
                yield
