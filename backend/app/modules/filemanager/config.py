"""
File Manager Configuration Models

Configuration classes for file manager module and storage providers.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class LocalStorageConfig(BaseModel):
    """Configuration for local file system storage provider."""
    base_path: str = Field(..., description="Base path for local file storage")
    create_dirs: bool = Field(default=True, description="Automatically create directories if they don't exist")


class S3StorageConfig(BaseModel):
    """Configuration for AWS S3 storage provider."""
    bucket_name: str = Field(..., description="S3 bucket name")
    aws_access_key_id: Optional[str] = Field(None, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(None, description="AWS secret access key")
    region_name: str = Field(default="us-east-1", description="AWS region name")


class AzureStorageConfig(BaseModel):
    """Configuration for Azure Blob Storage provider."""
    container_name: str = Field(..., description="Azure container name")
    connection_string: Optional[str] = Field(None, description="Azure connection string")
    account_name: Optional[str] = Field(None, description="Azure account name")
    account_key: Optional[str] = Field(None, description="Azure account key")


class GoogleCloudStorageConfig(BaseModel):
    """Configuration for Google Cloud Storage provider."""
    bucket_name: str = Field(..., description="GCS bucket name")
    credentials_path: Optional[str] = Field(None, description="Path to GCS credentials JSON file")
    credentials_json: Optional[Dict[str, Any]] = Field(None, description="GCS credentials as JSON dict")


class SharePointStorageConfig(BaseModel):
    """Configuration for SharePoint storage provider."""
    site_url: str = Field(..., description="SharePoint site URL")
    client_id: Optional[str] = Field(None, description="Azure AD client ID")
    client_secret: Optional[str] = Field(None, description="Azure AD client secret")
    tenant_id: Optional[str] = Field(None, description="Azure AD tenant ID")


class FileManagerConfig(BaseModel):
    """Base configuration for file manager module."""
    default_storage_provider: str = Field(default="local", description="Default storage provider to use")
    enable_cache: bool = Field(default=True, description="Enable Redis caching for metadata queries")
    max_file_size: int = Field(default=100 * 1024 * 1024, description="Maximum file size in bytes (100MB default)")
    allowed_mime_types: Optional[list[str]] = Field(default=None, description="List of allowed MIME types (None = all allowed)")
    
    # Provider-specific configurations
    local: Optional[LocalStorageConfig] = None
    s3: Optional[S3StorageConfig] = None
    azure: Optional[AzureStorageConfig] = None
    gcs: Optional[GoogleCloudStorageConfig] = None
    sharepoint: Optional[SharePointStorageConfig] = None

    def get_provider_config(self, provider_type: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific storage provider.
        
        Args:
            provider_type: Storage provider type (local, s3, azure, gcs, sharepoint)
            
        Returns:
            Configuration dictionary for the provider, or None if not configured
        """
        provider_map = {
            "local": self.local,
            "s3": self.s3,
            "azure": self.azure,
            "gcs": self.gcs,
            "sharepoint": self.sharepoint,
        }
        
        config = provider_map.get(provider_type)
        if config:
            return config.model_dump(exclude_none=True)
        return None
