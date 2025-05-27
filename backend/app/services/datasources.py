from uuid import UUID
from fastapi import Depends

from app.repositories.datasources import DataSourcesRepository

from app.schemas.datasource import DataSourceCreate, DataSourceUpdate

class DataSourceService:
    def __init__(self, repository: DataSourcesRepository = Depends()):
        self.repository = repository

    async def create(self, datasource: DataSourceCreate):
        db_datasource = await self.repository.create(datasource)
        return db_datasource

    async def get_by_id(self, datasource_id: UUID):
        db_datasource = await self.repository.get_by_id(datasource_id)
        return db_datasource

    async def get_all(self):
        db_datasources = await self.repository.get_all()
        return db_datasources

    async def update(self, datasource_id: UUID, datasource_update: DataSourceUpdate):
        update_data = datasource_update.model_dump(exclude_unset=True)
        db_datasource = await self.repository.update(datasource_id, update_data)
        return db_datasource

    async def delete(self, datasource_id: UUID):
        await self.repository.delete(datasource_id)

    async def get_active(self):
        db_datasources = await self.repository.get_active()
        return db_datasources

    async def get_by_type(self, source_type: str):
        db_datasources = await self.repository.get_by_type(source_type)
        return db_datasources