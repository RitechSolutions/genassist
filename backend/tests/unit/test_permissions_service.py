import pytest
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from app.schemas.filter import BaseFilterModel
from app.services.permissions import PermissionsService
from app.repositories.permissions import PermissionsRepository
from app.schemas.permission import PermissionCreate, PermissionUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.permission import PermissionModel

@pytest.fixture
def mock_repository():
    return AsyncMock(spec=PermissionsRepository)

@pytest.fixture
def permission_service(mock_repository):
    return PermissionsService(repository=mock_repository)

@pytest.fixture
def sample_permission_data():
    return {
        "name": "test_permission",
        "description": "Test permission description",
        "is_active": 1
    }

@pytest.mark.asyncio
async def test_create_success(permission_service, mock_repository, sample_permission_data):
    # Setup
    permission_create = PermissionCreate(**sample_permission_data)
    mock_permission = PermissionModel(**sample_permission_data)
    mock_repository.create_permission.return_value = mock_permission

    # Execute
    result = await permission_service.create(permission_create)

    # Assert
    mock_repository.create_permission.assert_called_once_with(permission_create)
    assert result.name == sample_permission_data["name"]
    assert result.description == sample_permission_data["description"]
    assert result.is_active == sample_permission_data["is_active"]


@pytest.mark.asyncio
async def test_get_by_id_success(permission_service, mock_repository, sample_permission_data):
    # Setup
    permission_id = uuid4()
    mock_permission = PermissionModel(id=permission_id, **sample_permission_data)
    mock_repository.get_by_id.return_value = mock_permission

    # Execute
    result = await permission_service.get_by_id(permission_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(permission_id)
    assert result.id == permission_id
    assert result.name == sample_permission_data["name"]
    assert result.description == sample_permission_data["description"]

@pytest.mark.asyncio
async def test_get_by_id_not_found(permission_service, mock_repository):
    # Setup
    permission_id = uuid4()
    mock_repository.get_by_id.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await permission_service.get_by_id(permission_id)
    
    assert exc_info.value.error_key == ErrorKey.PERMISSION_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(permission_id)

@pytest.mark.asyncio
async def test_get_all_success(permission_service, mock_repository, sample_permission_data):
    # Setup
    mock_permissions = [
        PermissionModel(id=uuid4(), **{
            **sample_permission_data,
            "name": f"permission{i}"
        })
        for i in range(3)
    ]
    mock_repository.get_all.return_value = mock_permissions

    # Execute
    filter_model = BaseFilterModel(skip=0, limit=10)
    result = await permission_service.get_all(filter_model)

    # Assert
    mock_repository.get_all.assert_called_once()
    assert len(result) == len(mock_permissions)
    for i, permission in enumerate(result):
        assert permission.name == f"permission{i}"
        assert permission.description == sample_permission_data["description"]


@pytest.mark.asyncio
async def test_update_success(permission_service, mock_repository, sample_permission_data):
    # Setup
    permission_id = uuid4()
    update_data = PermissionUpdate(
            name="updated_permission",
            description="Updated description"
            )

    updated_permission = PermissionModel(
            id=permission_id,
            name=update_data.name,
            description=update_data.description,
            is_active=sample_permission_data["is_active"]
            )
    mock_repository.update_permission.return_value = updated_permission

    # Execute
    result = await permission_service.update(permission_id, update_data)

    # Assert
    mock_repository.update_permission.assert_called_once_with(permission_id, update_data)
    assert result.id == permission_id
    assert result.name == update_data.name
    assert result.description == update_data.description

@pytest.mark.asyncio
async def test_delete_success(permission_service, mock_repository, sample_permission_data):
    # Setup
    permission_id = uuid4()
    mock_permission = PermissionModel(id=permission_id, **sample_permission_data)
    mock_repository.get_by_id.return_value = mock_permission

    # Execute
    result = await permission_service.delete(permission_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(permission_id)
    mock_repository.delete.assert_called_once_with(mock_permission)
    assert result["message"] == f"Permission {permission_id} deleted successfully." 