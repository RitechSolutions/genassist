from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.datasource import DataSourceModel
from app.schemas.datasource import DataSourceCreate
from starlette_context import context

@inject
class DataSourcesRepository:
    """Repository for datasource-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, datasource_data: DataSourceCreate) -> DataSourceModel:
        """Create a new datasource."""
        new_datasource = DataSourceModel(
            name=datasource_data.name,
            source_type=datasource_data.source_type,
            connection_data=datasource_data.connection_data,
            is_active=datasource_data.is_active,
        )
        self.db.add(new_datasource)
        await self.db.commit()
        await self.db.refresh(new_datasource)
        return new_datasource

    async def get_by_id(self, datasource_id: UUID) -> Optional[DataSourceModel]:
        """Fetch datasource by ID."""
        query = select(DataSourceModel).where(DataSourceModel.id == datasource_id)
        result = await self.db.execute(query)
        datasource = result.scalars().first()

        if not datasource:
            raise AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND)

        return datasource

    async def get_all(self) -> List[DataSourceModel]:
        """Fetch all datasources."""
        query = (
            select(DataSourceModel)
            .order_by(DataSourceModel.created_at.asc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update(self, datasource_id: UUID, update_data: dict) -> DataSourceModel:
        """Update an existing datasource."""
        datasource = await self.get_by_id(datasource_id)
        
        for key, value in update_data.items():
            setattr(datasource, key, value)
        
        datasource.updated_by = context.get("user_id")
        await self.db.commit()
        await self.db.refresh(datasource)
        return datasource

    async def delete(self, datasource_id: UUID) -> None:
        """Delete a datasource."""
        datasource = await self.get_by_id(datasource_id)
        await self.db.delete(datasource)
        await self.db.commit()

    async def get_active(self) -> List[DataSourceModel]:
        """Fetch all active datasources."""
        query = select(DataSourceModel).where(DataSourceModel.is_active == 1)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_type(self, source_type: str) -> List[DataSourceModel]:
        """Fetch datasources by their type."""
        query = select(DataSourceModel).where(DataSourceModel.source_type == source_type)
        result = await self.db.execute(query)
        return result.scalars().all() 