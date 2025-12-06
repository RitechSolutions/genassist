import pytest
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from app.schemas.filter import BaseFilterModel
from app.services.roles import RolesService
from app.repositories.roles import RolesRepository
from app.schemas.role import RoleCreate, RoleUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.role import RoleModel

@pytest.fixture
def mock_repository():
    return AsyncMock(spec=RolesRepository)

@pytest.fixture
def role_service(mock_repository):
    return RolesService(repository=mock_repository)

@pytest.fixture
def sample_role_data():
    return {
        "name": "test_role",
        "is_active": 1
    }

@pytest.mark.asyncio
async def test_create_success(role_service, mock_repository, sample_role_data):
    # Setup
    role_create = RoleCreate(**sample_role_data)
    mock_role = RoleModel(**sample_role_data)
    mock_repository.create_role.return_value = mock_role

    # Execute
    result = await role_service.create(role_create)

    # Assert
    mock_repository.create_role.assert_called_once_with(role_create)
    assert result.name == sample_role_data["name"]
    assert result.is_active == sample_role_data["is_active"]

@pytest.mark.asyncio
async def test_get_by_id_success(role_service, mock_repository, sample_role_data):
    # Setup
    role_id = uuid4()
    mock_role = RoleModel(id=role_id, **sample_role_data)
    mock_repository.get_by_id.return_value = mock_role

    # Execute
    result = await role_service.get_by_id(role_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(role_id)
    assert result.id == role_id
    assert result.name == sample_role_data["name"]
    assert result.is_active == sample_role_data["is_active"]

@pytest.mark.asyncio
async def test_get_by_id_not_found(role_service, mock_repository):
    # Setup
    role_id = uuid4()
    mock_repository.get_by_id.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await role_service.get_by_id(role_id)
    
    assert exc_info.value.error_key == ErrorKey.ROLE_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(role_id)

@pytest.mark.asyncio
async def test_get_all_success(role_service, mock_repository, sample_role_data):
    # Setup
    mock_roles = [
        RoleModel(id=uuid4(), **sample_role_data)
        for _ in range(2)
    ]
    mock_repository.get_all.return_value = mock_roles

    # Execute
    filter_model = BaseFilterModel(skip=0, limit=10)
    result = await role_service.get_all(filter_model)

    # Assert
    mock_repository.get_all.assert_called_once()
    assert result == mock_roles

@pytest.mark.asyncio
async def test_update_success(role_service, mock_repository, sample_role_data):
    # Setup
    role_id = uuid4()
    update_data = RoleUpdate(
        name="updated_role",
        is_active=0
    )
    mock_role = RoleModel(id=role_id, **sample_role_data)
    mock_repository.get_by_id.return_value = mock_role

    updated_data = {
        **sample_role_data,
        **update_data.model_dump(exclude_unset=True),
        "id": role_id
    }
    updated_role = RoleModel(**updated_data)
    mock_repository.update.return_value = updated_role

    # Execute
    result = await role_service.update_partial(role_id, update_data)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(role_id)
    mock_repository.update.assert_called_once()
    assert result.id == role_id
    assert result.name == update_data.name
    assert result.is_active == update_data.is_active

@pytest.mark.asyncio
async def test_delete_success(role_service, mock_repository, sample_role_data):
    # Setup
    role_id = uuid4()
    mock_role = RoleModel(id=role_id, **sample_role_data)
    mock_repository.get_by_id.return_value = mock_role

    # Execute
    result = await role_service.delete(role_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(role_id)
    mock_repository.delete.assert_called_once_with(mock_role)
    assert result["message"] == f"Role with ID {role_id} has been deleted." 