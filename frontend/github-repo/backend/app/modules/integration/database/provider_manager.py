"""
DBProviderManager - Singleton pattern for efficient DatabaseManager management

This module provides a singleton manager that creates and caches DatabaseManager
instances per source_id, avoiding repeated initialization and connection overhead.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from uuid import UUID
from app.dependencies.injector import injector
from app.services.datasources import DataSourceService
from app.modules.integration.database import DatabaseManager

logger = logging.getLogger(__name__)


class DBProviderManager:
    """
    Singleton manager for DatabaseManager instances.

    This manager:
    1. Creates and caches DatabaseManager instances per source_id
    2. Reuses connections to avoid overhead
    3. Provides simplified API for common operations
    4. Handles initialization and cleanup
    """

    _instance: Optional['DBProviderManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> 'DBProviderManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._managers: Dict[str, DatabaseManager] = {}
            cls._instance._initialization_locks: Dict[str, asyncio.Lock] = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'DBProviderManager':
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    _managers: Dict[str, DatabaseManager] = {}
    _initialization_locks: Dict[str, asyncio.Lock] = {}

    async def get_database_manager(self, source_id: str) -> Optional[DatabaseManager]:
        """
        Get or create a DatabaseManager for a source_id

        Args:
            source_id: Data source identifier

        Returns:
            DatabaseManager instance or None if creation fails
        """
        # Return existing manager if available
        if source_id in self._managers:
            manager = self._managers[source_id]
            if self._is_manager_valid(manager):
                return manager
            else:
                # Remove invalid manager
                logger.warning(
                    f"Removing invalid manager for source_id {source_id}")
                await self._remove_manager(source_id)

        # Ensure we have a lock for this source_id
        if source_id not in self._initialization_locks:
            self._initialization_locks[source_id] = asyncio.Lock()

        # Use lock to prevent concurrent initialization
        async with self._initialization_locks[source_id]:
            # Double-check pattern - manager might have been created while waiting
            if source_id in self._managers and self._is_manager_valid(self._managers[source_id]):
                return self._managers[source_id]

            try:
                logger.info(f"Creating DatabaseManager for source_id: {source_id}")
                # Get data source configuration
                ds_service = injector.get(DataSourceService)
                # Convert source_id to UUID if it's a string
                source_uuid = UUID(source_id) if isinstance(
                    source_id, str) else source_id
                ds = await ds_service.get_by_id(source_uuid, decrypt_sensitive=True)

                if not ds:
                    logger.warning(f"Data source {source_id} not found")
                    return None

                logger.info(f"Found datasource: {ds.name} (type: {ds.source_type})")
                # Create configuration for DatabaseManager
                # The DatabaseManager expects connection_data fields to be at the top level
                ds_config = ds.connection_data.copy() if ds.connection_data else {}
                ds_config.update({
                    "source_type": ds.source_type,
                    "name": ds.name,
                    "sync_source_id": str(ds.id),
                    "connection_data": ds.connection_data,
                })

                logger.info(f"Datasource config keys: {list(ds_config.keys())}")
                # Create DatabaseManager
                manager = DatabaseManager(ds_config)
                if not manager:
                    logger.error(
                        f"Failed to create DatabaseManager for source_id {source_id}")
                    return None
                
                await manager.initialize()

                # Cache the manager
                self._managers[source_id] = manager
                logger.info(
                    f"Created and cached DatabaseManager for source_id {source_id}")
                return manager

            except Exception as e:
                logger.error(
                    f"Error creating DatabaseManager for source_id {source_id}: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                return None

    def _is_manager_valid(self, manager: DatabaseManager) -> bool:
        """
        Check if a DatabaseManager is valid and ready to use

        Args:
            manager: DatabaseManager instance to check

        Returns:
            True if manager is valid, False otherwise
        """
        try:
            # Check if manager has required attributes
            if not (hasattr(manager, 'config') and
                    hasattr(manager, 'db_type') and
                    manager.config is not None):
                return False

            # Check if connection is still valid using the manager's internal method
            if hasattr(manager, '_is_connection_valid'):
                return manager._is_connection_valid()

            return True
        except Exception as e:
            logger.warning(f"Error checking manager validity: {e}")
            return False

    async def execute_query(self, source_id: str, query: str, parameters: list = None) -> tuple[list[dict], Optional[str]]:
        """
        Execute a query using the appropriate DatabaseManager

        Args:
            source_id: Data source identifier
            query: SQL query to execute
            parameters: Query parameters

        Returns:
            Tuple of (results, error_message)
        """
        manager = await self.get_database_manager(source_id)
        if not manager:
            logger.error(f"Could not get manager for source_id {source_id}")
            return [], f"Could not get manager for source_id {source_id}"

        try:
            return await manager.execute_query(query, parameters)
        except Exception as e:
            logger.error(
                f"Error executing query for source_id {source_id}: {e}")
            return [], str(e)

    async def get_schema(self, source_id: str) -> Dict[str, Any]:
        """
        Get database schema for a source

        Args:
            source_id: Data source identifier

        Returns:
            Database schema information
        """
        manager = await self.get_database_manager(source_id)
        if not manager:
            logger.error(f"Could not get manager for source_id {source_id}")
            return {"error": f"Could not get manager for source_id {source_id}"}

        try:
            return await manager.get_schema()
        except Exception as e:
            logger.error(
                f"Error getting schema for source_id {source_id}: {e}")
            return {"error": str(e)}

    async def _remove_manager(self, source_id: str):
        """Remove a manager from cache"""
        if source_id in self._managers:
            manager = self._managers[source_id]
            try:
                # Disconnect if possible
                if hasattr(manager, 'disconnect'):
                    await manager.disconnect()
            except Exception as e:
                logger.warning(
                    f"Error disconnecting manager for source_id {source_id}: {e}")
            finally:
                del self._managers[source_id]

        if source_id in self._initialization_locks:
            del self._initialization_locks[source_id]

    async def cleanup_manager(self, source_id: str):
        """
        Clean up a specific manager (useful when data source is deleted)

        Args:
            source_id: Data source ID
        """
        async with self._lock:
            await self._remove_manager(str(source_id))
            logger.info(f"Cleaned up manager for source_id {source_id}")

    async def cleanup_all(self):
        """Clean up all managers"""
        async with self._lock:
            for source_id in list(self._managers.keys()):
                await self._remove_manager(source_id)
            logger.info("Cleaned up all DatabaseManager instances")

    async def cleanup_inactive_connections(self):
        """Clean up inactive or invalid connections"""
        invalid_source_ids = []

        for source_id, manager in self._managers.items():
            if not self._is_manager_valid(manager):
                invalid_source_ids.append(source_id)

        for source_id in invalid_source_ids:
            await self._remove_manager(source_id)
            logger.info(
                f"Cleaned up inactive connection for source_id {source_id}")

        return len(invalid_source_ids)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about cached managers"""
        valid_count = 0
        connection_status = {}

        for source_id, manager in self._managers.items():
            is_valid = self._is_manager_valid(manager)
            valid_count += 1 if is_valid else 0
            connection_status[source_id] = {
                "valid": is_valid,
                "connected": getattr(manager, '_is_connected', False),
                "last_activity": getattr(manager, '_last_activity', None)
            }

        return {
            "total_managers": len(self._managers),
            "valid_managers": valid_count,
            "source_ids": list(self._managers.keys()),
            "connection_details": connection_status
        }

