from celery import Task, shared_task
from datetime import datetime
import logging
from typing import Callable, List, Any, Awaitable

from app.services.tenant import TenantService
from app.core.tenant_scope import set_tenant_context, clear_tenant_context
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class BaseTaskWithLogging(Task):
    """Base task class that adds logging and error handling."""

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {task_id} completed successfully")
        return super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")
        return super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Task {task_id} is being retried: {exc}")
        return super().on_retry(exc, task_id, args, kwargs, einfo)


@shared_task
def example_periodic_task():
    """Example periodic task that runs every hour."""
    logger.info(f"Running periodic task at {datetime.utcnow()}")
    # Add your task logic here
    return {"status": "completed", "timestamp": datetime.utcnow().isoformat()}


@shared_task
def long_running_task(duration: int = 60):
    """Example of a long-running task."""
    logger.info(f"Starting long running task for {duration} seconds")
    # Simulate work
    import time

    time.sleep(duration)
    return {"status": "completed", "duration": duration}


def create_task_wrapper(task_func: Callable[..., Awaitable[Any]]) -> Callable:
    """
    Creates a reusable wrapper function for tasks that need request scope and session cleanup.
    
    This helper eliminates code duplication by providing a standard pattern for:
    - Creating request scopes for dependency injection
    - Ensuring database sessions are properly closed
    - Handling errors gracefully
    
    Args:
        task_func: The actual async task function to wrap
        
    Returns:
        A wrapper function that can be used with run_task_for_all_tenants
        
    Example:
        async def my_task_async(param1: str):
            # Your task logic here
            return {"result": "success"}
            
        async def my_task_async_with_scope(param1: str = None):
            wrapper = create_task_wrapper(my_task_async)
            return await run_task_for_all_tenants(wrapper, param1=param1)
    """
    async def run_with_scope(**kwargs):
        """Inner wrapper that creates request scope and ensures cleanup"""
        from app.dependencies.injector import injector
        from fastapi_injector import RequestScopeFactory
        from sqlalchemy.ext.asyncio import AsyncSession
        
        request_scope_factory = injector.get(RequestScopeFactory)
        
        async with request_scope_factory.create_scope():
            try:
                # Call the actual task function with the provided kwargs
                return await task_func(**kwargs)
            finally:
                # Ensure any sessions created via DI are closed
                try:
                    # Try to get and close session if it exists
                    try:
                        session = injector.get(AsyncSession)
                        if session:
                            await session.close()
                    except Exception:
                        pass  # Session might not exist or already closed
                except Exception:
                    pass
    
    return run_with_scope


async def run_task_with_tenant_support(
    task_func: Callable[..., Awaitable[Any]],
    task_name: str,
    **kwargs
) -> dict:
    """
    High-level helper that runs a task for all tenants with proper error handling.
    
    This is a convenience function that combines create_task_wrapper and 
    run_task_for_all_tenants with consistent error handling and logging.
    
    Args:
        task_func: The actual async task function to run
        task_name: Name of the task for logging purposes
        **kwargs: Arguments to pass to the task function
        
    Returns:
        Dictionary with status and results
        
    Example:
        async def my_task_async(param1: str):
            # Your task logic here
            return {"result": "success"}
            
        async def my_task_async_with_scope(param1: str = None):
            return await run_task_with_tenant_support(
                my_task_async,
                "my_task",
                param1=param1
            )
    """
    try:
        logger.info(f"Starting {task_name} task for all tenants...")
        
        wrapper = create_task_wrapper(task_func)
        results = await run_task_for_all_tenants(wrapper, **kwargs)
        
        logger.info(f"{task_name} completed for {len(results)} tenant(s)")
        return {
            "status": "success",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error in {task_name} task: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
        }
    finally:
        logger.info(f"{task_name} task finished.")


async def run_task_for_all_tenants(task_func: Callable, **kwargs) -> List[dict]:
    """
    Helper to run a task function for all active tenants and master database.

    Args:
        task_func: Async function that runs the task logic
        **kwargs: Arguments to pass to the task function

    Returns:
        List of results for each tenant and master
    """
    results = []
    settings.BACKGROUND_TASK = True

    try:
        from app.db.multi_tenant_session import multi_tenant_manager
        from app.repositories.tenant import TenantRepository

        session_factory = multi_tenant_manager.get_tenant_session_factory("master")
        async with session_factory() as session:
            try:
                repository = TenantRepository(session)
                tenant_service = TenantService(repository=repository)
                tenants = await tenant_service.get_all_tenants()

                # First, run for master database (no tenant context)
                try:
                    logger.info("Running task for master database")
                    clear_tenant_context()  # Ensure no tenant context

                    result = await task_func(**kwargs)
                    if result:
                        results.append(
                            {
                                "tenant_id": "master",
                                "tenant_name": "Master Database",
                                "tenant_slug": "master",
                                "result": result,
                            }
                        )
                except Exception as e:
                    logger.error(
                        f"Error running task for master database: {e}", exc_info=True
                    )
                    results.append(
                        {
                            "tenant_id": "master",
                            "tenant_name": "Master Database",
                            "tenant_slug": "master",
                            "error": str(e),
                        }
                    )
                finally:
                    # Ensure tenant context is cleared after master run
                    clear_tenant_context()

                if not tenants:
                    logger.info("No active tenants found")
                    if not settings.MULTI_TENANT_ENABLED:
                        # In single-tenant mode, we only run for master (already done)
                        return results
                    return results

                logger.info(f"Running task for {len(tenants)} tenant(s)")

                for tenant in tenants:
                    try:
                        # Set tenant context for this tenant
                        set_tenant_context(str(tenant.slug))
                        logger.info(
                            f"Running task for tenant: {tenant.name} ({tenant.slug})"
                        )

                        # Run the task function with tenant context
                        result = await task_func(**kwargs)
                        if result:
                            results.append(
                                {
                                    "tenant_id": str(tenant.id),
                                    "tenant_name": tenant.name,
                                    "tenant_slug": tenant.slug,
                                    "result": result,
                                }
                            )

                    except Exception as e:
                        logger.error(
                            f"Error running task for tenant {tenant.name}: {e}",
                            exc_info=True,
                        )
                        results.append(
                            {
                                "tenant_id": str(tenant.id),
                                "tenant_name": tenant.name,
                                "tenant_slug": tenant.slug,
                                "error": str(e),
                            }
                        )
            finally:
                # Clear tenant context after each tenant
                clear_tenant_context()
            # Session is automatically closed by the async context manager

    except Exception as e:
        logger.error(f"Error in run_task_for_all_tenants: {e}", exc_info=True)
    finally:
        # Ensure context is cleared
        clear_tenant_context()
        # Reset BACKGROUND_TASK flag
        settings.BACKGROUND_TASK = False

    return results
