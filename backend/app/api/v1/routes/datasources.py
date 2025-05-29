from uuid import UUID
from fastapi import APIRouter, Depends

from app.auth.dependencies import auth, permissions
from app.schemas.datasource import DataSourceRead, DataSourceCreate, DataSourceUpdate
from app.services.datasources import DataSourceService
<<<<<<< HEAD
=======
from app.modules.agents.data.supported_configuration import DATA_SOURCE_SCHEMAS
>>>>>>> development

router = APIRouter()

@router.post("/", response_model=DataSourceRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:data_source"))
])
async def create(
    datasource: DataSourceCreate,
    service: DataSourceService = Depends()
):
    return await service.create(datasource)

<<<<<<< HEAD
=======
@router.get("/schemas", dependencies=[Depends(auth)])
async def get_schemas():
    return DATA_SOURCE_SCHEMAS

>>>>>>> development
@router.get("/{datasource_id}", response_model=DataSourceRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:data_source"))
])
async def get(
    datasource_id: UUID,
    service: DataSourceService = Depends()
):
    return await service.get_by_id(datasource_id)

@router.get("/", response_model=list[DataSourceRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:data_source"))
])
async def get_all(
    service: DataSourceService = Depends()
):
    return await service.get_all()

@router.put("/{datasource_id}", response_model=DataSourceRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:data_source"))
])
async def update(
    datasource_id: UUID,
    datasource_update: DataSourceUpdate,
    service: DataSourceService = Depends()
):
    return await service.update(datasource_id, datasource_update)

@router.delete("/{datasource_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:data_source"))
])
async def delete(
    datasource_id: UUID,
    service: DataSourceService = Depends()
):
    await service.delete(datasource_id)
    return {"message": "Datasource deleted successfully"} 