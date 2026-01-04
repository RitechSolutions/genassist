import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4
from app.services.role_permissions import RolePermissionsService
from app.repositories.role_permissions import RolePermissionsRepository
from app.schemas.role_permission import RolePermissionCreate, RolePermissionUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.role_permission import RolePermissionModel

@pytest.fixture
def mock_repository():
    return AsyncMock(spec=RolePermissionsRepository)

@pytest.fixture
def role_permission_service(mock_repository):
    return RolePermissionsService(repository=mock_repository)

@pytest.fixture
def sample_role_permission_data():
    return {
        "role_id": uuid4(),
        "permission_id": uuid4()
    }

@pytest.mark.asyncio
async def test_create_success(role_permission_service, mock_repository, sample_role_permission_data):
    # Setup
    role_permission_create = RolePermissionCreate(**sample_role_permission_data)
    mock_role_permission = RolePermissionModel(
        id=uuid4(),
        **sample_role_permission_data
    )
    mock_repository.create.return_value = mock_role_permission

    # Execute
    result = await role_permission_service.create(role_permission_create)

    # Assert
    mock_repository.create.assert_called_once_with(role_permission_create)
    assert result.role_id == sample_role_permission_data["role_id"]
    assert result.permission_id == sample_role_permission_data["permission_id"]

@pytest.mark.asyncio
async def test_get_by_id_success(role_permission_service, mock_repository, sample_role_permission_data):
    # Setup
    role_permission_id = uuid4()
    mock_role_permission = RolePermissionModel(
        id=role_permission_id,
        **sample_role_permission_data
    )
    mock_repository.get_by_id.return_value = mock_role_permission

    # Execute
    result = await role_permission_service.get_by_id(role_permission_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(role_permission_id)
    assert result.id == role_permission_id
    assert result.role_id == sample_role_permission_data["role_id"]
    assert result.permission_id == sample_role_permission_data["permission_id"]

@pytest.mark.asyncio
async def test_get_by_id_not_found(role_permission_service, mock_repository):
    # Setup
    role_permission_id = uuid4()
    mock_repository.get_by_id.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await role_permission_service.get_by_id(role_permission_id)
    
    assert exc_info.value.error_key == ErrorKey.ROLE_PERMISSION_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(role_permission_id)

@pytest.mark.asyncio
async def test_get_all_success(role_permission_service, mock_repository, sample_role_permission_data):
    # Setup
    mock_role_permissions = [
        RolePermissionModel(
            id=uuid4(),
            **{
                **sample_role_permission_data,
                "role_id": uuid4()
            }
        )
        for _ in range(3)
    ]
    mock_repository.get_all.return_value = mock_role_permissions

    # Execute
    result = await role_permission_service.get_all()

    # Assert
    mock_repository.get_all.assert_called_once()
    assert len(result) == len(mock_role_permissions)

@pytest.mark.asyncio
async def test_update_success(role_permission_service, mock_repository, sample_role_permission_data):
    # Setup
    role_permission_id = uuid4()
    update_data = RolePermissionUpdate(
        role_id=uuid4(),
        permission_id=uuid4()
    )
    mock_role_permission = RolePermissionModel(
        id=role_permission_id,
        **sample_role_permission_data
    )
    mock_repository.get_by_id.return_value = mock_role_permission
    
    updated_role_permission = RolePermissionModel(
        id=role_permission_id,
        **{
            **sample_role_permission_data,
            **update_data.model_dump(exclude_unset=True)
        }
    )
    mock_repository.update.return_value = updated_role_permission

    # Execute
    result = await role_permission_service.update(role_permission_id, update_data)

    # Assert
    mock_repository.update.assert_called_once_with(role_permission_id, update_data)
    assert result.id == role_permission_id
    assert result.role_id == update_data.role_id
    assert result.permission_id == update_data.permission_id

@pytest.mark.asyncio
async def test_delete_success(role_permission_service, mock_repository, sample_role_permission_data):
    # Setup
    role_permission_id = uuid4()
    mock_role_permission = RolePermissionModel(
        id=role_permission_id,
        **sample_role_permission_data
    )
    mock_repository.get_by_id.return_value = mock_role_permission

    # Execute
    result = await role_permission_service.delete(role_permission_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(role_permission_id)
    mock_repository.delete.assert_called_once_with(mock_role_permission)
    assert result["message"] == f"RolePermission {role_permission_id} deleted successfully." 