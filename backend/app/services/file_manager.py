from ast import Dict
from uuid import UUID
import uuid
from fastapi import UploadFile
from injector import inject
from typing import Optional, List
import logging
import base64
from urllib.parse import quote

from app.modules.filemanager.providers.base import BaseStorageProvider
from app.db.models.file import FileModel
from app.repositories.file_manager import FileManagerRepository
from app.schemas.file import FileCreate, FileUpdate
from app.core.tenant_scope import get_tenant_context
from app.auth.utils import get_current_user_id

from app.modules.filemanager.providers import init_by_name
logger = logging.getLogger(__name__)


@inject
class FileManagerService:
    """Service layer for file and folder management operations."""

    def __init__(self, repository: FileManagerRepository):
        self.repository = repository
        # Storage provider will be injected via manager or configuration
        self.storage_provider = None

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

    async def _get_default_storage_provider(self) -> BaseStorageProvider:
        """Get and initialize the default storage provider."""
        if self.storage_provider and self.storage_provider.is_initialized():
            return self.storage_provider

        from app.modules.filemanager.manager import get_file_manager_manager
        from app.modules.filemanager.config import FileManagerConfig, LocalStorageConfig
        from app.core.config.settings import settings

        manager = get_file_manager_manager()
        config = manager._config

        if not config:
            config = FileManagerConfig(
                default_storage_provider="local",
                local=LocalStorageConfig(
                    base_path=str(settings.UPLOAD_FOLDER) if hasattr(settings, 'UPLOAD_FOLDER') else "/tmp/filemanager"
                )
            )

        provider = await manager._get_or_create_provider(config.default_storage_provider, config)
        if provider:
            self.storage_provider = provider
        return provider

    def build_file_headers(self, file: FileModel, content: Optional[bytes] = None, disposition_type: str = "inline") -> tuple[dict, str]:
        """Build HTTP headers for file responses."""
        media_type = file.mime_type or "application/octet-stream"

        # Properly encode filename for Content-Disposition header
        # Use RFC 5987 encoding for non-ASCII characters to avoid latin-1 encoding errors
        # Percent-encode the filename for safe ASCII representation
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
            headers["content-Length"] = str(file.size)

        return headers, media_type

    # ==================== File Methods ====================

    async def create_file(
        self,
        file: UploadFile,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        permissions: Optional[Dict] = None,
        allowed_extensions: Optional[List[str]] = None,
    ) -> FileModel:
        """
        Create a file metadata record and upload file content to storage.

        Args:
            file: File to upload
            allowed_extensions: Optional list of allowed file extensions
        """


        # read from the file
        file_content = await file.read()
        file_size = len(file_content)
        file_extension = file.filename.split(".")[-1].lower()
        file_mime_type = file.content_type
        file_name = file.filename
        file_storage_provider = self.storage_provider.name
        file_path = self.storage_provider.get_base_path()

        # generate a unique file name
        relative_storage_path = f"{uuid.uuid4()}.{file_extension}"

        # check if file extension is allowed
        if allowed_extensions and file_extension not in allowed_extensions:
            raise ValueError(f"File extension {file_extension} not allowed")

        # Get or initialize the storage provider
        if not self.storage_provider or not self.storage_provider.is_initialized():
            # read from the file
            file_storage_provider = file.storage_provider
            if not file_storage_provider:
                file_storage_provider = "local"
                # get storage provider by name
                provider_config = {
                    "base_path": file_path
                }
                storage_provider_class = self.get_storage_provider_by_name(file_storage_provider, config=provider_config)
                await self.set_storage_provider(storage_provider_class)

        if not self.storage_provider:
            raise ValueError("Storage provider not configured")

        user_id = get_current_user_id()

        file_data = FileCreate(
            file=file,
            name=file_name,
            mime_type=file_mime_type,
            size=file_size,
            file_extension=file_extension,
            storage_provider=file_storage_provider,
            path=file_path,
            storage_path=relative_storage_path,
            description=description,
            tags=tags,
            permissions=permissions,
        )

        # Upload file content if provided
        if file_content is not None:
            uploaded_file = await self.storage_provider.upload_file(
                file_content=file_content,
                storage_path=file_data.storage_path,
                file_metadata={"name": file_data.name, "mime_type": file_data.mime_type}
            )

        # Create file metadata record
        db_file = await self.repository.create_file(file_data, user_id)
        return db_file

    async def get_file_by_id(self, file_id: UUID) -> FileModel:
        """Get file metadata by ID."""
        return await self.repository.get_file_by_id(file_id)

    async def get_file_content(self, file: FileModel) -> bytes:
        """Get file content from storage provider."""
        file_storage_provider = file.storage_provider

        if not file_storage_provider:
            raise ValueError("Storage provider not configured")

        # get storage provider by name
        provider_config = {
            "base_path": file.path
        }
        
        storage_provider_class = self.get_storage_provider_by_name(file_storage_provider, config=provider_config)
        if not storage_provider_class:
            raise ValueError(f"Storage provider class {file_storage_provider} not found")

        # initialize storage provider
        await self.set_storage_provider(storage_provider_class)
        if not self.storage_provider.is_initialized():
            raise ValueError(f"Storage provider {self.storage_provider} not initialized")

        content = await self.storage_provider.download_file(file.storage_path)
        return content

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

    async def update_file(self, file_id: UUID, file_update: FileUpdate) -> FileModel:
        """Update file metadata."""
        update_data = file_update.model_dump(exclude_unset=True)
        
        # Handle path updates
        if "path" in update_data and update_data["path"]:
            # If storage path is not explicitly updated, update it to match path
            if "storage_path" not in update_data:
                update_data["storage_path"] = update_data["path"]

        file_update_obj = FileUpdate(**update_data)
        return await self.repository.update_file(file_id, file_update_obj)

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

    # ==================== Helper Methods ====================

    def _generate_file_path(self, name: str, user_id: Optional[UUID] = None) -> str:
        """Generate a file path based on name and user for file metadata record."""
        # Simple path generation - can be enhanced
        tenant_id = get_tenant_context() or "master"
        user_prefix = f"user_{user_id}" if user_id else "shared"
        return f"{tenant_id}/{user_prefix}/{name}"
