"""
Request-scoped database transaction boundary.

Repositories `flush()` rather than `commit()`, so the commit/rollback decision is made
once per request here instead of piecemeal inside each repository:

* 2xx/3xx response  -> commit the request's pending writes.
* >=4xx response     -> roll back (covers ``AppException`` handlers, which turn into an
  error response *before* this middleware sees it, so no exception propagates).
* unhandled exception -> roll back and re-raise.

This middleware runs inside the fastapi-injector request scope (``InjectorMiddleware`` is
the outermost user middleware), so ``injector.get`` resolves the same request-scoped
``AsyncSession`` the repositories used. Session *close* is still handled by
fastapi-injector's ``enable_cleanup`` at scope exit; we only own commit/rollback.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db.transaction_manager import TransactionManager
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


class TransactionMiddleware(BaseHTTPMiddleware):
    """Commit on success / roll back on error for the request-scoped session."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            # Unhandled error escaped the endpoint -> discard all pending writes.
            await self._rollback()
            raise

        # AppException & friends are already converted to an error Response by the
        # inner ExceptionMiddleware, so decide by status code rather than exception.
        if response.status_code < 400:
            await self._commit()
        else:
            await self._rollback()
        return response

    async def _commit(self) -> None:
        tx = self._get_transaction_manager()
        if tx is not None:
            try:
                await tx.commit()
            except Exception:  # pylint: disable=broad-except
                # A failed commit must not leak a half-open transaction to the next
                # user of this (pooled) connection.
                await self._safe_rollback(tx)
                raise

    async def _rollback(self) -> None:
        tx = self._get_transaction_manager()
        if tx is not None:
            await self._safe_rollback(tx)

    @staticmethod
    async def _safe_rollback(tx: TransactionManager) -> None:
        try:
            await tx.rollback()
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(f"Transaction rollback skipped/failed: {exc}")

    @staticmethod
    def _get_transaction_manager() -> TransactionManager | None:
        """Resolve the request-scoped TransactionManager, or None if unavailable.

        Resolving this also resolves the request session; a session that never ran a
        query holds no connection and no transaction, so commit/rollback are no-ops.
        """
        try:
            return injector.get(TransactionManager)
        except Exception as exc:  # pylint: disable=broad-except
            # No active request scope / session (e.g. very early failures) - nothing to do.
            logger.debug(f"No transaction manager for request: {exc}")
            return None
