"""
FileManagerService Manager - Tenant-aware singleton for efficient service management

This module provides a tenant-aware singleton manager that creates and caches FileManagerService
instances per tenant/user, ensuring tenant isolation while avoiding repeated initialization.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.services.file_manager import FileManagerService

from app.repositories.file_manager import FileManagerRepository
from .config import FileManagerConfig
from .providers.base import BaseStorageProvider
from .providers.local import LocalFileSystemProvider
from .providers.azure import AzureStorageProvider
from .providers.s3 import S3StorageProvider
from app.core.tenant_scope import get_tenant_context

logger = logging.getLogger(__name__)


class FileManagerServiceManager:
    """
    Tenant-aware singleton manager for FileManagerService instances.

    This manager:
    1. Creates and caches service instances per tenant/user
    2. Provides tenant isolation - each tenant gets their own cache
    3. Manages storage provider initialization and selection
    4. Provides simplified API for file operations
    5. Handles initialization and cleanup
    """

    def __init__(self):
        self._services: Dict[str, "FileManagerService"] = {}
        self._providers: Dict[str, BaseStorageProvider] = {}
        self._initialization_locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        self._config: Optional[FileManagerConfig] = None
        logger.info("FileManagerServiceManager initialized")

    def set_config(self, config: FileManagerConfig):
        """Set the configuration for the manager."""
        self._config = config

    def _get_cache_key(self, user_id: Optional[UUID] = None, provider_type: Optional[str] = None) -> str:
        """Generate cache key for service instance."""
        tenant_id = get_tenant_context() or "master"
        user_str = str(user_id) if user_id else "default"
        provider = provider_type or (self._config.default_storage_provider if self._config else "local")
        return f"{tenant_id}:{user_str}:{provider}"

    async def _get_or_create_provider(
        self,
        provider_type: str,
        config: Optional[FileManagerConfig] = None
    ) -> Optional[BaseStorageProvider]:
        """
        Get or create a storage provider instance.

        Args:
            provider_type: Storage provider type (local, s3, azure, gcs, sharepoint)
            config: Optional FileManagerConfig (uses manager config if not provided)

        Returns:
            BaseStorageProvider instance or None if creation fails
        """
        config = config or self._config
        if not config:
            logger.error("No configuration provided for storage provider")
            return None

        # Check cache
        cache_key = f"provider:{provider_type}"
        if cache_key in self._providers:
            provider = self._providers[cache_key]
            if provider.is_initialized():
                return provider

        # Ensure we have a lock for this provider
        if cache_key not in self._initialization_locks:
            async with self._lock:
                if cache_key not in self._initialization_locks:
                    self._initialization_locks[cache_key] = asyncio.Lock()

        # Use lock to prevent concurrent initialization
        async with self._initialization_locks[cache_key]:
            # Double-check pattern
            if cache_key in self._providers and self._providers[cache_key].is_initialized():
                return self._providers[cache_key]

            try:
                # Get provider configuration
                provider_config = config.get_provider_config(provider_type)
                if not provider_config:
                    logger.error(f"No configuration found for provider type: {provider_type}")
                    return None

                # Create provider instance based on type
                provider: Optional[BaseStorageProvider] = None
                
                if provider_type == "local":
                    provider = LocalFileSystemProvider(provider_config)
                elif provider_type == "s3":
                    provider = S3StorageProvider(provider_config)
                elif provider_type == "azure":
                    provider = AzureStorageProvider(provider_config)
                elif provider_type == "gcs":
                    # TODO: Import and create GoogleCloudStorageProvider when implemented
                    logger.warning("GoogleCloudStorageProvider is not yet implemented")
                    return None
                elif provider_type == "sharepoint":
                    # TODO: Import and create SharePointProvider when implemented
                    logger.warning("SharePointProvider is not yet implemented")
                    return None
                else:
                    logger.error(f"Unknown provider type: {provider_type}")
                    return None

                if not provider:
                    return None

                # Initialize provider
                success = await provider.initialize()
                if not success:
                    logger.error(f"Failed to initialize {provider_type} provider")
                    return None

                # Cache the provider
                self._providers[cache_key] = provider
                logger.info(f"Created and cached {provider_type} storage provider")
                return provider

            except Exception as e:
                logger.error(f"Error creating {provider_type} provider: {e}", exc_info=True)
                return None

    async def get_service(
        self,
        repository: FileManagerRepository,
        user_id: Optional[UUID] = None,
        provider_type: Optional[str] = None
    ) -> Optional[FileManagerService]:
        """
        Get or create a FileManagerService for a user.

        Args:
            repository: FileManagerRepository instance
            user_id: Optional user ID (defaults to current user from context)
            provider_type: Optional storage provider type (defaults to config default)

        Returns:
            FileManagerService instance or None if creation fails
        """
        config = self._config
        if not config:
            # Use default config if not set
            from .config import FileManagerConfig, LocalStorageConfig
            from app.core.config.settings import settings
            
            config = FileManagerConfig(
                default_storage_provider="local",
                local=LocalStorageConfig(
                    base_path=str(settings.UPLOAD_FOLDER) if hasattr(settings, 'UPLOAD_FOLDER') else "/tmp/filemanager"
                )
            )

        provider_type = provider_type or config.default_storage_provider
        cache_key = self._get_cache_key(user_id, provider_type)

        # Return existing service if available
        if cache_key in self._services:
            service = self._services[cache_key]
            if service.storage_provider and service.storage_provider.is_initialized():
                return service

        # Ensure we have a lock for this service
        if cache_key not in self._initialization_locks:
            async with self._lock:
                if cache_key not in self._initialization_locks:
                    self._initialization_locks[cache_key] = asyncio.Lock()

        # Use lock to prevent concurrent initialization
        async with self._initialization_locks[cache_key]:
            # Double-check pattern
            if cache_key in self._services:
                service = self._services[cache_key]
                if service.storage_provider and service.storage_provider.is_initialized():
                    return service

            try:
                # Get or create storage provider
                provider = await self._get_or_create_provider(provider_type, config)
                if not provider:
                    logger.error(f"Failed to get storage provider: {provider_type}")
                    return None

                # Lazy import to avoid circular dependency
                from app.services.file_manager import FileManagerService

                # Create service
                service = FileManagerService(repository)
                service.set_storage_provider(provider)

                # Cache the service
                self._services[cache_key] = service
                logger.info(f"Created and cached FileManagerService for {cache_key}")
                return service

            except Exception as e:
                logger.error(f"Error creating FileManagerService for {cache_key}: {e}", exc_info=True)
                return None

    async def remove_service(self, user_id: Optional[UUID] = None, provider_type: Optional[str] = None):
        """Remove a cached service instance."""
        cache_key = self._get_cache_key(user_id, provider_type)
        if cache_key in self._services:
            del self._services[cache_key]
            logger.info(f"Removed FileManagerService for {cache_key}")

    async def cleanup(self):
        """Cleanup all services and providers."""
        # Close all providers
        for provider in self._providers.values():
            try:
                provider.close()
            except Exception as e:
                logger.warning(f"Error closing provider: {e}")

        self._services.clear()
        self._providers.clear()
        self._initialization_locks.clear()
        logger.info("FileManagerServiceManager cleaned up")


# Singleton instance
_manager: Optional[FileManagerServiceManager] = None


def get_file_manager_manager() -> FileManagerServiceManager:
    """Get the singleton FileManagerServiceManager instance."""
    global _manager
    if _manager is None:
        _manager = FileManagerServiceManager()
    return _manager
