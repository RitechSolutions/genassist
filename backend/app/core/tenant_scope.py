"""
Custom tenant-aware scope for dependency injection
"""

from injector import ScopeDecorator
import logging
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Type, TypeVar

from injector import Provider, Scope, InstanceProvider

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Context variable to store the current tenant ID
_tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id")


class TenantScope(Scope):
    """
    A scope that provides tenant-aware instances.
    Each tenant gets its own cached instances.
    """

    def configure(self) -> None:
        self._tenant_cache: Dict[str, Dict[Type, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Type[T], provider: Provider[T]) -> Provider[T]:
        try:
            tenant_id = _tenant_id_ctx.get()
        except LookupError:
            # No tenant context, use default provider
            logger.debug(
                f"TenantScope: No tenant context for {key.__name__}, using default provider"
            )
            return provider

        with self._lock:
            if tenant_id not in self._tenant_cache:
                self._tenant_cache[tenant_id] = {}

            tenant_cache = self._tenant_cache[tenant_id]

            if key not in tenant_cache:
                # Create instance for this tenant
                instance = provider.get(self.injector)
                tenant_cache[key] = InstanceProvider(instance)
                logger.debug(
                    f"TenantScope: Created instance for tenant {tenant_id} and key {key.__name__}"
                )

            return tenant_cache[key]


# Scope decorator for easy use
tenant_scope = ScopeDecorator(TenantScope)


def set_tenant_context(tenant_id: str) -> None:
    """Set the tenant ID in the current context"""
    _tenant_id_ctx.set(tenant_id)
    logger.debug(f"Set tenant context: {tenant_id}")


def get_tenant_context() -> str:
    """Get the current tenant ID from context.

    Lenient accessor: falls back to ``"master"`` when no context is set. Use for
    non-isolation-critical purposes (cache-key prefixes, storage paths, logging).
    For paths that route a database session, use :func:`require_tenant_context`
    instead so a missing context fails closed rather than silently hitting master.
    """
    try:
        tenant_id = _tenant_id_ctx.get()
        # Return None if tenant_id is None (explicitly set)
        return tenant_id if tenant_id is not None else "master"
    except LookupError:
        return "master"


class TenantContextError(RuntimeError):
    """Raised when a tenant-scoped operation runs without an explicit tenant context."""


def require_tenant_context() -> str:
    """Strict, fail-closed accessor for isolation-critical paths (DB routing).

    Unlike :func:`get_tenant_context`, this raises when no tenant context has been
    explicitly set, instead of silently defaulting to the master database. Callers
    that genuinely intend the master DB must opt in explicitly via
    ``set_tenant_context("master")`` or ``clear_tenant_context()`` (both of which
    set the context to ``"master"``, so they satisfy this check).
    """
    try:
        tenant_id = _tenant_id_ctx.get()
    except LookupError:
        raise TenantContextError(
            "No tenant context set for a tenant-scoped DB operation. Callers that "
            'intend the master database must set it explicitly (set_tenant_context("master") '
            "or clear_tenant_context())."
        )
    if tenant_id is None:
        raise TenantContextError(
            "Tenant context is None for a tenant-scoped DB operation; expected an "
            'explicit tenant slug or "master".'
        )
    return tenant_id


def clear_tenant_context() -> None:
    """Clear the tenant context"""
    try:
        # Simply set to None - the context will be properly isolated per request
        _tenant_id_ctx.set("master")
    except LookupError:
        pass


# ───────────── background-task scope ─────────────
# Marks the current execution as a background (Celery) task so DB engine
# selection can use a NullPool engine. Context-local (ContextVar) rather than a
# mutable global on ``settings`` so concurrent tasks in one worker can't race.
_background_task_ctx: ContextVar[bool] = ContextVar("background_task", default=False)


def is_background_task() -> bool:
    """Return whether the current context is running inside a background task."""
    return _background_task_ctx.get()


@contextmanager
def background_task_context() -> Iterator[None]:
    """Mark the enclosed block as a background task, restoring the prior value on exit.

    Replaces the previous ``settings.BACKGROUND_TASK`` global mutation, which was
    shared mutable state and raced under concurrency.
    """
    token = _background_task_ctx.set(True)
    try:
        yield
    finally:
        _background_task_ctx.reset(token)

