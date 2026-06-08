"""Repository for files_upload_sessions."""

from uuid import UUID

from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.files_upload_session import FilesUploadSessionModel


@inject
class FileUploadSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, row: FilesUploadSessionModel) -> FilesUploadSessionModel:
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def get_by_id(self, session_id: UUID) -> FilesUploadSessionModel | None:
        q = select(FilesUploadSessionModel).where(
            FilesUploadSessionModel.id == session_id,
            FilesUploadSessionModel.is_deleted == 0,
        )
        r = await self.db.execute(q)
        return r.scalars().first()

    async def update(self, row: FilesUploadSessionModel) -> FilesUploadSessionModel:
        await self.db.commit()
        await self.db.refresh(row)
        return row

