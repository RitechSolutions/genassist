import logging
from typing import Generic, List, Optional, Sequence, Type, TypeVar
from uuid import UUID
from sqlalchemy import select, update, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Load, selectinload
from app.db.base import Base
from app.schemas.filter import BaseFilterModel


logger = logging.getLogger(__name__)
OrmModelT = TypeVar("OrmModelT", bound=Base)


class DbRepository(Generic[OrmModelT]):
    """
    Generic async repository for one ORM model.
    Pass relationship names to `eager` to get them eagerly loaded
    with `selectinload`, e.g.  repo.get_by_id(id, eager=("comments",))
    """

    def __init__(self, model: Type[OrmModelT], db: AsyncSession):
        self.model = model
        self.db = db
        logger.debug("Initialised DbRepository for %s", model.__name__)


    # ───────────── internal helpers ─────────────
    def _apply_eager_options(
            self, stmt, eager: Sequence[str] | None
            ):
        if eager:
            options: List[Load] = [
                selectinload(getattr(self.model, rel)) for rel in eager
                ]
            stmt = stmt.options(*options)
        return stmt

    def _apply_filters(self, stmt, filter_obj):
        """
        Apply domain-specific filters (dates, operator_id, etc.)
        Override this in child repositories for custom filtering logic.
        """
        # Date range filtering (if model has created_at)
        if hasattr(self.model, 'created_at'):
            if filter_obj.from_date:
                stmt = stmt.where(self.model.created_at >= filter_obj.from_date)
            if filter_obj.to_date:
                stmt = stmt.where(self.model.created_at <= filter_obj.to_date)

        # Operator filtering (if model has operator_id)
        if hasattr(self.model, 'operator_id') and filter_obj.operator_id:
            stmt = stmt.where(self.model.operator_id == filter_obj.operator_id)

        return stmt

    def _apply_sorting(self, stmt, filter_obj: BaseFilterModel):
        """Apply sorting based on order_by and sort_direction"""
        if filter_obj.order_by:
            column = self._resolve_sort_column(filter_obj.order_by)
            if column is not None:
                order_clause = desc(column) if filter_obj.sort_direction == "DESC" else asc(column)
                stmt = stmt.order_by(order_clause)
        elif hasattr(self.model, 'created_at'):
            # Default sorting if no order_by specified
            stmt = stmt.order_by(self.model.created_at.asc())

        return stmt

    def _resolve_sort_column(self, sort_field):

        if hasattr(self.model, sort_field.value):
            return getattr(self.model, sort_field.value)

        logger.warning(f"Sort field {sort_field} not found on {self.model.__name__}")
        return None

    def _apply_pagination(self, stmt, filter_obj):
        """Apply offset and limit for pagination"""
        return stmt.offset(filter_obj.skip).limit(filter_obj.limit)


    # ───────────── READ methods ────────────────
    async def get_all(
            self,
            *,
            filter_obj=None,
            eager: Sequence[str] | None = None
            ) -> List[OrmModelT]:
        """
        Get all records with optional filtering, sorting, and pagination.

        Args:
            filter_obj: Optional BaseFilterModel instance for filtering/pagination/sorting
            eager: Optional sequence of relationship names to eagerly load
        """
        stmt = select(self.model)

        # Apply eager loading
        stmt = self._apply_eager_options(stmt, eager)

        if filter_obj:
            # Apply domain filters (dates, operator, etc.)
            stmt = self._apply_filters(stmt, filter_obj)

            # Apply sorting
            stmt = self._apply_sorting(stmt, filter_obj)

            # Apply pagination
            stmt = self._apply_pagination(stmt, filter_obj)
        else:
            # Default behavior when no filter provided
            if hasattr(self.model, 'created_at'):
                stmt = stmt.order_by(self.model.created_at.asc())

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

    async def get_by_operator_id(self, operator_id: UUID, eager: Sequence[str] | None = None) -> Optional[OrmModelT]:
        stmt = select(self.model).where(self.model.operator_id == operator_id)
        stmt = self._apply_eager_options(stmt, eager)
        result = await self.db.execute(stmt)
        return result.scalars().first()


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

    async def soft_delete(self, obj: OrmModelT) -> None:
        await self.db.execute(
                update(obj.__class__)
                .where(obj.__class__.id == obj.id)
                .values(is_deleted=True)
                .execution_options(synchronize_session="fetch")
                )
        await self.db.commit()
