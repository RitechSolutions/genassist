"""
Database connection management utilities.

Provides reusable functions for managing database connections and request scopes
to optimize connection pool utilization.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi_injector import RequestScopeFactory
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_scope import get_tenant_context, set_tenant_context
from app.db.transaction_manager import TransactionManager
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


async def commit_scope_session(context: Optional[str] = None) -> None:
    """
    Commit the current scope's request-scoped session if it has an open transaction.

    Repositories flush instead of commit, so background/Celery/workflow scopes (which do
    not pass through the HTTP transaction middleware) must commit their own unit of work
    at the end of a successful scope. Safe to call when no session/transaction exists.
    """
    try:
        tx = injector.get(TransactionManager)
    except Exception as e:  # pylint: disable=broad-except
        logger.debug(f"No transaction manager to commit ({context}): {e}")
        return
    await tx.commit()


async def rollback_scope_session(context: Optional[str] = None) -> None:
    """Roll back the current scope's request-scoped session on error. Safe if none exists."""
    try:
        tx = injector.get(TransactionManager)
    except Exception as e:  # pylint: disable=broad-except
        logger.debug(f"No transaction manager to roll back ({context}): {e}")
        return
    try:
        await tx.rollback()
    except Exception as e:  # pylint: disable=broad-except
        logger.debug(f"Scope rollback skipped/failed ({context}): {e}")


async def release_db_connection(
    context: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> None:
    """
    Release a database connection back to the pool by committing any pending
    transaction or expiring all objects in the session.

    This function helps optimize connection pool utilization by releasing
    connections when they're not actively being used (e.g., during long-running
    LLM calls).

    Args:
        context: Optional context string for logging (e.g., conversation_id, agent_id)
        session: Optional AsyncSession instance. If not provided, will get from injector.

    Example:
        ```python
        # Release connection after DB reads, before LLM call
        await release_db_connection(context=f"conversation {conversation_id}")
        ```
    """
    if session is None:
        try:
            session = injector.get(AsyncSession)
        except Exception as e:
            logger.debug(f"Could not get session for connection release: {e}")
            return

    try:
        # Try to commit any pending transaction to release the connection
        await session.commit()
        log_msg = "Committed transaction to release DB connection"
        if context:
            log_msg += f" for {context}"
        logger.debug(log_msg)
    except Exception:
        # If commit fails (e.g., no active transaction), expire all objects
        # to detach them from the session, which helps release the connection
        try:
            session.expire_all()
            log_msg = "Expired all objects to release DB connection"
            if context:
                log_msg += f" for {context}"
            logger.debug(log_msg)
        except Exception as expire_error:
            logger.debug(f"Could not expire objects: {expire_error}")


@asynccontextmanager
async def create_tenant_request_scope() -> AsyncGenerator[None, None]:
    """
    Create a new request scope with tenant context preserved.

    This context manager creates a new request scope (which provides fresh
    dependency injection instances including a new DB session) while ensuring
    the tenant context is properly set. This is useful for isolating long-running
    operations that need their own DB connection.

    The tenant context is automatically obtained from the current context,
    ensuring multi-tenant isolation is maintained.

    Yields:
        None - use as async context manager

    Example:
        ```python
        async with create_tenant_request_scope():
            # Get fresh service instances with new session in the new scope
            service = injector.get(SomeService)
            result = await service.do_something()
        ```

    Note:
        The tenant context is automatically preserved from the current context.
        This ensures multi-tenant isolation is maintained without needing to
        explicitly pass tenant_id.
    """
    # Get current tenant context from the current scope
    tenant_id = get_tenant_context()

    # Get the request scope factory
    request_scope_factory = injector.get(RequestScopeFactory)

    # Create new scope and set tenant context
    async with request_scope_factory.create_scope():
        # Set tenant context in the new scope to ensure proper isolation
        set_tenant_context(tenant_id)
        try:
            yield
        except Exception:
            # Repos only flush; roll back this scope's pending writes on error.
            await rollback_scope_session(context="create_tenant_request_scope")
            raise
        else:
            # Commit the scope's unit of work (no-op if nothing was written).
            await commit_scope_session(context="create_tenant_request_scope")
        finally:
            # Session close is handled by the scope context manager.
            pass
