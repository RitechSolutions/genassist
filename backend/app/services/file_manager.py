from ast import Dict
import re
from uuid import UUID
import uuid
from fastapi import UploadFile
from fastapi_injector import Injected
import httpx
from injector import inject
from typing import Optional, List
import logging
import base64
from urllib.parse import quote
import os
from app.modules.filemanager.providers.base import BaseStorageProvider
from app.db.models.file import FileModel
from app.schemas.file import FileBase
from app.repositories.file_manager import FileManagerRepository
from app.core.tenant_scope import get_tenant_context

from app.modules.filemanager.providers import init_by_name
from app.core.config.settings import file_storage_settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.app_settings import AppSettingsRead

logger = logging.getLogger(__name__)


@inject
class FileManagerService:
    """Service layer for file and folder management operations."""

    def __init__(self, repository: FileManagerRepository):
        self.repository = repository
        # Storage provider will be injected via manager or configuration
        self.storage_provider = None

    async def initialize(self, base_url: str, base_path: str, app_settings: Optional[AppSettingsRead] = None) -> BaseStorageProvider:
        """Initialize the file manager service with the default storage provider and return the storage provider."""
        default_provider_name = file_storage_settings.default_provider_name
        try:
            # get the storage provider configuration for the file storage provider
            config = file_storage_settings.model_dump()
            config["base_url"] = base_url
            config["base_path"] = base_path

            # get the file manager settings
            if app_settings:
                provider_name = app_settings.values.get("file_manager_provider", default_provider_name)
                config["base_path"] = app_settings.values.get("base_path", base_path)
                config["AWS_BUCKET_NAME"] = app_settings.values.get("aws_bucket_name", file_storage_settings.AWS_BUCKET_NAME)

            # get the storage provider by name
            self.storage_provider = self.get_storage_provider_by_name(provider_name, config=config)
            await self.storage_provider.initialize()

            # return the storage provider
            return self.storage_provider
        except Exception as e:
            logger.error(f"Failed to initialize file manager service: {e}")
            raise AppException(error_key=ErrorKey.FILE_MANAGER_INITIALIZATION_FAILED, detail=str(e))


    async def set_storage_provider(self, provider: BaseStorageProvider):
        """Set the storage provider for this service instance."""
        self.storage_provider = provider
        await self.storage_provider.initialize()

    def get_storage_provider_by_name(self, name: str, config: Optional[dict] = None) -> BaseStorageProvider:
        """Get storage provider by name."""
        storage_provider_class = init_by_name(name, config=config)
        if not storage_provider_class:
            raise ValueError(f"Storage provider {name} not found")

        return storage_provider_class

    def build_file_headers(self, file: FileModel, content: Optional[bytes] = None, disposition_type: str = "inline") -> tuple[dict, str]:
        """Build HTTP headers for file responses."""
        media_type = file.mime_type or "application/octet-stream"

        # Properly encode filename for Content-Disposition header
        filename_encoded = quote(file.name, safe='')

        # For UTF-8 version (RFC 5987), percent-encode UTF-8 bytes
        filename_utf8_bytes = file.name.encode('utf-8')
        filename_utf8_encoded = ''.join(f'%{b:02X}' for b in filename_utf8_bytes)

        # Build Content-Disposition header with both ASCII fallback and UTF-8 version
        content_disposition = f'{disposition_type};filename="{filename_encoded}";filename*=UTF-8\'\'{filename_utf8_encoded}'

        headers = {
            "content-type": media_type,
            "content-disposition": content_disposition,
            "x-content-type-options": "nosniff",
            "access-control-allow-origin": "*",
            "access-control-expose-headers": "Age, Date, Content-Length, Content-Range, X-Content-Duration, X-Cache",
            "cache-control": "public, max-age=31536000"
        }

        # Add Content-Length if content is provided
        if content is not None:
            headers["content-length"] = str(len(content))
        elif hasattr(file, 'size') and file.size:
            headers["content-length"] = str(file.size)

        return headers, media_type

    # ==================== File Methods ====================

    async def create_file(
        self,
        file: UploadFile,
        file_base: FileBase,
        allowed_extensions: Optional[list[str]] = None,
        max_file_size: Optional[int] = None,
    ) -> FileModel:
        """
        Create a file metadata record and upload file content to storage.

        Args:
            file: File to upload
            allowed_extensions: Optional list of allowed file extensions
        """

        try:
            file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
            file_extension = file_extension.lower() if file_extension else "txt"

            # check if file extension is allowed
            if allowed_extensions is not None:
                self._validate_file_extension(file_extension, allowed_extensions)

            # read from the file
            file_content = await file.read()
            file_size = len(file_content)
            file_mime_type = file.content_type
            file_name = file.filename

            # check if file size is allowed
            if max_file_size is not None:
                self._validate_file_size(file_size, max_file_size)

            # Prefer the storage provider coming from the request payload; fall back to the
            # already configured provider if present, otherwise default to "local".
            file_storage_provider = (
                file_base.storage_provider
                or (self.storage_provider.name if self.storage_provider else None)
                or "local"
            )

            # Generate a unique file name only when the client hasn't provided one
            unique_file_name = f"{uuid.uuid4()}.{file_extension}" if file_base.name is None else file_base.name
            file_path = f"{file_base.path}/{unique_file_name}" if file_base.path else unique_file_name

            # Get or initialize the storage provider
            provider_name = file_storage_provider or "local"
            await self._initialize_storage_provider(provider_name)
            if not self.storage_provider or not self.storage_provider.is_initialized():
                raise ValueError("Storage provider not initialized")

            # Resolve the storage path that will be persisted with the file metadata.
            # If the caller has explicitly provided a storage_path, prefer that.
            storage_path = file_base.storage_path or self.storage_provider.get_base_path()

            # create the file data
            file_data = FileBase(
                name=file_base.name or file_name,
                original_filename=file_base.original_filename or file_name,
                mime_type=file_mime_type,
                size=file_size,
                file_extension=file_extension,
                storage_provider=file_storage_provider,
                storage_path=storage_path,
                path=file_path,
                description=file_base.description,
                tags=file_base.tags,
                permissions=file_base.permissions,
            )

            # Upload file content if provided
            if file_content is not None:
                upload_result = await self.storage_provider.upload_file(
                    file_content=file_content,
                    file_path=file_path,
                    file_metadata={"name": file_data.name, "mime_type": file_data.mime_type}
                )
                if not upload_result:
                    raise AppException(error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"Failed to upload file {file_path} on storage provider {self.storage_provider.name}")
        except Exception as e:
            logger.error(f"Failed to create file: {e}")
            raise AppException(error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"Failed to create file {file_path} on storage provider {self.storage_provider.name}: {str(e)}")
        finally:
            # Create file metadata record
            db_file = await self.repository.create_file(file_data)
            return db_file

    async def get_file_by_id(self, file_id: UUID) -> FileModel:
        """Get file metadata by ID."""
        file = await self.repository.get_file_by_id(file_id)
        return file

    async def get_file_content(self, file: FileModel) -> bytes:
        """Get file content from storage provider."""
        # initialize the storage provider
        await self._initialize_storage_provider(file.storage_provider)

        # make sure the storage provider is initialized
        if not self.storage_provider.is_initialized():
            raise ValueError("Storage provider not initialized")

        # get the storage path to download the file from
        download_path = file.path if file.storage_provider == "s3" else f"{self.storage_provider.get_base_path()}/{file.path}"
        return await self.storage_provider.download_file(download_path)

    async def get_file_base64(self, file_id: UUID) -> str:
        """Get file content as base64 encoded string."""
        file = await self.get_file_by_id(file_id)
        content = await self.get_file_content(file)
        return base64.standard_b64encode(content).decode('utf-8')

    async def download_file(self, file_id: UUID) -> tuple[FileModel, bytes]:
        """Get both file metadata and content."""
        file = await self.get_file_by_id(file_id)
        content = await self.get_file_content(file)
        return file, content

    async def download_file_to_path(self, file_id: UUID, path: str) -> None:
        """Download file to path."""
        try:
            # create the directory if it doesn't exist
            os.makedirs(os.path.dirname(path), exist_ok=True)

            file = await self.get_file_by_id(file_id)
            content = await self.get_file_content(file)
            with open(path, "wb") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to download file to path {path}: {e}")
            raise AppException(error_key=ErrorKey.INTERNAL_ERROR, detail=str(e))

    async def download_file_from_url_to_path(self, file_url: str, path: str) -> bool:
        """Download file from URL to path."""
        try:
            # create the directory if it doesn't exist
            os.makedirs(os.path.dirname(path), exist_ok=True)

            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("GET", file_url) as response:
                    response.raise_for_status()

                    with open(path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)

            return True
        except Exception as e:
            logger.error(f"Failed to download file from URL {file_url} to path {path}: {e}")
            return False

    async def get_file_content_from_url(self, file_url: str) -> bytes:
        """Get file content from URL."""
        # use regex to extract the file id from the url
        file_id = re.search(r"/files/([a-f0-9-]+)/source", file_url)
        if file_id:
            file_id = file_id.group(1)
        else:
            raise ValueError("Invalid file URL: {file_url}")
        file = await self.get_file_by_id(file_id)
        try:
            return await self.get_file_content(file)
        except Exception as e:
            logger.error(f"Failed to get file content from URL {file_url}: {e}")
            raise AppException(error_key=ErrorKey.INTERNAL_ERROR, error_detail=str(e))

    async def list_files(
        self,
        user_id: Optional[UUID] = None,
        storage_provider: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> list[FileModel]:
        """List files with optional filtering."""
        return await self.repository.list_files(
            # user_id=user_id or context.get("user_id"),
            storage_provider=storage_provider,
            user_id=user_id,
            limit=limit,
            offset=offset
        )

    async def update_file(self, file_id: UUID, file: UploadFile, file_base: FileBase) -> FileModel:
        """Update file metadata."""
        # update the file
        file = await self.repository.update_file(file_id, file, **file_base)
        return file_base

    async def delete_file(self, file_id: UUID, delete_from_storage: bool = True) -> None:
        """
        Delete a file (soft delete in DB, optionally delete from storage).

        Args:
            file_id: File ID to delete
            delete_from_storage: Whether to delete from storage provider as well
        """
        if delete_from_storage and self.storage_provider:
            file = await self.repository.get_file_by_id(file_id)
            try:
                await self.storage_provider.delete_file(file.storage_path)
            except Exception as e:
                logger.warning(f"Failed to delete file from storage: {e}")

        await self.repository.delete_file(file_id)

    # ==================== File URL Methods ====================
    async def get_file_url(self, file: FileModel) -> str:
        """Get the URL of a file."""
        # initialize the storage provider
        await self._initialize_storage_provider(file.storage_provider)

        # make sure the storage provider is initialized
        if not self.storage_provider.is_initialized():
            raise ValueError("Storage provider not initialized")

        # when used the local file storage provider, use the source url
        if file.storage_provider == "local":
            return await self.get_file_source_url(file.id)

        # get the file url from the storage provider
        return await self.storage_provider.get_file_url(file.storage_path, file.path)


    # ==================== File Source URL Methods ====================
    async def get_file_source_url(self, file_id: UUID) -> str:
        """Get the source URL of a file."""
        config_base_url = self.storage_provider.config.get("base_url")

        if not config_base_url:
            raise ValueError("Storage provider base URL not set")

        tenant_id = get_tenant_context()
        str_file_id = str(file_id)

        if tenant_id:
            return f"{config_base_url}/api/file-manager/files/{str_file_id}/source?X-Tenant-Id={tenant_id}"

        return f"{config_base_url}/api/file-manager/files/{str_file_id}/source"


    async def extract_file_id_from_url(self, file_url: str) -> Optional[UUID]:
        """Extract the file ID from the file URL."""
        file_id = file_url.split("/")[-1]
        try:
            return UUID(file_id) if file_id else None
        except ValueError:
            return None

    async def get_file_from_url(self, file_url: str) -> Optional[FileModel]:
        """Get the file from the URL."""
        file_id = await self.extract_file_id_from_url(file_url)
        return await self.get_file_by_id(file_id)


    # ==================== Helper Methods ====================
    async def _initialize_storage_provider(self, storage_provider_name: str) -> BaseStorageProvider:
        """Initialize the storage provider."""
        if self.storage_provider and self.storage_provider.is_initialized():
            return self.storage_provider

        # make sure the file has a storage provider
        if not storage_provider_name:
            raise ValueError("File has no storage provider")


        # get the storage provider configuration for the file storage provider
        # convert pydantic settings object to a plain dict for providers
        config = file_storage_settings.model_dump()

        # initialize the storage provider with the resolved configuration
        await self.set_storage_provider(
            self.get_storage_provider_by_name(storage_provider_name, config=config)
        )

    def _generate_file_path(self, name: str, user_id: Optional[UUID] = None) -> str:
        """Generate a file path based on name and user for file metadata record."""
        # Simple path generation - can be enhanced
        tenant_id = get_tenant_context() or "master"
        user_prefix = f"user_{user_id}" if user_id else "shared"
        return f"{tenant_id}/{user_prefix}/{name}"

    def _validate_file_extension(self, file_extension: str, allowed_extensions: list[str]) -> None:
        """Validate the file extension."""
        if file_extension not in allowed_extensions:
            raise ValueError(f"File extension {file_extension} not allowed")

    def _validate_file_size(self, file_size: int, max_file_size: int) -> None:
        """Validate the file size."""
        if file_size > max_file_size:
            raise ValueError(f"File size {file_size} is greater than the maximum allowed size {max_file_size}")