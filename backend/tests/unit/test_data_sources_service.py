import pytest
from unittest.mock import AsyncMock, create_autospec
from uuid import UUID, uuid4
from app.services.datasources import DataSourceService
from app.repositories.datasources import DataSourcesRepository
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.datasource import DataSourceModel

@pytest.fixture
def mock_repository():
    return AsyncMock(spec=DataSourcesRepository)

@pytest.fixture
def data_source_service(mock_repository):
    return DataSourceService(repository=mock_repository)

@pytest.fixture
def sample_data_source_data():
    return {
        "name": "test_source",
        "source_type": "test_type",
        "connection_data": {
            "url": "postgresql://user:pass@localhost:5432/db"
        },
        "is_active": 1
    }

@pytest.mark.asyncio
async def test_create_data_source_success(data_source_service, mock_repository, sample_data_source_data):
    # Setup
    data_source_create = DataSourceCreate(**sample_data_source_data)
    mock_source = create_autospec(DataSourceModel, instance=True)
    mock_source.id = uuid4()
    mock_source.name = sample_data_source_data["name"]
    mock_source.source_type = sample_data_source_data["source_type"]
    mock_source.connection_data = sample_data_source_data["connection_data"]
    mock_source.is_active = sample_data_source_data["is_active"]
    mock_repository.create.return_value = mock_source

    # Execute
    result = await data_source_service.create(data_source_create)

    # Assert
    mock_repository.create.assert_called_once_with(data_source_create)
    assert result.name == sample_data_source_data["name"]
    assert result.source_type == sample_data_source_data["source_type"]
    assert result.connection_data == sample_data_source_data["connection_data"]
    assert result.is_active == sample_data_source_data["is_active"]

@pytest.mark.asyncio
async def test_get_data_source_by_id_success(data_source_service, mock_repository, sample_data_source_data):
    # Setup
    source_id = uuid4()
    mock_source = create_autospec(DataSourceModel, instance=True)
    mock_source.id = source_id
    mock_source.name = sample_data_source_data["name"]
    mock_source.source_type = sample_data_source_data["source_type"]
    mock_source.connection_data = sample_data_source_data["connection_data"]
    mock_source.is_active = sample_data_source_data["is_active"]
    mock_repository.get_by_id.return_value = mock_source

    # Execute
    result = await data_source_service.get_by_id(source_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(source_id)
    assert result == mock_source

@pytest.mark.asyncio
async def test_get_data_source_by_id_not_found(data_source_service, mock_repository):
    # Setup
    source_id = uuid4()
    mock_repository.get_by_id.side_effect = AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND)

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await data_source_service.get_by_id(source_id)
    
    assert exc_info.value.error_key == ErrorKey.DATASOURCE_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(source_id)

@pytest.mark.asyncio
async def test_get_data_sources_by_type(data_source_service, mock_repository, sample_data_source_data):
    # Setup
    mock_sources = []
    for _ in range(2):
        source = create_autospec(DataSourceModel, instance=True)
        source.id = uuid4()
        source.name = sample_data_source_data["name"]
        source.source_type = sample_data_source_data["source_type"]
        source.connection_data = sample_data_source_data["connection_data"]
        source.is_active = sample_data_source_data["is_active"]
        mock_sources.append(source)
    mock_repository.get_by_type.return_value = mock_sources

    # Execute
    result = await data_source_service.get_by_type(sample_data_source_data["source_type"])

    # Assert
    mock_repository.get_by_type.assert_called_once_with(sample_data_source_data["source_type"])
    assert result == mock_sources

@pytest.mark.asyncio
async def test_get_all_data_sources(data_source_service, mock_repository, sample_data_source_data):
    # Setup
    mock_sources = []
    for _ in range(2):
        source = create_autospec(DataSourceModel, instance=True)
        source.id = uuid4()
        source.name = sample_data_source_data["name"]
        source.source_type = sample_data_source_data["source_type"]
        source.connection_data = sample_data_source_data["connection_data"]
        source.is_active = sample_data_source_data["is_active"]
        mock_sources.append(source)
    mock_repository.get_all.return_value = mock_sources

    # Execute
    result = await data_source_service.get_all()

    # Assert
    mock_repository.get_all.assert_called_once()
    assert result == mock_sources

@pytest.mark.asyncio
async def test_delete_data_source_success(data_source_service, mock_repository):
    # Setup
    source_id = uuid4()

    # Execute
    await data_source_service.delete(source_id)

    # Assert
    mock_repository.delete.assert_called_once_with(source_id)

@pytest.mark.asyncio
async def test_get_active_data_sources(data_source_service, mock_repository, sample_data_source_data):
    # Setup
    mock_sources = []
    for _ in range(2):
        source = create_autospec(DataSourceModel, instance=True)
        source.id = uuid4()
        source.name = sample_data_source_data["name"]
        source.source_type = sample_data_source_data["source_type"]
        source.connection_data = sample_data_source_data["connection_data"]
        source.is_active = sample_data_source_data["is_active"]
        mock_sources.append(source)
    mock_repository.get_active.return_value = mock_sources

    # Execute
    result = await data_source_service.get_active()

    # Assert
    mock_repository.get_active.assert_called_once()
    assert result == mock_sources

@pytest.mark.asyncio
async def test_update_data_source_success(data_source_service, mock_repository):
    # Setup
    source_id = uuid4()
    update_data = DataSourceUpdate(
        name="updated_source",
        source_type="updated_type",
        connection_data={
            "url": "postgresql://updated:pass@localhost:5432/db"
        },
        is_active=0
    )
    mock_updated_source = create_autospec(DataSourceModel, instance=True)
    mock_updated_source.id = source_id
    mock_updated_source.name = update_data.name
    mock_updated_source.source_type = update_data.source_type
    mock_updated_source.connection_data = update_data.connection_data
    mock_updated_source.is_active = update_data.is_active
    mock_repository.update.return_value = mock_updated_source

    # Execute
    result = await data_source_service.update(source_id, update_data)

    # Assert
    mock_repository.update.assert_called_once_with(source_id, update_data.model_dump(exclude_unset=True))
    assert result == mock_updated_source 