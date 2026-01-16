from uuid import UUID
from injector import inject
from typing import Optional, BinaryIO
import logging
from pathlib import Path

from app.db.models.file import FileModel
from app.repositories.file_manager import FileManagerRepository
from app.schemas.file import FileCreate, FileUpdate
from app.core.tenant_scope import get_tenant_context
from starlette_context import context

logger = logging.getLogger(__name__)


@inject
class FileManagerService:
    """Service layer for file and folder management operations."""

    def __init__(self, repository: FileManagerRepository):
        self.repository = repository
        # Storage provider will be injected via manager or configuration
        self.storage_provider = None

    def set_storage_provider(self, provider):
        """Set the storage provider for this service instance."""
        self.storage_provider = provider

    # ==================== File Methods ====================

    async def create_file(
        self,
        file_data: FileCreate,
        file_content: Optional[bytes] = None,
        user_id: Optional[UUID] = None
    ) -> FileModel:
        """
        Create a file metadata record and upload file content to storage.
        
        Args:
            file_data: File metadata
            file_content: Optional file content bytes
            user_id: Optional user ID (defaults to current user)
        """
        if not self.storage_provider:
            raise ValueError("Storage provider not configured")

        user_id = user_id or context.get("user_id")

        # Generate paths if not provided
        if not file_data.path:
            file_data.path = self._generate_file_path(file_data.name, user_id)
        
        if not file_data.storage_path:
            file_data.storage_path = file_data.path

        # Upload file content if provided
        if file_content is not None:
            storage_path = await self.storage_provider.upload_file(
                file_content=file_content,
                storage_path=file_data.storage_path,
                file_metadata={"name": file_data.name, "mime_type": file_data.mime_type}
            )
            file_data.storage_path = storage_path

            # Get file size if not provided
            if not file_data.size:
                file_data.size = len(file_content)

        # Create file metadata record
        db_file = await self.repository.create_file(file_data, user_id)
        return db_file

    async def get_file_by_id(self, file_id: UUID) -> FileModel:
        """Get file metadata by ID."""
        return await self.repository.get_file_by_id(file_id)

    async def get_file_content(self, file_id: UUID) -> bytes:
        """Get file content from storage provider."""
        if not self.storage_provider:
            raise ValueError("Storage provider not configured")

        file = await self.repository.get_file_by_id(file_id)
        return await self.storage_provider.download_file(file.storage_path)

    async def download_file(self, file_id: UUID) -> tuple[FileModel, bytes]:
        """Get both file metadata and content."""
        file = await self.get_file_by_id(file_id)
        content = await self.get_file_content(file_id)
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
            user_id=user_id or context.get("user_id"),
            storage_provider=storage_provider,
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
