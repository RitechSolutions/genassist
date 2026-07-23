from typing import Iterable, List, Optional
from uuid import UUID

from injector import inject
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.enums.template_status_enum import TemplateStatus
from app.db.models.template import TemplateModel
from app.repositories.db_repository import DbRepository


@inject
class TemplateRepository(DbRepository[TemplateModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TemplateModel, db)

    async def list_for_user(self, user_id: UUID) -> List[TemplateModel]:
        """A user's own PRIVATE templates (newest first).

        Filtered to ``status == 'private'`` so that published copies (which, in
        the master/single-tenant DB, live alongside the originals and share
        ``created_by``) are never listed here — they surface via the community
        query instead.
        """
        stmt = select(TemplateModel).where(
            TemplateModel.created_by == user_id,
            TemplateModel.status == TemplateStatus.PRIVATE,
            TemplateModel.is_deleted == 0,
        ).order_by(TemplateModel.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_by_status(self, status: TemplateStatus) -> List[TemplateModel]:
        """Rows in a given lifecycle status (used against the master DB)."""
        stmt = (
            select(TemplateModel)
            .where(TemplateModel.status == status, TemplateModel.is_deleted == 0)
            .order_by(TemplateModel.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def published_by_user(self, user_id: UUID) -> List[TemplateModel]:
        """Master rows this user has published (any status), to annotate their cards.

        Newest first so callers annotating by source can take the latest row.
        """
        stmt = (
            select(TemplateModel)
            .where(
                TemplateModel.published_by == user_id,
                TemplateModel.is_deleted == 0,
            )
            .order_by(TemplateModel.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def increment_install(self, template_id: UUID) -> None:
        await self.db.execute(
            update(TemplateModel)
            .where(TemplateModel.id == template_id)
            .values(install_count=TemplateModel.install_count + 1)
        )
        await self.db.commit()

    async def find_published(
        self, source_template_id: UUID, statuses: Iterable[TemplateStatus]
    ) -> Optional[TemplateModel]:
        """An existing master copy of a source template in one of the given statuses."""
        stmt = select(TemplateModel).where(
            TemplateModel.source_template_id == source_template_id,
            TemplateModel.status.in_(list(statuses)),
            TemplateModel.is_deleted == 0,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
