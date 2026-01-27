import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4
from datetime import datetime
import os

from app.schemas.filter import BaseFilterModel
from app.services.users import UserService
from app.repositories.users import UserRepository
from app.schemas.user import UserCreate, UserRead, UserTypeRead, UserUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

# Test-only credentials - these are intentionally simple for unit testing
# and are never used in production. They can be overridden via environment variables.
TEST_USERNAME = os.environ.get('TEST_USER_USERNAME', 'testuser')
TEST_EMAIL = os.environ.get('TEST_USER_EMAIL', 'test@example.com')
TEST_PASSWORD = os.environ.get('TEST_USER_PASSWORD', 'testpassword')  # nosec B105 - test credential
# Test fixture for non-existent user scenarios - not a real credential
TEST_NONEXISTENT_USERNAME = os.environ.get('TEST_NONEXISTENT_USERNAME', 'nonexistent_user_test')

@pytest.fixture
def mock_repository():
    return AsyncMock(spec=UserRepository)

@pytest.fixture
def user_service(mock_repository):
    return UserService(repository=mock_repository)

@pytest.fixture
def sample_user_data():
    return {
        "username": TEST_USERNAME,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "is_active": 1,
        "user_type_id": uuid4(),
        "role_ids": [uuid4()]
    }

@pytest.mark.asyncio
async def test_create_user_success(user_service, mock_repository, sample_user_data):
    # Setup
    user_create = UserCreate(**sample_user_data)
    mock_repository.get_by_username.return_value = None
    mock_repository.create.return_value = MagicMock(id=uuid4())
    mock_repository.get_full.return_value = MagicMock(
        id=uuid4(),
        username=sample_user_data["username"],
        email=sample_user_data["email"],
        is_active=sample_user_data["is_active"]
    )

    # Execute
    result = await user_service.create(user_create)

    # Assert
    mock_repository.get_by_username.assert_called_once_with(user_create.username)
    mock_repository.create.assert_called_once()
    mock_repository.get_full.assert_called_once()
    assert result.username == sample_user_data["username"]
    assert result.email == sample_user_data["email"]

@pytest.mark.asyncio
async def test_create_user_duplicate_username(user_service, mock_repository, sample_user_data):
    # Setup
    user_create = UserCreate(**sample_user_data)
    mock_repository.get_by_username.return_value = MagicMock()

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await user_service.create(user_create)
    
    assert exc_info.value.error_key == ErrorKey.USERNAME_ALREADY_EXISTS
    mock_repository.get_by_username.assert_called_once_with(user_create.username)
    mock_repository.create.assert_not_called()

@pytest.mark.asyncio
async def test_get_user_by_id_success(user_service, mock_repository):
    # Setup
    user_id = uuid4()
    mock_user = UserRead(
            id=user_id,
            username="testuser",
            email="test@example.com",
            is_active=1,
            roles=[],
            user_type=UserTypeRead(id=UUID("00000196-edb1-2b80-a681-167fc2a697dd"), name="interactive", created_at=datetime.now(), updated_at=datetime.now()),
            api_keys=[]
            )
    mock_repository.get_full.return_value = mock_user

    # Execute
    result = await user_service.get_by_id(user_id)

    # Assert
    mock_repository.get_full.assert_called_once_with(user_id)
    assert result == mock_user

@pytest.mark.asyncio
async def test_get_user_by_id_not_found(user_service, mock_repository):
    # Setup
    user_id = uuid4()
    mock_repository.get_full.return_value = None

    # Execute
    result = await user_service.get_by_id(user_id)

    # Assert
    mock_repository.get_full.assert_called_once_with(user_id)
    assert result is None

@pytest.mark.asyncio
async def test_get_user_by_username_success(user_service, mock_repository):
    # Setup
    username = TEST_USERNAME
    mock_user = MagicMock(
        id=uuid4(),
        username=username,
        email=TEST_EMAIL,
        is_active=1,
        user_type = UserTypeRead(id=UUID('00000196-edb1-2b80-a681-167fc2a697dd'), name="interactive", created_at=datetime.now(), updated_at=datetime.now())
    )
    mock_repository.get_by_username.return_value = mock_user

    # Execute
    result = await user_service.get_by_username(username)

    # Assert
    mock_repository.get_by_username.assert_called_once_with(username)
    assert result == mock_user

@pytest.mark.asyncio
async def test_get_user_by_username_not_found(user_service, mock_repository):
    # Setup - using a clearly non-existent username for negative test
    username = TEST_NONEXISTENT_USERNAME
    mock_repository.get_by_username.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await user_service.get_by_username(username)

    assert exc_info.value.error_key == ErrorKey.USER_NOT_FOUND
    mock_repository.get_by_username.assert_called_once_with(username)

@pytest.mark.asyncio
async def test_get_user_by_username_not_found_no_throw(user_service, mock_repository):
    # Setup - using a clearly non-existent username for negative test
    username = TEST_NONEXISTENT_USERNAME
    mock_repository.get_by_username.return_value = None

    # Execute
    result = await user_service.get_by_username(username, throw_not_found=False)

    # Assert
    mock_repository.get_by_username.assert_called_once_with(username)
    assert result is None

@pytest.mark.asyncio
async def test_update_user_success(user_service, mock_repository):
    # Setup
    user_id = uuid4()
    update_data = UserUpdate(
        username="test",
        email="updated@example.com",
        is_active=0,
        user_type=UserTypeRead(id=UUID('00000196-edb1-2b80-a681-167fc2a697dd'), name="interactive", created_at=datetime.now(), updated_at=datetime.now())
    )
    mock_updated_user = UserRead(
            id=user_id,
            username="test",
            email="updated@example.com",
            is_active=0,
            roles=[],
            user_type=UserTypeRead(id=UUID("00000196-edb1-2b80-a681-167fc2a697dd"), name="interactive", created_at=datetime.now(), updated_at=datetime.now()),
            api_keys=[]
            )
    mock_repository.update.return_value = mock_updated_user
    mock_repository.get_full.return_value = mock_updated_user

    # Execute
    result = await user_service.update(user_id, update_data)

    # Assert
    mock_repository.update.assert_called_once_with(user_id, update_data)
    mock_repository.get_full.assert_called_once_with(mock_updated_user.id)
    assert result == mock_updated_user

@pytest.mark.asyncio
async def test_get_all_users(user_service, mock_repository):
    # Setup
    mock_users = [
        MagicMock(id=uuid4(), username=f"user{i}", email=f"user{i}@example.com")
        for i in range(3)
    ]
    mock_repository.get_all.return_value = mock_users

    # Execute
    filter_model = BaseFilterModel(skip=0, limit=10)
    result = await user_service.get_all(filter_model)

    # Assert
    mock_repository.get_all.assert_called_once_with(filter_model)
    assert result == mock_users