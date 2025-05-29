import logging
<<<<<<< HEAD
from typing import TypeVar, Generic, Type, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.db.base import Base



logger = logging.getLogger(__name__)
# Single generic bound to “any SQL-Alchemy declarative model”
=======
from typing import Generic, List, Optional, Sequence, Type, TypeVar
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Load, selectinload

from app.db.base import Base


logger = logging.getLogger(__name__)
>>>>>>> development
OrmModelT = TypeVar("OrmModelT", bound=Base)


class DbRepository(Generic[OrmModelT]):
    """
<<<<<<< HEAD
    Reusable async repository that exposes CRUD for a single ORM model.
    Works purely with SQLAlchemy entities; conversion to/from Pydantic
    happens **outside** (usually in the service layer).
    """


=======
    Generic async repository for one ORM model.
    Pass relationship names to `eager` to get them eagerly loaded
    with `selectinload`, e.g.  repo.get_by_id(id, eager=("comments",))
    """

>>>>>>> development
    def __init__(self, model: Type[OrmModelT], db: AsyncSession):
        self.model = model
        self.db = db
        logger.debug("Initialised DbRepository for %s", model.__name__)


<<<<<<< HEAD
    # ---------- READ ----------
    async def get_all(self) -> List[OrmModelT]:
        result = await self.db.execute(select(self.model))
        return result.scalars().all()


    async def get_by_id(self, obj_id: UUID) -> Optional[OrmModelT]:
        result = await self.db.execute(
                select(self.model).where(self.model.id == obj_id)
                )
        return result.scalars().first()


    async def get_by_ids(self, ids: List[UUID]) -> List[OrmModelT]:
        if not ids:
            return []
        result = await self.db.execute(
                select(self.model).where(self.model.id.in_(ids))
                )
        return result.scalars().all()


=======
    # ───────────── internal helper ─────────────
    def _apply_eager_options(
            self, stmt, eager: Sequence[str] | None
            ):
        if eager:
            options: List[Load] = [
                selectinload(getattr(self.model, rel)) for rel in eager
                ]
            stmt = stmt.options(*options)
        return stmt


    # ───────────── READ methods ────────────────
    async def get_all(
            self, *, eager: Sequence[str] | None = None
            ) -> List[OrmModelT]:
        stmt = self._apply_eager_options(select(self.model), eager)
        result = await self.db.execute(stmt)
        return result.scalars().all()


    async def get_by_id(
            self, obj_id: UUID, *, eager: Sequence[str] | None = None
            ) -> Optional[OrmModelT]:
        stmt = (
            self._apply_eager_options(select(self.model), eager)
            .where(self.model.id == obj_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()


    async def get_by_ids(
            self, ids: List[UUID], *, eager: Sequence[str] | None = None
            ) -> List[OrmModelT]:
        if not ids:
            return []
        stmt = (
            self._apply_eager_options(select(self.model), eager)
            .where(self.model.id.in_(ids))
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()


    # (create / update / delete unchanged)


>>>>>>> development
    # ---------- WRITE ----------
    async def create(self, obj: OrmModelT) -> OrmModelT:
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj


    async def update(self, obj: OrmModelT) -> OrmModelT:
        """
        Accepts a *managed* ORM object whose attributes have already been
        mutated by the caller.  Flush/commit & refresh are done here.
        """
        await self.db.commit()
        await self.db.refresh(obj)
        return obj


    async def delete(self, obj: OrmModelT) -> None:
        await self.db.delete(obj)
        await self.db.commit()
<<<<<<< HEAD
=======

    async def soft_delete(self, obj: OrmModelT) -> None:
        await self.db.execute(
                update(obj.__class__)
                .where(obj.__class__.id == obj.id)
                .values(is_deleted=True)
                .execution_options(synchronize_session="fetch")  # keep session in sync
                )
        await self.db.commit()
>>>>>>> development
