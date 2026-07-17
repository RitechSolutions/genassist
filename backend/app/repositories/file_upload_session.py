"""Repository for files_upload_sessions."""

from uuid import UUID

from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.files_upload_session import FilesUploadSessionModel
from app.repositories.db_repository import DbRepository


@inject
class FileUploadSessionRepository(DbRepository[FilesUploadSessionModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(FilesUploadSessionModel, db)

    async def get_by_id(self, session_id: UUID) -> FilesUploadSessionModel | None:
        q = select(FilesUploadSessionModel).where(
            FilesUploadSessionModel.id == session_id,
            FilesUploadSessionModel.is_deleted == 0,
        )
        r = await self.db.execute(q)
        return r.scalars().first()

