from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.file import FileModel
from app.schemas.file import FileCreate, FileUpdate
from app.cache.redis_cache import make_key_builder
from starlette_context import context
from fastapi_cache import FastAPICache
from redis.exceptions import ResponseError

file_manager_key_builder = make_key_builder("file_manager")


@inject
class FileManagerRepository:
    """Repository for file and folder database operations with caching."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== File Methods ====================

    async def create_file(self, file_data: FileCreate, user_id: Optional[UUID] = None) -> FileModel:
        """Create a new file metadata record."""
        new_file = FileModel(
            name=file_data.name,
            size=file_data.size,
            mime_type=file_data.mime_type,
            path=file_data.path or file_data.name,
            storage_path=file_data.storage_path or file_data.path or file_data.name,
            storage_provider=file_data.storage_provider,
            description=file_data.description,
            file_extension=file_data.file_extension,
            file_metadata=file_data.file_metadata,
            tags=file_data.tags,
            permissions=file_data.permissions,
        )
        self.db.add(new_file)
        await self.db.commit()
        await self.db.refresh(new_file)
        return new_file

    async def get_file_by_id(self, file_id: UUID) -> Optional[FileModel]:
        """Fetch file by ID."""
        query = select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.is_deleted == 0)
        )
        result = await self.db.execute(query)
        file = result.scalars().first()

        if not file:
            raise AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND)  # TODO: Create FILE_NOT_FOUND error

        return file

    async def get_file_by_path(self, path: str, user_id: Optional[UUID] = None) -> Optional[FileModel]:
        """Fetch file by path."""
        query = select(FileModel).where(
            and_(
                FileModel.path == path,
                FileModel.is_deleted == 0
            )
        )
        if user_id:
            query = query.where(FileModel.user_id == user_id)
        
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_files(
        self,
        user_id: Optional[UUID] = None,
        storage_provider: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[FileModel]:
        """List files with optional filtering."""
        query = select(FileModel).where(FileModel.is_deleted == 0)

        if user_id:
            query = query.where(FileModel.created_by == user_id)
        if storage_provider:
            query = query.where(FileModel.storage_provider == storage_provider)

        query = query.order_by(FileModel.created_at.desc())

        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_file(self, file_id: UUID, update_data: FileUpdate) -> FileModel:
        """Update file metadata."""
        file = await self.get_file_by_id(file_id)
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(file, key, value)
        
        file.updated_by = context.get("user_id")
        await self.db.commit()
        await self.db.refresh(file)
        
        # Invalidate cache (safe for Redis Cluster: Lua scripts without keys not supported)
        cache_key = f"file_manager:file:{file_id}"
        try:
            await FastAPICache.get_backend().clear(key=cache_key)
        except ResponseError as e:
            if "Lua scripts without any input keys are not supported" not in str(e):
                raise
            # Redis Cluster: ignore; cache will expire or be overwritten

        return file

    async def delete_file(self, file_id: UUID) -> None:
        """Soft delete a file (set is_deleted=1)."""
        file = await self.get_file_by_id(file_id)
        file.is_deleted = 1
        file.updated_by = context.get("user_id")
        await self.db.commit()
        
        # Invalidate cache (safe for Redis Cluster: Lua scripts without keys not supported)
        cache_key = f"file_manager:file:{file_id}"
        try:
            await FastAPICache.get_backend().clear(key=cache_key)
        except ResponseError as e:
            if "Lua scripts without any input keys are not supported" not in str(e):
                raise
            # Redis Cluster: ignore; cache will expire or be overwritten
