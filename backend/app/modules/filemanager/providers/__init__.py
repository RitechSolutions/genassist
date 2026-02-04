from typing import Optional
from .base import BaseStorageProvider
from .local import LocalFileSystemProvider
from .s3 import S3StorageProvider
from .azure import AzureStorageProvider
from .gcs import GoogleCloudStorageProvider
from .sharepoint import SharePointProvider

__all__ = [
    "BaseStorageProvider",
    "LocalFileSystemProvider",
    "S3StorageProvider",
    "AzureStorageProvider",
    "GoogleCloudStorageProvider",
    "SharePointProvider",
]


providers = {
    "local": LocalFileSystemProvider,
    "s3": S3StorageProvider,
    "azure": AzureStorageProvider,
    "gcs": GoogleCloudStorageProvider,
    "sharepoint": SharePointProvider,
}

def init_by_name(name: str, config: Optional[dict] = None) -> BaseStorageProvider:
    """Initialize a storage provider by name."""
    storage_provider_class = providers.get(name)
    if not storage_provider_class:
        raise ValueError(f"Storage provider {name} not found")

    match name:
        case "local":
            return LocalFileSystemProvider(config=config)
        case "s3":
            return S3StorageProvider(config=config)
        case "azure":
            return AzureStorageProvider(config=config)
        case "gcs":
            return GoogleCloudStorageProvider(config=config)
        case "sharepoint":
            return SharePointProvider(config=config)
        case _:
            raise ValueError(f"Storage provider {name} not found")