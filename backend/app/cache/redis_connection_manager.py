"""
Redis Connection Manager for efficient connection pooling
"""

import logging
from typing import Optional
import asyncio
from redis.asyncio import Redis, ConnectionPool
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """Global singleton Redis connection manager with connection pooling"""

    _instance: Optional["RedisConnectionManager"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[Redis] = None
        self._initialized = False

    @classmethod
    async def get_instance(cls) -> "RedisConnectionManager":
        """Get singleton instance with thread-safe initialization (for backward compatibility)"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = RedisConnectionManager()
                    await cls._instance._initialize()
        return cls._instance

    async def initialize(self) -> None:
        """Public initialize method for dependency injection"""
        await self._initialize()

    async def _initialize(self) -> None:
        """Initialize Redis connection pool"""
        if self._initialized:
            return

        try:
            # Create connection pool with configurable settings
            self._pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                retry_on_timeout=True,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT,
                health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,
            )

            # Create Redis client with the pool
            self._redis = Redis(connection_pool=self._pool)

            # Test connection
            await self._redis.ping()

            self._initialized = True
            logger.info("Redis connection pool initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Redis connection pool: {e}")
            self._initialized = False
            raise

    async def get_redis(self) -> Redis:
        """Get Redis client from connection pool"""
        if not self._initialized:
            await self._initialize()

        if self._redis is None:
            raise RuntimeError("Redis connection not initialized")

        return self._redis

    async def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            if self._redis is None:
                return False
            await self._redis.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    async def get_connection_info(self) -> dict:
        """Get connection pool information"""
        if self._pool is None:
            return {"status": "not_initialized"}

        try:
            info = await self._redis.info()
            # Get pool statistics (attributes may vary by Redis version)
            pool_stats = {}
            try:
                pool_stats["pool_created_connections"] = getattr(
                    self._pool, "created_connections", "N/A"
                )
                pool_stats["pool_max_connections"] = getattr(
                    self._pool, "max_connections", "N/A"
                )
                # These attributes might not exist in all Redis versions
                available_conns = getattr(self._pool, "_available_connections", None)
                in_use_conns = getattr(self._pool, "_in_use_connections", None)
                pool_stats["pool_available_connections"] = (
                    len(available_conns) if available_conns else "N/A"
                )
                pool_stats["pool_in_use_connections"] = (
                    len(in_use_conns) if in_use_conns else "N/A"
                )
            except Exception as e:
                logger.debug(f"Could not get detailed pool stats: {e}")
                pool_stats = {"pool_info": "Limited stats available"}

            return {
                "status": "connected",
                "connected_clients": info.get("connected_clients", "unknown"),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                **pool_stats,
            }
        except Exception as e:
            logger.error(f"Error getting connection info: {e}")
            return {"status": "error", "error": str(e)}

    async def close(self) -> None:
        """Close Redis connection pool"""
        try:
            if self._redis:
                await self._redis.close()
                self._redis = None

            if self._pool:
                await self._pool.disconnect()
                self._pool = None

            self._initialized = False
            logger.info("Redis connection pool closed")

        except Exception as e:
            logger.error(f"Error closing Redis connection pool: {e}")

    @classmethod
    async def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)"""
        async with cls._lock:
            if cls._instance:
                await cls._instance.close()
                cls._instance = None
