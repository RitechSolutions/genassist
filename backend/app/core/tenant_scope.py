"""
Custom tenant-aware scope for dependency injection
"""

from injector import ScopeDecorator
import logging
import threading
from contextvars import ContextVar
from typing import Any, Dict, Type, TypeVar

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
    """Get the current tenant ID from context"""
    try:
        tenant_id = _tenant_id_ctx.get()
        # Return None if tenant_id is None (explicitly set)
        return tenant_id if tenant_id is not None else "master"
    except LookupError:
        return "master"


def clear_tenant_context() -> None:
    """Clear the tenant context"""
    try:
        # Simply set to None - the context will be properly isolated per request
        _tenant_id_ctx.set("master")
    except LookupError:
        pass

