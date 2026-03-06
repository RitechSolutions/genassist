from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.datasource import (
    DataSourceBase,
    DataSourceCreate,
    DataSourceRead,
    DataSourceUpdate,
)
from app.schemas.dynamic_form_schemas import DATA_SOURCE_SCHEMAS_DICT
from app.services.datasources import DataSourceService

router = APIRouter()


@router.post("", response_model=DataSourceRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.DataSource.CREATE))
])
async def create(
    datasource: DataSourceCreate,
    service: DataSourceService = Injected(DataSourceService),
):
    return await service.create(datasource)


@router.get("/form_schemas", dependencies=[Depends(auth)])
async def get_schemas():
    """Get field schemas for all data source types."""
    return DATA_SOURCE_SCHEMAS_DICT


@router.get("/{datasource_id}", response_model=DataSourceRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.DataSource.READ))
])
async def get(
    datasource_id: UUID,
    decrypt_sensitive: bool = False,
    service: DataSourceService = Injected(DataSourceService)
):
    return await service.get_by_id(datasource_id, decrypt_sensitive)


@router.get("", response_model=list[DataSourceRead], dependencies=[
    Depends(auth),
    Depends(permissions(P.DataSource.READ))
])
async def get_all(
    service: DataSourceService = Injected(DataSourceService)
):
    return await service.get_all()


@router.put("/{datasource_id}", response_model=DataSourceRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.DataSource.UPDATE))
])
async def update(
    datasource_id: UUID,
    datasource_update: DataSourceUpdate,
    service: DataSourceService = Injected(DataSourceService)
):
    return await service.update(datasource_id, datasource_update)


@router.delete("/{datasource_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.DataSource.DELETE))
])
async def delete(
    datasource_id: UUID,
    service: DataSourceService = Injected(DataSourceService)
):
    await service.delete(datasource_id)
    return {"message": "Datasource deleted successfully"}


@router.post("/test-connection", dependencies=[Depends(auth)])
async def test_connection(
    datasource: DataSourceBase,
    datasource_id: Optional[UUID] = None,
    service: DataSourceService = Injected(DataSourceService),
):
    return await service.test_connection(
        datasource.source_type, datasource.connection_data, datasource_id
    )
