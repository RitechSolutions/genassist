"""
Playground routes for mocking APIs - no authentication or validations required.
Use this for testing and development purposes only.

Available endpoints:
- GET /api/v1/playground/ - Root endpoint
- GET /api/v1/playground/health - Health check
- GET/POST/PUT/DELETE/PATCH /api/v1/playground/mock/{endpoint} - Mock any endpoint
- POST /api/v1/playground/echo - Echo request data
- GET /api/v1/playground/sample-data - Return sample data
- POST /api/v1/playground/sample-response - Create sample response
- GET /api/v1/playground/error/{status_code} - Mock error responses
- GET /api/v1/playground/delay/{seconds} - Mock delayed responses
- POST /api/v1/playground/webhook - Mock webhook endpoint
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.utils.sensitive_data_utils import redact_structure

logger = logging.getLogger(__name__)


# @deprecated: This endpoint is deprecated and will be removed in the future.
# Use the /api/v1/health endpoint instead.
router = APIRouter(deprecated=True)


@router.get("")
async def playground_root():
    """Root playground endpoint."""
    return {"message": "Playground API - No auth required", "status": "active"}


@router.get("/health")
async def playground_health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "playground"}


@router.get("/health/redis")
async def redis_health():
    """
    Redis connection health check endpoint.
    Returns detailed information about all Redis connection pools.
    """
    from app.core.config.settings import settings
    from app.dependencies.dependency_injection import RedisBinary, RedisString
    from app.dependencies.injector import injector
    from app.modules.websockets.socket_connection_manager import SocketConnectionManager

    health_status = {
        "status": "unknown",
        "pools": {}
    }

    try:
        # Check Redis String Client
        try:
            redis_string = injector.get(RedisString)
            await redis_string.ping()

            # Get connection pool statistics
            pool = redis_string.connection_pool
            pool_stats = {
                "max_connections": settings.REDIS_MAX_CONNECTIONS,
            }

            # Try to get detailed pool stats (may not be available in all Redis versions)
            try:
                available_conns = getattr(pool, "_available_connections", None)
                in_use_conns = getattr(pool, "_in_use_connections", None)

                if available_conns is not None:
                    pool_stats["available_connections"] = len(available_conns)
                if in_use_conns is not None:
                    pool_stats["in_use_connections"] = len(in_use_conns)

                if available_conns is not None and in_use_conns is not None:
                    total_created = len(available_conns) + len(in_use_conns)
                    pool_stats["total_created_connections"] = total_created
                    if settings.REDIS_MAX_CONNECTIONS > 0:
                        pool_stats["utilization_percent"] = round(
                            (len(in_use_conns) / settings.REDIS_MAX_CONNECTIONS) * 100, 2
                        )
            except Exception:
                pass  # Silently ignore if pool stats aren't available

            health_status["pools"]["redis_string"] = {
                "status": "healthy",
                "decode_responses": True,
                "usage": "WebSockets, conversations",
                **pool_stats
            }
        except Exception as e:
            health_status["pools"]["redis_string"] = {
                "status": "error",
                "error": str(e)
            }

        # Check Redis Binary Client (FastAPI cache)
        try:
            redis_binary = injector.get(RedisBinary)
            await redis_binary.ping()

            # Get connection pool statistics
            pool = redis_binary.connection_pool
            pool_stats = {
                "max_connections": settings.REDIS_MAX_CONNECTIONS_FOR_ENDPOINT_CACHE,
            }

            # Try to get detailed pool stats
            try:
                available_conns = getattr(pool, "_available_connections", None)
                in_use_conns = getattr(pool, "_in_use_connections", None)

                if available_conns is not None:
                    pool_stats["available_connections"] = len(available_conns)
                if in_use_conns is not None:
                    pool_stats["in_use_connections"] = len(in_use_conns)

                if available_conns is not None and in_use_conns is not None:
                    total_created = len(available_conns) + len(in_use_conns)
                    pool_stats["total_created_connections"] = total_created
                    if settings.REDIS_MAX_CONNECTIONS_FOR_ENDPOINT_CACHE > 0:
                        pool_stats["utilization_percent"] = round(
                            (len(in_use_conns) / settings.REDIS_MAX_CONNECTIONS_FOR_ENDPOINT_CACHE) * 100, 2
                        )
            except Exception:
                pass  # Silently ignore if pool stats aren't available

            health_status["pools"]["redis_binary"] = {
                "status": "healthy",
                "decode_responses": False,
                "usage": "FastAPI cache",
                **pool_stats
            }
        except Exception as e:
            health_status["pools"]["redis_binary"] = {
                "status": "error",
                "error": str(e)
            }

        # Check WebSocket Connection Manager
        try:
            socket_manager = injector.get(SocketConnectionManager)
            ws_stats = await socket_manager.get_connection_stats()
            health_status["pools"]["websocket_manager"] = {
                "status": "healthy",
                "websocket_stats": ws_stats,
                "redis_subscriber": "active" if socket_manager._redis_subscriber_task and not socket_manager._redis_subscriber_task.done() else "inactive",
                "note": "Uses redis_string pool for pub/sub (no separate connection limit)"
            }
        except Exception as e:
            health_status["pools"]["websocket_manager"] = {
                "status": "error",
                "error": str(e)
            }

        # Check Celery Redis (note: these are managed by Celery, not directly accessible)
        health_status["pools"]["celery"] = {
            "broker": {
                "status": "unknown",
                "max_connections": settings.CELERY_REDIS_MAX_CONNECTIONS,
                "note": "Managed by Celery, not directly accessible"
            }
        }

        # Calculate overall status based on our managed pools only
        # Count healthy, error, and unknown pools separately
        managed_pools_healthy = sum(
            1 for pool in [
                health_status["pools"].get("redis_string"),
                health_status["pools"].get("redis_binary"),
                health_status["pools"].get("websocket_manager")
            ]
            if pool and pool.get("status") == "healthy"
        )

        managed_pools_total = 3  # redis_string, redis_binary, websocket_manager

        if managed_pools_healthy == managed_pools_total:
            health_status["status"] = "healthy"
        elif managed_pools_healthy > 0:
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "unhealthy"

        health_status["summary"] = {
            "managed_pools_healthy": managed_pools_healthy,
            "managed_pools_total": managed_pools_total,
            "unmanaged_pools": 2  # Celery broker & backend
        }

        return health_status

    except Exception as e:
        logger.error(f"Error in Redis health check: {e}")
        return {
            "status": "error",
            "error": str(e),
            "pools": health_status.get("pools", {})
        }


@router.get("/mock/{endpoint}")
async def mock_get_endpoint(endpoint: str, request: Request):
    """Mock any GET endpoint - returns the endpoint name and query parameters."""
    query_params = redact_structure(dict(request.query_params))
    return {
        "endpoint": endpoint,
        "method": "GET",
        "query_params": query_params,
        "message": f"Mocked GET request to /{endpoint}"
    }


@router.post("/mock/{endpoint}")
async def mock_post_endpoint(endpoint: str, request: Request):
    """Mock any POST endpoint - returns the endpoint name and request body."""
    try:
        body = await request.json()
    except Exception:
        body = None
    return {
        "endpoint": endpoint,
        "method": "POST",
        "body": body,
        "message": f"Mocked POST request to /{endpoint}"
    }


@router.put("/mock/{endpoint}")
async def mock_put_endpoint(endpoint: str, request: Request):
    """Mock any PUT endpoint - returns the endpoint name and request body."""
    try:
        body = await request.json()
    except Exception:
        body = None
    return {
        "endpoint": endpoint,
        "method": "PUT",
        "body": body,
        "message": f"Mocked PUT request to /{endpoint}"
    }


@router.delete("/mock/{endpoint}")
async def mock_delete_endpoint(endpoint: str):
    """Mock any DELETE endpoint - returns the endpoint name."""
    return {
        "endpoint": endpoint,
        "method": "DELETE",
        "message": f"Mocked DELETE request to /{endpoint}"
    }


@router.patch("/mock/{endpoint}")
async def mock_patch_endpoint(endpoint: str, request: Request):
    """Mock any PATCH endpoint - returns the endpoint name and request body."""
    try:
        body = await request.json()
    except Exception:
        body = None
    return {
        "endpoint": endpoint,
        "method": "PATCH",
        "body": body,
        "message": f"Mocked PATCH request to /{endpoint}"
    }


@router.post("/echo")
async def echo_request(request: Request):
    """Echo back the request data."""
    try:
        body = await request.json()
    except Exception:
        body = None
    headers = redact_structure(dict(request.headers))
    query_params = redact_structure(dict(request.query_params))
    body = redact_structure(body)

    return {
        "method": request.method,
        "url": str(request.url),
        "headers": headers,
        "query_params": query_params,
        "body": body,
        "message": "Echoed request data"
    }


@router.get("/sample-data")
async def get_sample_data():
    """Return sample data for testing."""
    return {
        "users": [
            {"id": 1, "name": "John Doe", "email": "john@example.com"},
            {"id": 2, "name": "Jane Smith", "email": "jane@example.com"}
        ],
        "products": [
            {"id": 1, "name": "Product A", "price": 29.99},
            {"id": 2, "name": "Product B", "price": 49.99}
        ],
        "status": "success"
    }


@router.post("/sample-response")
async def create_sample_response(data: Dict[str, Any]):
    """Create a sample response with provided data."""
    return {
        "id": "mock-id-123",
        "created_at": "2024-01-01T00:00:00Z",
        "data": data,
        "status": "created",
        "message": "Sample response created successfully"
    }


@router.get("/error/{status_code}")
async def mock_error(status_code: int):
    """Mock different HTTP error responses."""
    if status_code == 400:
        return JSONResponse(
            status_code=400,
            content={"error": "Bad Request", "message": "Invalid input data"}
        )
    elif status_code == 401:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized",
                     "message": "Authentication required"}
        )
    elif status_code == 403:
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden", "message": "Access denied"}
        )
    elif status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"error": "Not Found", "message": "Resource not found"}
        )
    elif status_code == 500:
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error",
                     "message": "Something went wrong"}
        )
    else:
        return JSONResponse(
            status_code=status_code,
            content={"error": "Custom Error",
                     "message": f"Error with status {status_code}"}
        )


@router.get("/delay/{seconds}")
async def mock_delay(seconds: int):
    """Mock a delayed response."""
    import asyncio
    await asyncio.sleep(min(seconds, 30))  # Cap at 30 seconds
    return {
        "message": f"Response delayed by {seconds} seconds",
        "delay": seconds,
        "timestamp": "2024-01-01T00:00:00Z"
    }


@router.post("/webhook")
async def mock_webhook(request: Request):
    """Mock webhook endpoint."""
    try:
        body = await request.json()
    except Exception:
        body = None
    headers = dict(request.headers)

    return {
        "webhook_received": True,
        "headers": headers,
        "body": body,
        "message": "Webhook mock endpoint hit successfully"
    }
