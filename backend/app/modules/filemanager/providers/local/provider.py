"""
Local File System Storage Provider

Implements storage operations using the local file system.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..base import BaseStorageProvider

logger = logging.getLogger(__name__)


class LocalFileSystemProvider(BaseStorageProvider):
    """
    Storage provider implementation using local file system.
    
    Files are stored in a base directory specified in configuration.
    """

    name = "local"
    provider_type = "local"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the local file system provider.
        
        Args:
            config: Configuration dictionary containing 'base_path' key
        """
        super().__init__(config)
        self.base_path = Path(config.get("base_path", "/tmp/filemanager"))
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> bool:
        """
        Initialize the provider by ensuring base directory exists.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            self._initialized = True
            logger.info(f"LocalFileSystemProvider initialized with base_path: {self.base_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize LocalFileSystemProvider: {e}")
            return False

    def get_base_path(self) -> str:
        """
        Get the base path of the storage provider
        
        Returns:
            Base path of the storage provider
        """
        return str(self.base_path)

    def _resolve_path(self, storage_path: str) -> Path:
        """
        Resolve storage path to absolute file system path.
        
        Args:
            storage_path: Storage path (relative to base_path)
            
        Returns:
            Absolute Path object
        """
        # Normalize path to prevent directory traversal
        normalized_path = Path(storage_path).as_posix()
        # Remove leading slashes and resolve
        normalized_path = normalized_path.lstrip('/')
        full_path = (self.base_path / normalized_path).resolve()
        
        # Ensure resolved path is within base_path
        try:
            full_path.relative_to(self.base_path.resolve())
        except ValueError:
            raise ValueError(f"Path {storage_path} is outside base_path {self.base_path}")
        
        return full_path

    async def upload_file(
        self,
        file_content: bytes,
        storage_path: str,
        file_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Upload a file to local file system.
        
        Args:
            file_content: File content as bytes
            storage_path: Path where the file should be stored
            file_metadata: Optional file metadata dictionary (not used for local storage)
            
        Returns:
            Storage path where the file was stored
        """
        try:
            full_path = self._resolve_path(storage_path)
            
            # Create parent directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file content
            full_path.write_bytes(file_content)
            
            logger.debug(f"Uploaded file to {full_path}")
            return storage_path
        except Exception as e:
            logger.error(f"Failed to upload file {storage_path}: {e}")
            raise

    async def download_file(self, storage_path: str) -> bytes:
        """
        Download a file from local file system.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            File content as bytes
        """
        try:
            full_path = self._resolve_path(storage_path)
            
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {storage_path}")
            
            return full_path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to download file {storage_path}: {e}")
            raise

    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from local file system.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            True if successful, False otherwise
        """
        try:
            full_path = self._resolve_path(storage_path)
            
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
                logger.debug(f"Deleted file {full_path}")
                return True
            else:
                logger.warning(f"File not found or not a file: {storage_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete file {storage_path}: {e}")
            return False

    async def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in local file system.
        
        Args:
            storage_path: Path to the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            full_path = self._resolve_path(storage_path)
            return full_path.exists() and full_path.is_file()
        except Exception:
            return False

    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        List files in local file system.
        
        Args:
            prefix: Optional path prefix to filter files
            limit: Optional maximum number of files to return
            
        Returns:
            List of file paths (relative to base_path)
        """
        try:
            if prefix:
                search_path = self._resolve_path(prefix)
                if search_path.is_file():
                    # If prefix is a file, return just that file
                    return [prefix]
                elif search_path.is_dir():
                    # List files in directory
                    files = [f for f in search_path.rglob("*") if f.is_file()]
                else:
                    # Prefix doesn't exist or is invalid
                    return []
            else:
                # List all files in base_path
                files = [f for f in self.base_path.rglob("*") if f.is_file()]
            
            # Convert to relative paths
            relative_files = [str(f.relative_to(self.base_path)) for f in files]
            
            # Apply limit
            if limit:
                relative_files = relative_files[:limit]
            
            return relative_files
        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return []

    async def create_folder(self, folder_path: str) -> bool:
        """
        Create a folder/directory in local file system.
        
        Args:
            folder_path: Path to the folder to create
            
        Returns:
            True if successful, False otherwise
        """
        try:
            full_path = self._resolve_path(folder_path)
            full_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created folder {full_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create folder {folder_path}: {e}")
            return False

    async def delete_folder(self, folder_path: str, recursive: bool = True) -> bool:
        """
        Delete a folder/directory from local file system.
        
        Args:
            folder_path: Path to the folder to delete
            recursive: Whether to delete recursively (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            full_path = self._resolve_path(folder_path)
            
            if full_path.exists() and full_path.is_dir():
                if recursive:
                    import shutil
                    shutil.rmtree(full_path)
                else:
                    full_path.rmdir()
                logger.debug(f"Deleted folder {full_path}")
                return True
            else:
                logger.warning(f"Folder not found or not a directory: {folder_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete folder {folder_path}: {e}")
            return False

    async def folder_exists(self, folder_path: str) -> bool:
        """
        Check if a folder exists in local file system.
        
        Args:
            folder_path: Path to the folder in storage
            
        Returns:
            True if folder exists, False otherwise
        """
        try:
            full_path = self._resolve_path(folder_path)
            return full_path.exists() and full_path.is_dir()
        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get provider statistics and file metadata.
        
        Returns:
            Dictionary containing provider statistics
        """
        try:
            total_size = sum(
                f.stat().st_size for f in self.base_path.rglob("*") if f.is_file()
            )
            file_count = len([f for f in self.base_path.rglob("*") if f.is_file()])
            folder_count = len([d for d in self.base_path.rglob("*") if d.is_dir()])
            
            return {
                "provider_type": self.provider_type,
                "base_path": str(self.base_path),
                "total_size": total_size,
                "file_count": file_count,
                "folder_count": folder_count,
                "initialized": self._initialized,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "provider_type": self.provider_type,
                "base_path": str(self.base_path),
                "initialized": self._initialized,
                "error": str(e),
            }

    def close(self):
        """Clean up resources (no-op for local file system)."""
        pass
