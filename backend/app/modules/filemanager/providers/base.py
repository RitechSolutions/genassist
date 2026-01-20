"""
Base Storage Provider Interface

Defines the common interface that all storage providers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseStorageProvider(ABC):
    """
    Abstract base class for all storage providers
    
    This interface ensures consistency across different storage provider implementations
    (local, S3, Azure, GCS, SharePoint, etc.) and enables polymorphic usage.
    """

    name: str
    provider_type: str

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with configuration
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the provider
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    def get_base_path(self) -> str:
        """
        Get the base path of the storage provider
        
        Returns:
            Base path of the storage provider
        """
        pass

    @abstractmethod
    async def upload_file(
        self,
        file_content: bytes,
        storage_path: str,
        file_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Upload a file to the storage provider
        
        Args:
            file_content: File content as bytes
            storage_path: Path where the file should be stored
            file_metadata: Optional file metadata dictionary
            
        Returns:
            Storage path where the file was stored
        """
        pass

    @abstractmethod
    async def download_file(self, storage_path: str) -> bytes:
        """
        Download a file from the storage provider
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            File content as bytes
        """
        pass

    @abstractmethod
    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from the storage provider
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in storage
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        List files in storage
        
        Args:
            prefix: Optional path prefix to filter files
            limit: Optional maximum number of files to return
            
        Returns:
            List of file paths
        """
        pass

    async def create_folder(self, folder_path: str) -> bool:
        """
        Create a folder/directory in storage (optional for some providers)
        
        Args:
            folder_path: Path to the folder to create
            
        Returns:
            True if successful, False otherwise
            
        Note:
            Some providers (like S3) don't have explicit folders, so this may be a no-op
        """
        # Default implementation does nothing (for object storage providers)
        return True

    async def delete_folder(self, folder_path: str, recursive: bool = True) -> bool:
        """
        Delete a folder/directory from storage (optional for some providers)
        
        Args:
            folder_path: Path to the folder to delete
            recursive: Whether to delete recursively (default: True)
            
        Returns:
            True if successful, False otherwise
            
        Note:
            Some providers (like S3) don't have explicit folders, so this may be a no-op
        """
        # Default implementation does nothing (for object storage providers)
        return True

    async def folder_exists(self, folder_path: str) -> bool:
        """
        Check if a folder exists in storage
        
        Args:
            folder_path: Path to the folder in storage
            
        Returns:
            True if folder exists, False otherwise
        """
        # Default implementation checks if any files exist with the prefix
        files = await self.list_files(prefix=folder_path, limit=1)
        return len(files) > 0

    def is_initialized(self) -> bool:
        """
        Check if the provider is initialized
        
        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get provider statistics and file metadata
        
        Returns:
            Dictionary containing provider statistics
        """
        pass

    def close(self):
        """
        Clean up resources (optional override)
        
        Default implementation does nothing.
        Providers should override if they need cleanup.
        """
        pass
